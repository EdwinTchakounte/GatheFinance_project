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
              background: a.heroImageUrl == null
                  ? const _CoverPlaceholder()
                  : Stack(
                      fit: StackFit.expand,
                      children: [
                        CachedNetworkImage(
                          imageUrl: a.heroImageUrl!,
                          fit: BoxFit.cover,
                          placeholder: (_, __) => const _CoverPlaceholder(),
                          errorWidget: (_, __, ___) =>
                              const _CoverPlaceholder(),
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

class _CoverPlaceholder extends StatelessWidget {
  const _CoverPlaceholder();

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFFFDF2E2), Color(0xFFFAE6CB)],
        ),
      ),
      alignment: Alignment.center,
      child: const Icon(
        Icons.article_outlined,
        color: PaColors.warning,
        size: 64,
      ),
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
