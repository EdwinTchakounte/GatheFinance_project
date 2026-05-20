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
  });

  final int id;
  final String numeroMembre;
  final String prenom;
  final String nom;
  final String email;
  final String phone;
  final MemberStatus statut;
  final DateTime dateAdhesion;

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
    );
  }
}

enum MemberStatus { actif, suspendu, radie }
