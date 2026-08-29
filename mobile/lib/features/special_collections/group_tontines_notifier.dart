import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/di/providers.dart';
import '../../core/services/tara_checkout_launcher.dart';

num? _asNum(dynamic v) {
  if (v == null) return null;
  if (v is num) return v;
  return num.tryParse(v.toString());
}

/// Résumé d'une réunion (carte + liste).
class GroupTontineSummary {
  const GroupTontineSummary({
    required this.id,
    required this.nom,
    required this.description,
    required this.solde,
    required this.montantCotisation,
    required this.isOpen,
    required this.membersCount,
    this.myRole,
  });

  final int id;
  final String nom;
  final String description;
  final num solde;
  final num montantCotisation;
  final bool isOpen;
  final int membersCount;
  final String? myRole; // president | tresorier | membre

  bool get canManage => myRole == 'president' || myRole == 'tresorier';

  factory GroupTontineSummary.fromJson(Map<String, dynamic> j) =>
      GroupTontineSummary(
        id: (j['id'] as num?)?.toInt() ?? 0,
        nom: j['nom'] as String? ?? '',
        description: j['description'] as String? ?? '',
        solde: _asNum(j['solde']) ?? 0,
        montantCotisation: _asNum(j['montant_cotisation']) ?? 0,
        isOpen: j['is_open'] as bool? ?? false,
        membersCount: (j['members_count'] as num?)?.toInt() ?? 0,
        myRole: j['my_role'] as String?,
      );
}

/// Catalogue d'actions habilitables dans une réunion (rôles personnalisés).
const kGroupRoleActions = <String, String>{
  'can_manage_funds': 'Verser (payout)',
  'can_grant_loan': 'Accorder un prêt',
  'can_manage_roster': 'Gérer le roster / les rôles',
  'can_record_cotisation': 'Enregistrer des cotisations',
  'can_close': 'Clôturer la réunion',
};

Map<String, bool> _permsFromJson(dynamic raw) {
  final m = raw is Map<String, dynamic> ? raw : const <String, dynamic>{};
  return {for (final k in kGroupRoleActions.keys) k: m[k] == true};
}

class GroupCustomRole {
  const GroupCustomRole({required this.id, required this.nom, required this.perms});

  final int id;
  final String nom;
  final Map<String, bool> perms;

  factory GroupCustomRole.fromJson(Map<String, dynamic> j) => GroupCustomRole(
        id: (j['id'] as num?)?.toInt() ?? 0,
        nom: j['nom'] as String? ?? '',
        perms: _permsFromJson(j),
      );
}

class GroupMember {
  const GroupMember({
    required this.memberId,
    required this.numeroMembre,
    required this.nom,
    required this.prenom,
    required this.role,
    required this.roleDisplay,
    this.customRoleId,
    this.customRoleNom = '',
    this.permissions = const {},
  });

  final int memberId;
  final String numeroMembre;
  final String nom;
  final String prenom;
  final String role;
  final String roleDisplay;
  final int? customRoleId;
  final String customRoleNom;
  final Map<String, bool> permissions;

  factory GroupMember.fromJson(Map<String, dynamic> j) => GroupMember(
        memberId: (j['member_id'] as num?)?.toInt() ?? 0,
        numeroMembre: j['numero_membre'] as String? ?? '',
        nom: j['nom'] as String? ?? '',
        prenom: j['prenom'] as String? ?? '',
        role: j['role'] as String? ?? 'membre',
        roleDisplay: j['role_display'] as String? ?? '',
        customRoleId: (j['custom_role_id'] as num?)?.toInt(),
        customRoleNom: j['custom_role_nom'] as String? ?? '',
        permissions: _permsFromJson(j['permissions']),
      );
}

class GroupLoan {
  const GroupLoan({
    required this.id,
    required this.memberId,
    required this.nom,
    required this.prenom,
    required this.montant,
    required this.soldeRestant,
    required this.statut,
    required this.statutDisplay,
    this.avalisteDisplay = '',
  });

  final int id;
  final int memberId;
  final String nom;
  final String prenom;
  final num montant;
  final num soldeRestant;
  final String statut;
  final String statutDisplay;
  // Avaliste INFORMATIF (membre du roster OU nom libre). Sans impact financier.
  final String avalisteDisplay;

  factory GroupLoan.fromJson(Map<String, dynamic> j) => GroupLoan(
        id: (j['id'] as num?)?.toInt() ?? 0,
        memberId: (j['member_id'] as num?)?.toInt() ?? 0,
        nom: j['nom'] as String? ?? '',
        prenom: j['prenom'] as String? ?? '',
        montant: _asNum(j['montant']) ?? 0,
        soldeRestant: _asNum(j['solde_restant']) ?? 0,
        statut: j['statut'] as String? ?? 'en_cours',
        statutDisplay: j['statut_display'] as String? ?? '',
        avalisteDisplay: j['avaliste_display'] as String? ?? '',
      );
}

class GroupTx {
  const GroupTx({
    required this.typeOpDisplay,
    required this.montant,
    required this.soldeApres,
    required this.libelle,
    required this.memberNom,
    required this.memberPrenom,
    this.actedByName = '',
  });

  final String typeOpDisplay;
  final num montant;
  final num soldeApres;
  final String libelle;
  final String memberNom;
  final String memberPrenom;
  final String actedByName;

