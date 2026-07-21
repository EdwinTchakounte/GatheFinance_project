import 'package:dio/dio.dart';

import '../../../../core/error/exceptions.dart';
import '../../../../core/network/api_client.dart';
import '../../../../core/network/api_exceptions.dart';
import '../../domain/entities/member.dart';
import 'auth_remote_datasource.dart';

/// Implémentation HTTP de [AuthRemoteDataSource] — calls `/api/v1/auth/*`.
///
/// Flow :
///   1. signIn : POST /auth/login/ (avec CSRF priming si absent)
///   2. currentMember : GET /auth/me/ — 401/403 → null (non connecté)
///   3. signOut : POST /auth/logout/ + clear local cookies
class AuthDioDataSource implements AuthRemoteDataSource {
  AuthDioDataSource(this._client);

  final ApiClient _client;
  Dio get _dio => _client.dio;

  @override
  Future<Member> signIn({
    required String email,
    required String password,
  }) async {
    try {
      // Toujours purger l'ancienne session avant un nouveau login.
      // Sinon un cookie sessionid/csrftoken stale (apres un restart backend
      // qui rotate la SECRET_KEY ou simplement apres expiration) fait
      // echouer le POST avec un 403 CSRF, et l'utilisateur voit
      // "Connexion impossible" sans pouvoir s'en sortir.
      await _client.clearSession();
      await _client.primeCsrf();
      return await _signInAttempt(email, password);
    } on DioException catch (e) {
      // 403 sur le login = quasi-toujours un CSRF token expire / orphelin.
      // On retente une fois avec une session totalement vierge.
      if (e.response?.statusCode == 403) {
        try {
          await _client.clearSession();
          await _client.primeCsrf();
          return await _signInAttempt(email, password);
        } on DioException catch (retryErr) {
          throw mapDioError(retryErr);
        }
      }
      throw mapDioError(e);
    }
  }

