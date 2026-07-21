import 'package:flutter/foundation.dart';

enum SavingsType { depot, retrait, interet }

// Types d'opération qui font SORTIR de l'argent (affichés en négatif). Reflète
// `savings.serializers._DEBIT_TYPE_OPS` côté backend, utilisé en repli si le
// champ `sens` n'est pas fourni par une ancienne API.
const _kDebitTypeOps = {
  'retrait',
  'retrait_force',
  'frais_renouvellement',
  'frais_demande_credit',
  'interets_reconduction',
  // NB : restitution_maturite = CRÉDIT (placement restitué à la part libre).
};

@immutable
class SavingsTransaction {
  const SavingsTransaction({
    required this.id,
    required this.type,
    required this.montant,
    required this.soldeApres,
    required this.date,
    this.typeOp = '',
    this.typeDisplay = '',
    this.isDebit = false,
    this.bookletId,
    this.bookletAnnee,
  });

  final int id;
  final SavingsType type;

  /// Type d'opération brut (ex. `frais_demande_credit`).
  final String typeOp;

  /// Libellé humain fourni par le backend (ex. « Frais d'étude crédit… »).
  final String typeDisplay;

  /// Sortie d'argent explicite (frais, retrait forcé…). Combiné avec le type
  /// « retrait » via [isOutflow].
  final bool isDebit;

  /// Carnet (BookletOrder) auquel l'écriture est rattachée — `null` si aucune
  /// (membre sans carnet commandé, ou écriture système). Permet le filtre
  /// « par carnet » dans « Mes écritures ».
  final int? bookletId;

  /// Année du carnet de rattachement (pour libeller « Carnet 2026 »).
  final int? bookletAnnee;
  final num montant;
  final num soldeApres;
  final DateTime date;

  /// L'opération fait-elle SORTIR de l'argent du compte ? (retrait OU débit).
  bool get isOutflow => isDebit || type == SavingsType.retrait;

  /// Montant signé : négatif pour une sortie, positif sinon.
  num get montantSigne => isOutflow ? -montant : montant;

  Map<String, Object?> toJson() => {
        'id': id,
        'type_op': typeOp.isNotEmpty ? typeOp : type.name,
        'type_display': typeDisplay,
        'sens': isOutflow ? 'debit' : 'credit',
        'montant': montant,
        'solde_apres': soldeApres,
        'date': date.toIso8601String(),
        'booklet_order': bookletId,
        'booklet_annee': bookletAnnee,
      };

  static SavingsTransaction fromJson(Map<String, dynamic> json) {
    final rawType = (json['type_op'] as String?) ?? 'depot';
    SavingsType parseType(String raw) => switch (raw) {
          'retrait' || 'retrait_force' => SavingsType.retrait,
          'interet' || 'interet_placement' || 'interet_preteur' =>
            SavingsType.interet,
          _ => SavingsType.depot,
        };
    final sens = json['sens'] as String?;
    final isDebit =
        sens != null ? sens == 'debit' : _kDebitTypeOps.contains(rawType);
    return SavingsTransaction(
      id: (json['id'] as num?)?.toInt() ?? 0,
      type: parseType(rawType),
      typeOp: rawType,
      typeDisplay: (json['type_display'] as String?) ?? '',
      isDebit: isDebit,
      bookletId: _asInt(json['booklet_order']),
      bookletAnnee: _asInt(json['booklet_annee']),
      montant: _asNum(json['montant']),
      soldeApres: _asNum(json['solde_apres']),
      date: DateTime.tryParse((json['date'] as String?) ?? '') ??
          DateTime.now(),
    );
  }
}

/// Parse un montant qu'il arrive en nombre (COERCE_DECIMAL_TO_STRING=False) ou
/// en chaîne (`DecimalField` par défaut → « 1000.00 »). Défaut 0.
num _asNum(Object? v) {
  if (v is num) return v;
  if (v is String) return num.tryParse(v) ?? 0;
  return 0;
}

/// Idem pour un entier optionnel (id/année de carnet) — `null` si absent.
int? _asInt(Object? v) {
  if (v is num) return v.toInt();
  if (v is String) return int.tryParse(v);
  return null;
}
