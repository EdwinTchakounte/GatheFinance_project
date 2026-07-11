import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

/// Partage natif propre pour les contenus GATHE (campagnes + actualités).
///
/// Construit un message texte + lien public, et **joint le média** (flyer /
/// image d'entête) en le téléchargeant d'abord dans un fichier temporaire.
/// Best-effort : si le média ne peut pas être téléchargé, on partage le texte
/// seul — le partage n'échoue jamais à cause de l'image.
class ShareService {
  ShareService._();
  static final ShareService instance = ShareService._();

  final Dio _dio = Dio(
    BaseOptions(
      connectTimeout: const Duration(seconds: 12),
      receiveTimeout: const Duration(seconds: 15),
    ),
  );

  /// Partage un contenu : [text] (corps + lien), média optionnel [mediaUrl],
  /// [subject] (objet, utilisé par mail/certaines apps).
  Future<void> shareContent({
    required String text,
    String? mediaUrl,
    String? subject,
  }) async {
    final files = <XFile>[];
    if (mediaUrl != null && mediaUrl.trim().isNotEmpty) {
      final path = await _downloadToTemp(mediaUrl.trim());
      if (path != null) files.add(XFile(path));
    }
    if (files.isNotEmpty) {
      await Share.shareXFiles(files, text: text, subject: subject);
    } else {
      await Share.share(text, subject: subject);
    }
  }

  /// Télécharge [url] dans un fichier temporaire. Renvoie le chemin, ou null
  /// en cas d'échec (le partage se rabat alors sur le texte seul).
  Future<String?> _downloadToTemp(String url) async {
    try {
      final dir = await getTemporaryDirectory();
      final uri = Uri.parse(url);
      var name = uri.pathSegments.isNotEmpty ? uri.pathSegments.last : 'gathe';
      if (!name.contains('.')) name = '$name.jpg';
      final path = '${dir.path}/gathe_share_$name';
      final resp = await _dio.download(url, path);
      if (resp.statusCode == 200 && File(path).existsSync()) return path;
      return null;
    } catch (e) {
      debugPrint('ShareService: download média échoué ($e) — partage texte seul');
      return null;
    }
  }
}