  Future<Member> _signInAttempt(String email, String password) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/auth/login/',
      data: {'email': email, 'password': password},
    );
    final data = response.data;
    if (data == null || data['member'] == null) {
      throw const ServerException(
        'Compte sans profil membre — contactez l\'administration.',
        200,
      );
    }
    return _toMember(data);
  }

  @override
  Future<Member?> currentMember() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>('/auth/me/');
      final data = response.data;
      if (data == null || data['member'] == null) return null;
      return _toMember(data);
    } on DioException catch (e) {
      // 401/403 = non connecté → null (pas une erreur métier).
      if (e.response?.statusCode == 401 || e.response?.statusCode == 403) {
        return null;
      }
      throw mapDioError(e);
    }
  }

  @override
  Future<void> signOut() async {
    try {
      await _dio.post<void>('/auth/logout/');
    } on DioException catch (e) {
      // Si le serveur estime qu'on n'est pas connecté, on s'en fout :
      // on coupe quand même côté client.
      if (e.response?.statusCode != 401 && e.response?.statusCode != 403) {
        throw mapDioError(e);
      }
    } finally {
      await _client.clearSession();
    }
  }

  @override
  Future<Member> updateProfile({
    required String prenom,
    required String nom,
    required String phone,
  }) async {
    try {
      final res = await _dio.patch<Map<String, dynamic>>(
        '/members/me/',
        data: {
          'prenom': prenom.trim(),
          'nom': nom.trim(),
          'phone': phone.trim(),
        },
      );
      // PATCH /members/me/ ne renvoie PAS l'email (il est sur User, pas
      // Member). On recharge donc /auth/me/ pour avoir l'identité complète.
      final updated = await currentMember();
      if (updated != null) return updated;
      // Fallback : si /auth/me/ échoue, on assemble manuellement à partir
      // du body PATCH (email perdu).
      final data = res.data ?? const {};
      return Member(
        id: (data['id'] as num).toInt(),
        numeroMembre: (data['numero_membre'] as String?) ?? '',
        prenom: (data['prenom'] as String?) ?? prenom,
        nom: (data['nom'] as String?) ?? nom,
        email: '',
        phone: (data['phone'] as String?) ?? phone,
        statut: _toStatus((data['statut'] as String?) ?? 'actif'),
        dateAdhesion: _toDate(data['date_adhesion']),
      );
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<Member> updatePhoto(String filePath) async {
    try {
      final form = FormData();
      form.files.add(
        MapEntry(
          'photo_profil',
          await MultipartFile.fromFile(filePath),
        ),
      );
      await _dio.patch<Map<String, dynamic>>('/members/me/', data: form);
      // PATCH /members/me/ ne renvoie pas l'email → on recharge l'identité
      // complète (avec la nouvelle photo_profil_url) via /auth/me/.
      final updated = await currentMember();
      if (updated != null) return updated;
      throw const ServerException(
        'Photo enregistrée mais rechargement du profil échoué.',
        200,
      );
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<String?> changePassword({
    required String oldPassword,
    required String newPassword,
  }) async {
    try {
      await _dio.post<void>(
        '/auth/change-password/',
        data: {
          'current_password': oldPassword,
          'new_password': newPassword,
        },
      );
      return null;
    } on DioException catch (e) {
      // 400 = mot de passe actuel faux ou nouveau invalide → message UI.
      if (e.response?.statusCode == 400) {
        final body = e.response?.data;
        if (body is Map<String, dynamic>) {
          final detail = body['detail'];
          if (detail is String && detail.isNotEmpty) return detail;
          for (final v in body.values) {
            if (v is List && v.isNotEmpty && v.first is String) {
              return v.first as String;
            }
            if (v is String && v.isNotEmpty) return v;
          }
        }
        return 'Modification refusée par le serveur.';
      }
      throw mapDioError(e);
    }
  }

  @override
  Future<void> requestPasswordReset({required String email}) async {
    try {
      await _client.primeCsrf();
      await _dio.post<void>(
        '/auth/password-reset/request/',
        data: {'email': email.trim()},
      );
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<String?> confirmPasswordReset({
    required String email,
    required String code,
    required String newPassword,
  }) async {
    try {
      await _client.primeCsrf();
      await _dio.post<void>(
        '/auth/password-reset/confirm/',
        data: {
          'email': email.trim(),
          'code': code.trim(),
          'new_password': newPassword,
        },
      );
      return null;
    } on DioException catch (e) {
      if (e.response?.statusCode == 400) {
        final body = e.response?.data;
        if (body is Map<String, dynamic>) {
          final detail = body['detail'];
          if (detail is String && detail.isNotEmpty) return detail;
        }
        return 'Code invalide ou expiré.';
      }
      if (e.response?.statusCode == 429) {
        return 'Trop de tentatives — réessayez dans une heure.';
      }
      throw mapDioError(e);
    }
  }

  @override
  Future<PasswordSetupTokenInfo> verifySetupToken(String token) async {
    try {
      final res = await _dio.get<Map<String, dynamic>>(
        '/auth/setup-password/verify/',
        queryParameters: {'token': token.trim()},
      );
      final body = res.data ?? const <String, dynamic>{};
      final emailMask = (body['email_mask'] as String?) ?? '';
      final expiresAtRaw = (body['expires_at'] as String?) ?? '';
      final expiresAt =
          DateTime.tryParse(expiresAtRaw) ?? DateTime.now().add(const Duration(hours: 72));
      return PasswordSetupTokenInfo(emailMask: emailMask, expiresAt: expiresAt);
    } on DioException catch (e) {
      // 404 = token inconnu, 410 = expire/consume → on remonte un message lisible.
      final code = e.response?.statusCode;
      if (code == 404 || code == 410 || code == 400) {
        final body = e.response?.data;
        if (body is Map<String, dynamic>) {
          final detail = body['detail'];
          if (detail is String && detail.isNotEmpty) {
            throw Exception(detail);
          }
        }
        throw Exception('Lien invalide ou expire.');
      }
      throw mapDioError(e);
    }
  }

  @override
  Future<String?> confirmPasswordSetup({
    required String token,
    required String newPassword,
  }) async {
    try {
      await _client.primeCsrf();
      await _dio.post<void>(
        '/auth/setup-password/confirm/',
        data: {
          'token': token.trim(),
          'password': newPassword,
        },
      );
      return null;
    } on DioException catch (e) {
      final code = e.response?.statusCode;
      if (code == 400 || code == 404 || code == 410) {
        final body = e.response?.data;
        if (body is Map<String, dynamic>) {
          final detail = body['detail'];
          if (detail is String && detail.isNotEmpty) return detail;
        }
        return 'Mot de passe invalide ou lien expire.';
      }
      if (code == 429) {
        return 'Trop de tentatives . reessayez dans une heure.';
      }
      throw mapDioError(e);
    }
  }
}

Member _toMember(Map<String, dynamic> data) {
  final email = (data['email'] as String?) ?? '';
  final m = data['member'] as Map<String, dynamic>;
  return Member(
    id: (m['id'] as num).toInt(),
    numeroMembre: (m['numero_membre'] as String?) ?? '',
    prenom: (m['prenom'] as String?) ?? '',
    nom: (m['nom'] as String?) ?? '',
    email: email,
    phone: (m['phone'] as String?) ?? '',
    statut: _toStatus((m['statut'] as String?) ?? 'actif'),
    dateAdhesion: _toDate(m['date_adhesion']),
    photoUrl: (m['photo_profil_url'] as String?),
  );
}

MemberStatus _toStatus(String raw) {
  switch (raw) {
    case 'suspendu':
      return MemberStatus.suspendu;
    case 'radie':
      return MemberStatus.radie;
    case 'temporaire':
      return MemberStatus.temporaire;
    case 'actif':
    default:
      return MemberStatus.actif;
  }
}

DateTime _toDate(dynamic value) {
  if (value is String && value.isNotEmpty) {
    return DateTime.tryParse(value) ?? DateTime.now();
  }
  return DateTime.now();
}
