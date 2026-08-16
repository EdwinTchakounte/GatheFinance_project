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

/// Un « slot » par type : l'état du cycle ouvert (le cas échéant) + ma
/// participation dans ce cycle (le cas échéant).
class SpecialCollectionSlot {
  const SpecialCollectionSlot({
    required this.type,
    required this.typeDisplay,
    required this.hasOpenCycle,
    this.cycleNom = '',
    this.membership,
  });

  final String type; // caisse_scolaire | tontine_alimentaire
  final String typeDisplay;
  final bool hasOpenCycle;
  final String cycleNom;
  final SpecialCollection? membership;

  factory SpecialCollectionSlot.fromJson(Map<String, dynamic> j) {
    final cycle = j['cycle'] as Map<String, dynamic>?;
    final membership = j['membership'] as Map<String, dynamic>?;
    return SpecialCollectionSlot(
      type: j['type'] as String? ?? '',
      typeDisplay: j['type_display'] as String? ?? '',
      hasOpenCycle: cycle != null && (cycle['is_open'] as bool? ?? false),
      cycleNom: (cycle?['nom'] as String?) ?? '',
      membership:
          membership != null ? SpecialCollection.fromJson(membership) : null,
    );
  }

  Map<String, dynamic> toJson() => {
        'type': type,
        'hasOpenCycle': hasOpenCycle,
        'cycleNom': cycleNom,
        'statut': membership?.statut,
        'solde': membership?.solde,
      };
}

/// Les deux types disponibles (ordre d'affichage sur l'accueil).
const kSpecialCollectionTypes = <String, String>{
  'caisse_scolaire': 'Caisse scolaire',
  'tontine_alimentaire': 'Tontine alimentaire',
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

  /// Slot (cycle + participation) pour [type].
  SpecialCollectionSlot? slotFor(String type) {
    for (final s in state.valueOrNull ?? const <SpecialCollectionSlot>[]) {
      if (s.type == type) return s;
    }
    return null;
  }

  /// Envoie une demande de participation (dans le cycle ouvert).
  Future<void> requestParticipation({
    required String type,
    required String objectif,
    num? montantCible,
  }) async {
    final dio = ref.read(apiClientProvider).dio;
    await dio.post<Map<String, dynamic>>(
      '/special-collections/request/',
      data: {
        'type': type,
        'objectif': objectif,
        if (montantCible != null) 'montant_cible': montantCible,
      },
    );
    await refresh();
  }

  /// Transfert interne depuis l'épargne classique disponible.
  Future<void> transferFromClassic({
    required String type,
    required num montant,
  }) async {
    final dio = ref.read(apiClientProvider).dio;
    await dio.post<Map<String, dynamic>>(
      '/special-collections/transfer/',
      data: {'type': type, 'montant': montant},
    );
    await refresh();
  }

  /// Versement Mobile Money : initie le paiement puis lance le checkout Tara.
  Future<void> initVersement({
    required String type,
    required num montant,
    required String phone,
    required String network,
  }) async {
    final dio = ref.read(apiClientProvider).dio;
    final res = await dio.post<Map<String, dynamic>>(
      '/payments/init/',
      data: {
        'type': type,
        'montant': montant,
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
