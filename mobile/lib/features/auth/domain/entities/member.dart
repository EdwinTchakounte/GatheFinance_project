import 'package:flutter/foundation.dart';

/// Membre — entité métier pure. Aucune dépendance framework/data.
@immutable
class Member {
  const Member({
    required this.id,
    required this.numeroMembre,
    required this.prenom,
    required this.nom,
    required this.email,
    required this.phone,
    required this.statut,
    required this.dateAdhesion,
    this.photoUrl,
  });

  final int id;
  final String numeroMembre;
  final String prenom;
  final String nom;
  final String email;
  final String phone;
  final MemberStatus statut;
  final DateTime dateAdhesion;

  /// URL absolue de la photo de profil (avatar), `null` si non définie.
  final String? photoUrl;

  String get fullName => '$prenom $nom';

  Member copyWith({
    int? id,
    String? numeroMembre,
    String? prenom,
    String? nom,
    String? email,
    String? phone,
    MemberStatus? statut,
    DateTime? dateAdhesion,
    String? photoUrl,
  }) {
    return Member(
      id: id ?? this.id,
      numeroMembre: numeroMembre ?? this.numeroMembre,
      prenom: prenom ?? this.prenom,
      nom: nom ?? this.nom,
      email: email ?? this.email,
      phone: phone ?? this.phone,
      statut: statut ?? this.statut,
      dateAdhesion: dateAdhesion ?? this.dateAdhesion,
      photoUrl: photoUrl ?? this.photoUrl,
    );
  }
}

/// Statut métier d'un membre, aligné sur `apps_coop.members.models.Member.Statut`.
///
/// - [actif] : membre confirmé, accès complet.
/// - [suspendu] : sanction administrative (ex. retards graves).
/// - [radie] : exclusion définitive de la coopérative.
/// - [temporaire] : bénéficiaire micro-crédit campagne (LOT 11) — accès au
///   crédit campagne uniquement, peut basculer [actif] après paiement des
///   frais d'inscription (CH-2).
enum MemberStatus { actif, suspendu, radie, temporaire }
