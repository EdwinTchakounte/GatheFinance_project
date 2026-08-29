import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/di/providers.dart';
import '../../core/services/tara_checkout_launcher.dart';

/// Participation d'un membre à une collecte particulière, DANS un cycle donné.
class SpecialCollection {
  const SpecialCollection({
    required this.statut,
    required this.statutDisplay,
    required this.isActive,
    required this.solde,
    required this.objectif,
    this.montantCible,
    this.motifRejet = '',
  });

  final String statut; // en_attente | valide | rejete | suspendu
  final String statutDisplay;
  final bool isActive;
  final num solde;
  final String objectif;
  final num? montantCible;
  final String motifRejet;

  factory SpecialCollection.fromJson(Map<String, dynamic> j) =>
      SpecialCollection(
        statut: j['statut'] as String? ?? 'en_attente',
        statutDisplay: j['statut_display'] as String? ?? '',
        isActive: j['is_active'] as bool? ?? false,
        // DRF sérialise les DecimalField en STRING ("0.00") : un cast `as num?`
        // planterait (« String is not a subtype of type num? »). On parse.
        solde: _asNum(j['solde']) ?? 0,
        objectif: j['objectif'] as String? ?? '',
        montantCible: _asNum(j['montant_cible']),
        motifRejet: j['motif_rejet'] as String? ?? '',
      );
}

/// Convertit une valeur JSON (num OU String OU null) en `num?` sans jamais
/// lever — DRF renvoie les montants décimaux sous forme de chaîne.
num? _asNum(dynamic v) {
  if (v == null) return null;
  if (v is num) return v;
  return num.tryParse(v.toString());
}

/// Infos d'une collecte ouverte (cycle).
class SpecialCollectionCycleInfo {
  const SpecialCollectionCycleInfo({
    required this.id,
    required this.nom,
    this.description = '',
    this.montantMinimal = 0,
    this.isOpen = true,
  });

  final int id;
  final String nom;
  final String description;
  final num montantMinimal;
  final bool isOpen;

  factory SpecialCollectionCycleInfo.fromJson(Map<String, dynamic> j) =>
      SpecialCollectionCycleInfo(
        id: (j['id'] as num?)?.toInt() ?? 0,
        nom: j['nom'] as String? ?? '',
        description: j['description'] as String? ?? '',
        montantMinimal: _asNum(j['montant_minimal']) ?? 0,
        isOpen: j['is_open'] as bool? ?? false,
      );
}

/// Une collecte ouverte + ma participation dedans.
class SpecialCollectionOpen {
  const SpecialCollectionOpen({required this.cycle, this.membership});

  final SpecialCollectionCycleInfo cycle;
  final SpecialCollection? membership;

  factory SpecialCollectionOpen.fromJson(Map<String, dynamic> j) {
    final cycle = j['cycle'] as Map<String, dynamic>? ?? const {};
    final membership = j['membership'] as Map<String, dynamic>?;
    return SpecialCollectionOpen(
      cycle: SpecialCollectionCycleInfo.fromJson(cycle),
      membership:
          membership != null ? SpecialCollection.fromJson(membership) : null,
    );
  }
}

/// Un « slot » par type : le carnet acheté ? + la liste des collectes ouvertes
/// (plusieurs possibles) avec ma participation dans chacune.
class SpecialCollectionSlot {
  const SpecialCollectionSlot({
    required this.type,
    required this.typeDisplay,
    required this.hasCarnet,
    this.cycles = const [],
  });

  final String type; // caisse_scolaire | tontine_alimentaire
  final String typeDisplay;
  final bool hasCarnet;
  final List<SpecialCollectionOpen> cycles;

  bool get hasOpenCycle => cycles.isNotEmpty;

