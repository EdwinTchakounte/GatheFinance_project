import 'package:flutter/foundation.dart';

/// Un versement (paiement) du membre, tel que remonté par `GET /payments/me/`
/// (miroir de `PaymentReadSerializer`). Sert de source au **reçu de versement**
/// téléchargeable : chaque versement validé peut générer une mini-facture.
@immutable
class PaymentReceipt {
  const PaymentReceipt({
    required this.id,
    required this.type,
    required this.typeDisplay,
    required this.montant,
    required this.fraisTransaction,
    required this.statut,
    required this.statutDisplay,
    required this.date,
    this.dateValidation,
    this.reference,
    this.nbJoursCouverts = 1,
    this.isPlacement = false,
  });

  final int id;

  /// Type brut backend (`epargne`, `epargne_classique`, `remboursement`,
  /// `frais_carnet`, …).
  final String type;
  final String typeDisplay;
  final num montant;
  final num fraisTransaction;
  final String statut; // valide / en_attente / rejete …
  final String statutDisplay;
  final DateTime date;
  final DateTime? dateValidation;
  final String? reference;
  final int nbJoursCouverts;
  final bool isPlacement;

  bool get isValidated => statut == 'valide';

  /// Montant réellement débité = versement + frais de transaction éventuels.
  num get totalDebite => montant + fraisTransaction;

  static PaymentReceipt fromJson(Map<String, dynamic> json) {
    return PaymentReceipt(
      id: (json['id'] as num?)?.toInt() ?? 0,
      type: (json['type'] as String?) ?? '',
      typeDisplay: (json['type_display'] as String?) ?? '',
      montant: _num(json['montant']),
      fraisTransaction: _num(json['frais_transaction']),
      statut: (json['statut'] as String?) ?? 'en_attente',
      statutDisplay: (json['statut_display'] as String?) ?? '',
      date: _date(json['date_versement'] ?? json['created_at']),
      dateValidation: _dateOrNull(json['date_validation']),
      reference: (json['reference_externe'] as String?)?.trim(),
      nbJoursCouverts: (json['nb_jours_couverts'] as num?)?.toInt() ?? 1,
      isPlacement: (json['is_placement'] as bool?) ?? false,
    );
  }
}

num _num(dynamic v) {
  if (v is num) return v;
  if (v is String) return num.tryParse(v) ?? 0;
  return 0;
}

DateTime _date(dynamic v) {
  if (v is String && v.isNotEmpty) {
    return DateTime.tryParse(v) ?? DateTime.now();
  }
  return DateTime.now();
}

DateTime? _dateOrNull(dynamic v) {
  if (v is String && v.isNotEmpty) return DateTime.tryParse(v);
  return null;
}
