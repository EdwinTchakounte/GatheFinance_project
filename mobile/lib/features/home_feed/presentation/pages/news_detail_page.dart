import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../../../app/theme/paysika/pa_colors.dart';
import '../../../../core/di/providers.dart';
import '../../../../core/network/api_config.dart';
import '../../../social/domain/entities/reaction.dart';
import '../../../social/presentation/widgets/comments_section.dart';
import '../../../social/presentation/widgets/like_button.dart';
import '../../domain/entities/feed_item.dart';

/// Page détail d'une actualité — design éditorial épuré.
/// Reçoit l'`NewsArticle` en `extra` du go_router (chargement instantané)
/// puis fetche le `body` complet en arrière-plan via l'API Wagtail si
/// disponible. Si le fetch échoue ou le body est vide, on retombe sur
/// `excerpt` qui est toujours présent.
class NewsDetailPage extends ConsumerStatefulWidget {
  const NewsDetailPage({super.key, required this.article});

  final NewsArticle article;

  @override
  ConsumerState<NewsDetailPage> createState() => _NewsDetailPageState();
}

class _NewsDetailPageState extends ConsumerState<NewsDetailPage> {
  String? _body;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _fetchBody();
  }

  Future<void> _fetchBody() async {
    try {
      final dio = ref.read(apiClientProvider).dio;
      // Wagtail API v2 — URL absolue car le baseUrl Dio est sur /api/v1.
      final res = await dio.get<Map<String, dynamic>>(
        '${ApiConfig.baseUrl}/api/v2/pages/${widget.article.id}/',
        queryParameters: const {'fields': 'body,excerpt'},
      );
      final body = _extractPlainText(res.data?['body']);
      if (!mounted) return;
      setState(() {
        _body = body;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loading = false; // fallback silencieux sur l'excerpt
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final a = widget.article;
    final dt = DateFormat('dd MMMM yyyy', 'fr_FR');
    final body = (_body ?? '').trim();
    return Scaffold(
      backgroundColor: PaColors.canvas,
      body: CustomScrollView(
        slivers: [
          SliverAppBar(
            expandedHeight: 240,
            pinned: true,
            backgroundColor: PaColors.canvas,
            surfaceTintColor: PaColors.canvas,
            // Back button noir lisible sur fond crème ET sur la hero image
            // (un petit halo blanc semi-transparent contraste l'icône).
            leading: Padding(
              padding: const EdgeInsets.all(8),
              child: Material(
                color: Colors.white.withValues(alpha: 0.88),
                shape: const CircleBorder(),
                child: InkWell(
                  customBorder: const CircleBorder(),
                  onTap: () => Navigator.of(context).maybePop(),
                  child: const Padding(
                    padding: EdgeInsets.all(8),
                    child: Icon(
                      Icons.arrow_back_rounded,
                      color: PaColors.inkPrimary,
                      size: 20,
                    ),
                  ),
                ),
              ),
            ),
            iconTheme: const IconThemeData(color: PaColors.inkPrimary),
            flexibleSpace: FlexibleSpaceBar(
              background: Stack(
                      fit: StackFit.expand,
                      children: [
                        CachedNetworkImage(
                          imageUrl: a.heroImageUrl ?? '',
                          fit: BoxFit.cover,
                          placeholder: (_, __) => _CoverPlaceholder(title: a.title),
                          errorWidget: (_, __, ___) =>
                              _CoverPlaceholder(title: a.title),
                        ),
                        const DecoratedBox(
                          decoration: BoxDecoration(
                            gradient: LinearGradient(
                              begin: Alignment.topCenter,
                              end: Alignment.bottomCenter,
                              colors: [
                                Color(0x33000000),
                                Color(0x00000000),
                              ],
                            ),
                          ),
                        ),
                      ],
                    ),
            ),
          ),
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 24, 20, 40),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    dt.format(a.publishedAt).toUpperCase(),
                    style: const TextStyle(
                      color: PaColors.warning,
                      fontSize: 11,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 1.6,
                    ),
                  ),
                  const SizedBox(height: 10),
                  Text(
                    a.title,
                    style: const TextStyle(
                      color: PaColors.inkPrimary,
                      fontSize: 24,
                      fontWeight: FontWeight.w800,
                      height: 1.2,
                      letterSpacing: -0.3,
                    ),
                  ),
                  const SizedBox(height: 18),
                  if (a.excerpt.isNotEmpty)
                    Text(
                      _stripHtml(a.excerpt),
                      style: const TextStyle(
                        color: PaColors.inkSecondary,
                        fontSize: 16,
                        height: 1.5,
                        fontStyle: FontStyle.italic,
                      ),
                    ),
                  if (body.isNotEmpty) ...[
                    const SizedBox(height: 18),
                    Container(
                      height: 1,
                      width: 48,
                      color: PaColors.teal,
                    ),
                    const SizedBox(height: 18),
                    Text(
                      body,
                      style: const TextStyle(
                        color: PaColors.inkPrimary,
                        fontSize: 15,
                        height: 1.65,
                      ),
                    ),
                  ] else if (_loading) ...[
                    const SizedBox(height: 24),
                    const Center(
                      child: SizedBox(
                        width: 22,
                        height: 22,
                        child: CircularProgressIndicator(
                          strokeWidth: 2.4,
                          color: PaColors.teal,
                        ),
                      ),
                    ),
                  ],
                  // --- Interactions sociales (like + commentaires) -------
                  const SizedBox(height: 28),
                  const Divider(color: PaColors.line, height: 1),
                  const SizedBox(height: 16),
                  LikeButton(
                    target: SocialTarget(
                      kind: SocialTargetKind.article,
                      id: a.id,
                    ),
                  ),
                  const SizedBox(height: 18),
                  CommentsSection(
                    target: SocialTarget(
                      kind: SocialTargetKind.article,
                      id: a.id,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Cover par défaut quand un article n'a pas de hero image — visuel
/// éditorial soft avec gradient (déterministe par hash du titre), halos
/// lumineux + icône thématique + filigrane brand. Donne une présence
/// visuelle plutôt qu'un placeholder gris terne.
class _CoverPlaceholder extends StatelessWidget {
  const _CoverPlaceholder({this.title = ''});
  final String title;

  static const _gradients = <List<Color>>[
    [Color(0xFF1E3A8A), Color(0xFF0EA5E9)], // bleu nuit -> azur
    [Color(0xFF065F46), Color(0xFF10B981)], // forêt -> émeraude
    [Color(0xFF7C3AED), Color(0xFFEC4899)], // violet -> rose
    [Color(0xFFB45309), Color(0xFFF59E0B)], // ambre -> doré
    [Color(0xFF0F766E), Color(0xFF14B8A6)], // teal foncé -> teal clair
    [Color(0xFF1E40AF), Color(0xFF8B5CF6)], // marine -> violet
  ];

  static const _icons = <IconData>[
    Icons.trending_up_rounded,
    Icons.savings_outlined,
    Icons.school_outlined,
    Icons.handshake_outlined,
    Icons.lightbulb_outline_rounded,
    Icons.local_florist_outlined,
  ];

  int get _slot {
    var h = 0;
    for (final c in title.runes) {
      h = (h * 31 + c) & 0x7fffffff;
    }
    return h % _gradients.length;
  }

  @override
  Widget build(BuildContext context) {
    final palette = _gradients[_slot];
    final icon = _icons[_slot];
    return Stack(
      fit: StackFit.expand,
      children: [
        Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: palette,
            ),
          ),
        ),
        Positioned(
          top: -90,
          right: -70,
          child: IgnorePointer(
            child: Container(
              width: 280,
              height: 280,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: RadialGradient(
                  colors: [
                    Colors.white.withValues(alpha: 0.22),
                    Colors.white.withValues(alpha: 0),
                  ],
                ),
              ),
            ),
          ),
        ),
        Positioned(
          bottom: -60,
          left: -40,
          child: IgnorePointer(
            child: Container(
              width: 200,
              height: 200,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: RadialGradient(
                  colors: [
                    Colors.white.withValues(alpha: 0.10),
                    Colors.white.withValues(alpha: 0),
                  ],
                ),
              ),
            ),
          ),
        ),
        Center(
          child: Container(
            width: 96,
            height: 96,
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.16),
              shape: BoxShape.circle,
              border: Border.all(
                color: Colors.white.withValues(alpha: 0.3),
                width: 1.5,
              ),
            ),
            alignment: Alignment.center,
            child: Icon(icon, color: Colors.white, size: 44),
          ),
        ),
        Positioned(
          bottom: 18,
          right: 22,
          child: IgnorePointer(
            child: Opacity(
              opacity: 0.32,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  border: Border.all(
                    color: Colors.white.withValues(alpha: 0.7),
                    width: 1.2,
                  ),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Text(
                  'GATHÉ',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 9.5,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 2.0,
                  ),
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }
}

/// Strip basique des tags HTML — Wagtail RichTextField renvoie du HTML
/// comme `<p>Texte</p>`. Pas besoin d'un parser DOM complet ici.
String _stripHtml(String html) {
  if (html.isEmpty) return '';
  final noTags = html.replaceAll(RegExp(r'<[^>]*>'), '');
  return noTags
      .replaceAll('&nbsp;', ' ')
      .replaceAll('&amp;', '&')
      .replaceAll('&quot;', '"')
      .replaceAll('&#39;', "'")
      .replaceAll('&lt;', '<')
      .replaceAll('&gt;', '>')
      .trim();
}

/// Extrait le texte plat de la `body` StreamField Wagtail (liste de blocks).
/// Chaque block est `{ "type": "...", "value": ... }`. On garde uniquement
/// les blocs textuels — `paragraph`, `heading`, `quote` — et on strippe le
/// HTML que retourne RichTextField.
String _extractPlainText(dynamic body) {
  if (body is! List) return '';
  final buf = StringBuffer();
  for (final block in body) {
    if (block is! Map) continue;
    final type = block['type'] as String?;
    final value = block['value'];
    switch (type) {
      case 'heading':
        if (value is String) {
          buf.writeln();
          buf.writeln(_stripHtml(value).toUpperCase());
          buf.writeln();
        }
        break;
      case 'paragraph':
      case 'quote':
        if (value is String) {
          buf.writeln(_stripHtml(value));
          buf.writeln();
        }
        break;
      default:
        // Ignore image, gallery, embed pour le moment — pas de renderer.
        break;
    }
  }
  return buf.toString().trim();
}
