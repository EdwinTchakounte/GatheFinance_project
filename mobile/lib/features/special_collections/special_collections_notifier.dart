import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/di/providers.dart';
import '../../core/services/tara_checkout_launcher.dart';

/// Collecte particulière (caisse scolaire / tontine alimentaire) côté membre.
///
/// Chaque membre a au plus une participation par type. Le versement et le
/// transfert ne sont possibles qu'une fois la participation VALIDÉE par la
/// coopérative (statut `valide`).
class SpecialCollection {
  const SpecialCollection({
    required this.type,
    required this.typeDisplay,
    required this.statut,
    required this.statutDisplay,
    required this.isActive,
    required this.solde,
    required this.objectif,
    this.montantCible,
    this.motifRejet = '',
  });

  final String type; // caisse_scolaire | tontine_alimentaire
  final String typeDisplay;
  final String statut; // en_attente | valide | rejete | suspendu
  final String statutDisplay;
  final bool isActive;
  final num solde;
  final String objectif;
  final num? montantCible;
  final String motifRejet;

  factory SpecialCollection.fromJson(Map<String, dynamic> j) =>
      SpecialCollection(
        type: j['type'] as String? ?? '',
        typeDisplay: j['type_display'] as String? ?? '',
        statut: j['statut'] as String? ?? 'en_attente',
        statutDisplay: j['statut_display'] as String? ?? '',
        isActive: j['is_active'] as bool? ?? false,
        solde: (j['solde'] as num?) ?? num.tryParse('${j['solde']}') ?? 0,
        objectif: j['objectif'] as String? ?? '',
        montantCible: j['montant_cible'] == null
            ? null
            : (j['montant_cible'] as num?) ??
                num.tryParse('${j['montant_cible']}'),
        motifRejet: j['motif_rejet'] as String? ?? '',
      );

  Map<String, dynamic> toJson() => {
        'type': type,
        'statut': statut,
        'is_active': isActive,
        'solde': solde,
        'objectif': objectif,
        'montant_cible': montantCible,
        'motif_rejet': motifRejet,
      };
}

/// Les deux types disponibles (ordre d'affichage sur l'accueil).
const kSpecialCollectionTypes = <String, String>{
  'caisse_scolaire': 'Caisse scolaire',
  'tontine_alimentaire': 'Tontine alimentaire',
};

class SpecialCollectionsNotifier
    extends AsyncNotifier<List<SpecialCollection>> {
  Future<List<SpecialCollection>> _fetch() async {
    final dio = ref.read(apiClientProvider).dio;
    final res = await dio.get<List<dynamic>>('/special-collections/');
    return (res.data ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(SpecialCollection.fromJson)
        .toList();
  }

  @override
  Future<List<SpecialCollection>> build() => _fetch();

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(_fetch);
  }

  /// Participation existante pour [type], ou `null` si le membre n'a rien demandé.
  SpecialCollection? byType(String type) {
    for (final c in state.valueOrNull ?? const <SpecialCollection>[]) {
      if (c.type == type) return c;
    }
    return null;
  }

  /// Envoie une demande de participation (petit formulaire).
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
  /// Le solde se met à jour au retour dans l'app (poll/refresh).
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

final specialCollectionsProvider =
    AsyncNotifierProvider<SpecialCollectionsNotifier, List<SpecialCollection>>(
  SpecialCollectionsNotifier.new,
);