  factory GroupTx.fromJson(Map<String, dynamic> j) => GroupTx(
        typeOpDisplay: j['type_op_display'] as String? ?? '',
        montant: _asNum(j['montant']) ?? 0,
        soldeApres: _asNum(j['solde_apres']) ?? 0,
        libelle: j['libelle'] as String? ?? '',
        memberNom: j['member_nom'] as String? ?? '',
        memberPrenom: j['member_prenom'] as String? ?? '',
        actedByName: j['acted_by_name'] as String? ?? '',
      );
}

class GroupDetail {
  const GroupDetail({
    required this.summary,
    required this.members,
    required this.loans,
    required this.transactions,
    this.customRoles = const [],
    this.myPermissions = const {},
    this.myMemberId,
  });

  final GroupTontineSummary summary;
  final List<GroupMember> members;
  final List<GroupLoan> loans;
  final List<GroupTx> transactions;
  final List<GroupCustomRole> customRoles;
  final Map<String, bool> myPermissions;
  final int? myMemberId;

  bool can(String action) => myPermissions[action] == true;

  factory GroupDetail.fromJson(Map<String, dynamic> j) => GroupDetail(
        summary: GroupTontineSummary.fromJson(j),
        myMemberId: (j['my_member_id'] as num?)?.toInt(),
        myPermissions: _permsFromJson(j['my_permissions']),
        members: (j['members'] as List<dynamic>? ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(GroupMember.fromJson)
            .toList(),
        loans: (j['loans'] as List<dynamic>? ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(GroupLoan.fromJson)
            .toList(),
        transactions: (j['transactions'] as List<dynamic>? ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(GroupTx.fromJson)
            .toList(),
        customRoles: (j['custom_roles'] as List<dynamic>? ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(GroupCustomRole.fromJson)
            .toList(),
      );
}

class GroupTontinesNotifier extends AsyncNotifier<List<GroupTontineSummary>> {
  Future<List<GroupTontineSummary>> _fetch() async {
    final dio = ref.read(apiClientProvider).dio;
    final res = await dio.get<List<dynamic>>('/special-collections/groups/');
    return (res.data ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(GroupTontineSummary.fromJson)
        .toList();
  }

  @override
  Future<List<GroupTontineSummary>> build() => _fetch();

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(_fetch);
  }

  Future<GroupDetail> fetchDetail(int id) async {
    final dio = ref.read(apiClientProvider).dio;
    final res = await dio.get<Map<String, dynamic>>(
      '/special-collections/groups/$id/',
    );
    return GroupDetail.fromJson(res.data ?? const {});
  }

  Future<GroupDetail> _post(
    int id,
    String suffix,
    Map<String, dynamic> data,
  ) async {
    final dio = ref.read(apiClientProvider).dio;
    final res = await dio.post<Map<String, dynamic>>(
      '/special-collections/groups/$id/$suffix',
      data: data,
    );
    await refresh();
    return GroupDetail.fromJson(res.data ?? const {});
  }

  Future<GroupDetail> payout(int id, int beneficiaryId, num montant) => _post(
        id,
        'payout/',
        {'beneficiary_id': beneficiaryId, 'montant': montant},
      );

  Future<GroupDetail> loan(
    int id,
    int memberId,
    num montant, {
    int? avalisteId,
    String avalisteNom = '',
  }) =>
      _post(id, 'loan/', {
        'member_id': memberId,
        'montant': montant,
        if (avalisteId != null) 'avaliste_id': avalisteId,
        if (avalisteNom.trim().isNotEmpty) 'avaliste_nom': avalisteNom.trim(),
      });

  // Rôles personnalisés (actions rattachées) — membre habilité « gérer le roster ».
  Future<GroupDetail> createRole(int id, String nom, Map<String, bool> perms) =>
      _post(id, 'roles/', {'nom': nom, 'permissions': perms});

  Future<GroupDetail> deleteRole(int id, int roleId) async {
    final dio = ref.read(apiClientProvider).dio;
    final res = await dio.delete<Map<String, dynamic>>(
      '/special-collections/groups/$id/roles/$roleId/',
    );
    await refresh();
    return GroupDetail.fromJson(res.data ?? const {});
  }

  Future<GroupDetail> assignRole(int id, int memberId, int? customRoleId) =>
      _post(id, 'assign-role/', {
        'member_id': memberId,
        'custom_role_id': customRoleId,
      });

  Future<GroupDetail> repay(int id, int loanId, num montant) =>
      _post(id, 'loan/$loanId/repay/', {'montant': montant});

  Future<GroupDetail> setRole(int id, int memberId, String role) =>
      _post(id, 'role/', {'member_id': memberId, 'role': role});

  Future<GroupDetail> cotiserFromSavings(int id, num montant) =>
      _post(id, 'cotiser/', {'montant': montant});

  Future<GroupDetail> close(int id) => _post(id, 'close/', {});

  /// Cotisation Mobile Money → initie le paiement puis lance le checkout Tara.
  /// Si [loanId] est fourni, le versement REMBOURSE ce prêt (au lieu d'alimenter
  /// la cagnotte comme cotisation).
  Future<void> cotiserMomo({
    required int id,
    required num montant,
    required String phone,
    required String network,
    int? loanId,
  }) async {
    final dio = ref.read(apiClientProvider).dio;
    final res = await dio.post<Map<String, dynamic>>(
      '/payments/init/',
      data: {
        'type': 'tontine_groupe',
        'group_id': id,
        'montant': montant,
        'phone': phone,
        'network': network,
        if (loanId != null) 'group_loan_id': loanId,
      },
    );
    await TaraCheckoutLauncher.launchFromInitResponse(res.data);
  }
}

final groupTontinesProvider =
    AsyncNotifierProvider<GroupTontinesNotifier, List<GroupTontineSummary>>(
  GroupTontinesNotifier.new,
);
