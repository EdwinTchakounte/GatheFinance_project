import 'package:flutter/foundation.dart';

/// Annonce broadcast diffusée par la coopérative (lecture membre).
@immutable
class Announcement {
  const Announcement({
    required this.id,
    required this.titre,
    required this.corps,
    required this.publishedAt,
    this.imageUrl,
    this.lien,
  });

  final int id;
  final String titre;
  final String corps;
  final DateTime? publishedAt;

  /// URL absolue de la pièce jointe image (ou null).
  final String? imageUrl;

  /// Lien interne optionnel associé à l'annonce.
  final String? lien;

  bool get hasImage => imageUrl != null && imageUrl!.isNotEmpty;

  factory Announcement.fromJson(Map<String, dynamic> json) {
    DateTime? parsedDate;
    final raw = json['published_at'];
    if (raw is String && raw.isNotEmpty) {
      parsedDate = DateTime.tryParse(raw)?.toLocal();
    }
    return Announcement(
      id: (json['id'] as num?)?.toInt() ?? 0,
      titre: (json['titre'] as String?)?.trim() ?? '',
      corps: (json['corps'] as String?)?.trim() ?? '',
      publishedAt: parsedDate,
      imageUrl: json['image_url'] as String?,
      lien: json['lien'] as String?,
    );
  }
}
