import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../app/theme/paysika/pa_colors.dart';
import '../../core/di/providers.dart';

/// Info de mise à jour : version installée vs version minimale requise (serveur).
class UpdateInfo {
  const UpdateInfo({
    required this.updateRequired,
    required this.downloadUrl,
    required this.message,
    required this.latest,
    required this.current,
  });

  final bool updateRequired; // version installée < min_version serveur
  final String downloadUrl;
  final String message;
  final String latest;
  final String current;
}

/// Compare deux versions "x.y.z" (le suffixe build `+N` est ignoré).
/// Renvoie < 0 si a < b, 0 si égal, > 0 si a > b.
int compareVersions(String a, String b) {
  List<int> parts(String v) => v
      .split('+')
      .first
      .split('.')
      .map((x) => int.tryParse(x.trim()) ?? 0)
      .toList();
  final pa = parts(a);
  final pb = parts(b);
  for (var i = 0; i < 3; i++) {
    final x = i < pa.length ? pa[i] : 0;
    final y = i < pb.length ? pb[i] : 0;
    if (x != y) return x < y ? -1 : 1;
  }
  return 0;
}

/// Récupère la version minimale requise (serveur) et la compare à la version
/// installée. En cas d'erreur réseau → renvoie ``null`` (fail-open : on ne
/// bloque JAMAIS un membre pour un simple souci de connexion).
final updateInfoProvider = FutureProvider<UpdateInfo?>((ref) async {
  try {
    final dio = ref.read(apiClientProvider).dio;
    final res = await dio.get<Map<String, dynamic>>('/app-version/');
    final data = res.data ?? const <String, dynamic>{};
    final info = await PackageInfo.fromPlatform();
    final minVersion = (data['min_version'] as String?) ?? '0.0.0';
    final current = info.version;
    return UpdateInfo(
      updateRequired: compareVersions(current, minVersion) < 0,
      downloadUrl: (data['android_download_url'] as String?) ?? '',
      message: (data['update_message'] as String?) ??
          'Une nouvelle version est disponible. Merci de mettre à jour.',
      latest: (data['latest_version'] as String?) ?? '',
      current: current,
    );
  } catch (_) {
    return null;
  }
});

/// Enveloppe l'app : si la version installée est en-dessous du minimum requis,
/// affiche un écran BLOQUANT (pas d'accès à l'app) avec un bouton « Mettre à
/// jour ». Sinon, laisse passer l'app normalement.
class UpdateGate extends ConsumerWidget {
  const UpdateGate({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final info = ref.watch(updateInfoProvider).valueOrNull;
    if (info != null && info.updateRequired) {
      return _ForcedUpdateScreen(info: info);
    }
    return child;
  }
}

class _ForcedUpdateScreen extends StatelessWidget {
  const _ForcedUpdateScreen({required this.info});

  final UpdateInfo info;

  Future<void> _openUpdate() async {
    final uri = Uri.tryParse(info.downloadUrl);
    if (uri != null) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }

  @override
  Widget build(BuildContext context) {
    // Blocage total : le retour système ne ferme rien (pas d'accès à l'app).
    return PopScope(
      canPop: false,
      child: Scaffold(
        backgroundColor: PaColors.canvas,
        body: SafeArea(
          child: Center(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 28),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    width: 76,
                    height: 76,
                    decoration: BoxDecoration(
                      color: PaColors.tealSurface,
                      borderRadius: BorderRadius.circular(22),
                    ),
                    child: const Icon(
                      Icons.system_update_alt_rounded,
                      color: PaColors.teal,
                      size: 38,
                    ),
                  ),
                  const SizedBox(height: 22),
                  const Text(
                    'Mise à jour requise',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: PaColors.inkPrimary,
                      fontSize: 21,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 10),
                  Text(
                    info.message,
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      color: PaColors.inkSecondary,
                      fontSize: 14.5,
                      height: 1.4,
                    ),
                  ),
                  if (info.latest.isNotEmpty) ...[
                    const SizedBox(height: 14),
                    Text(
                      'Version installée ${info.current} · dernière ${info.latest}',
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        color: PaColors.inkMuted,
                        fontSize: 12,
                      ),
                    ),
                  ],
                  const SizedBox(height: 28),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton.icon(
                      onPressed: info.downloadUrl.isEmpty ? null : _openUpdate,
                      style: FilledButton.styleFrom(
                        backgroundColor: PaColors.teal,
                        padding: const EdgeInsets.symmetric(vertical: 15),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(14),
                        ),
                      ),
                      icon: const Icon(Icons.download_rounded, size: 20),
                      label: const Text(
                        'Mettre à jour',
                        style: TextStyle(
                          fontSize: 15.5,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
