import 'package:flutter/material.dart';

/// Avatar génératif Paysika — gradient unique dérivé du nom du membre.
///
/// Donne à chaque membre une identité chromatique personnelle (façon Notion /
/// Linear) tout en restant dans une palette cohérente avec la marque. Le
/// gradient est déterministe : le même nom produit toujours les mêmes couleurs.
///
/// L'initiale (ou les 2 premières lettres) est posée en blanc par-dessus.
class PaAvatar extends StatelessWidget {
  const PaAvatar({
    super.key,
    required this.seed,
    this.initials,
    this.size = 44,
  });

  /// Chaîne servant à dériver le gradient (typiquement le nom complet).
  final String seed;

  /// Texte affiché au centre. Si null, dérivé du [seed].
  final String? initials;

  final double size;

  /// Palette de gradients « membre » — tons riches mais accordés à la marque.
  /// Choisis pour bien contraster avec le texte blanc.
  static const _palettes = <List<Color>>[
    [Color(0xFF36C8B0), Color(0xFF1F7A8C)], // teal → petrol (brand)
    [Color(0xFF5B7CFA), Color(0xFF1A1B3D)], // periwinkle → navy
    [Color(0xFFF6A623), Color(0xFFD4711E)], // amber → terracotta
    [Color(0xFF26C281), Color(0xFF128A5B)], // emerald
    [Color(0xFFAA6CF0), Color(0xFF6B3FB0)], // violet
    [Color(0xFFEF6F8C), Color(0xFFC23E63)], // rose
    [Color(0xFF3FB8E0), Color(0xFF1E6E96)], // sky
    [Color(0xFFE0A93F), Color(0xFF96701E)], // gold
  ];

  int get _hash {
    var h = 0;
    for (final c in seed.codeUnits) {
      h = (h * 31 + c) & 0x7fffffff;
    }
    return h;
  }

  String get _initials {
    if (initials != null && initials!.isNotEmpty) return initials!;
    final parts = seed.trim().split(RegExp(r'\s+'));
    if (parts.isEmpty || parts.first.isEmpty) return '?';
    final a = parts.first[0];
    final b = parts.length > 1 && parts[1].isNotEmpty ? parts[1][0] : '';
    return (a + b).toUpperCase();
  }

  @override
  Widget build(BuildContext context) {
    final palette = _palettes[_hash % _palettes.length];
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: palette,
        ),
        boxShadow: [
          BoxShadow(
            color: palette.last.withValues(alpha: 0.30),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      alignment: Alignment.center,
      child: Text(
        _initials,
        style: TextStyle(
          color: Colors.white,
          fontSize: size * 0.38,
          fontWeight: FontWeight.w700,
          letterSpacing: 0.2,
        ),
      ),
    );
  }
}