  factory SpecialCollectionSlot.fromJson(Map<String, dynamic> j) {
    final list = (j['cycles'] as List<dynamic>? ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(SpecialCollectionOpen.fromJson)
        .toList();
    return SpecialCollectionSlot(
      type: j['type'] as String? ?? '',
      typeDisplay: j['type_display'] as String? ?? '',
      hasCarnet: j['has_carnet'] as bool? ?? false,
      cycles: list,
    );
  }

  Map<String, dynamic> toJson() => {
        'type': type,
        'hasCarnet': hasCarnet,
        // Inclut l'état de CHAQUE collecte (id/statut/solde) pour que le
        // polling détecte tout changement de solde ou de statut.
        'cycles': cycles
            .map(
              (o) => {
                'id': o.cycle.id,
                'statut': o.membership?.statut,
                'solde': o.membership?.solde,
              },
            )
            .toList(),
      };
}

/// Type de collecte → type de paiement du carnet dédié (payant, prérequis).
const kCarnetPaymentType = <String, String>{
  'tontine_alimentaire': 'frais_carnet_tontine',
  'caisse_scolaire': 'frais_carnet_caisse',
};

/// Les deux types disponibles (ordre d'affichage sur l'accueil).
const kSpecialCollectionTypes = <String, String>{
  'caisse_scolaire': 'Caisse scolaire',
  'tontine_alimentaire': 'Tontine',
};

class SpecialCollectionsNotifier
    extends AsyncNotifier<List<SpecialCollectionSlot>> {
  Future<List<SpecialCollectionSlot>> _fetch() async {
    final dio = ref.read(apiClientProvider).dio;
    final res = await dio.get<List<dynamic>>('/special-collections/');
    return (res.data ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(SpecialCollectionSlot.fromJson)
        .toList();
  }

  @override
  Future<List<SpecialCollectionSlot>> build() => _fetch();

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(_fetch);
  }

  /// Slot pour [type].
  SpecialCollectionSlot? slotFor(String type) {
    for (final s in state.valueOrNull ?? const <SpecialCollectionSlot>[]) {
      if (s.type == type) return s;
    }
    return null;
  }

  /// Envoie une demande de participation à une collecte ouverte précise.
  Future<void> requestParticipation({
    required String type,
    required int cycleId,
    required String objectif,
    num? montantCible,
  }) async {
    final dio = ref.read(apiClientProvider).dio;
    await dio.post<Map<String, dynamic>>(
      '/special-collections/request/',
      data: {
        'type': type,
        'cycle_id': cycleId,
        'objectif': objectif,
        if (montantCible != null) 'montant_cible': montantCible,
      },
    );
    await refresh();
  }

  /// Transfert interne depuis l'épargne classique disponible (collecte précise).
  Future<void> transferFromClassic({
    required String type,
    required int cycleId,
    required num montant,
  }) async {
    final dio = ref.read(apiClientProvider).dio;
    await dio.post<Map<String, dynamic>>(
      '/special-collections/transfer/',
      data: {'type': type, 'cycle_id': cycleId, 'montant': montant},
    );
    await refresh();
  }

  /// Versement Mobile Money vers une collecte précise : initie + checkout Tara.
  Future<void> initVersement({
    required String type,
    required int cycleId,
    required num montant,
    required String phone,
    required String network,
  }) async {
    final dio = ref.read(apiClientProvider).dio;
    final res = await dio.post<Map<String, dynamic>>(
      '/payments/init/',
      data: {
        'type': type,
        'cycle_id': cycleId,
        'montant': montant,
        'phone': phone,
        'network': network,
      },
    );
    await TaraCheckoutLauncher.launchFromInitResponse(res.data);
  }

  /// Achat du carnet dédié (tontine/caisse) : prérequis pour verser. Montant
  /// omis → tarif officiel imposé par le serveur (FeeType).
  Future<void> buyCarnet({
    required String type,
    required String phone,
    required String network,
  }) async {
    final carnetType = kCarnetPaymentType[type];
    if (carnetType == null) return;
    final dio = ref.read(apiClientProvider).dio;
    final res = await dio.post<Map<String, dynamic>>(
      '/payments/init/',
      data: {
        'type': carnetType,
        'phone': phone,
        'network': network,
      },
    );
    await TaraCheckoutLauncher.launchFromInitResponse(res.data);
  }
}

final specialCollectionsProvider = AsyncNotifierProvider<
    SpecialCollectionsNotifier, List<SpecialCollectionSlot>>(
  SpecialCollectionsNotifier.new,
);
