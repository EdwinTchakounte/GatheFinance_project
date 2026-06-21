import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';

/// Adapter Dio scriptable pour les tests — chaque appel renvoie la réponse
/// stockée pour le path correspondant, sans toucher au réseau.
///
/// Usage :
/// ```dart
/// final adapter = ScriptedAdapter()
///   ..on('/auth/login/', method: 'POST', status: 200, body: {'email': '...'});
/// final dio = Dio()..httpClientAdapter = adapter;
/// ```
class ScriptedAdapter implements HttpClientAdapter {
  final List<_ScriptedCall> _calls = [];
  final List<_RecordedRequest> recorded = [];

  void on(
    String path, {
    String method = 'GET',
    int status = 200,
    Object? body,
    Map<String, List<String>>? headers,
  }) {
    _calls.add(
      _ScriptedCall(
        path: path,
        method: method.toUpperCase(),
        status: status,
        body: body,
        headers: headers,
      ),
    );
  }

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final path = options.path;
    final method = options.method.toUpperCase();
    final match = _calls.firstWhere(
      (c) => c.method == method && (path.endsWith(c.path) || c.path == path),
      orElse: () => throw StateError(
        'ScriptedAdapter: aucune réponse pour $method $path '
        '(scripts: ${_calls.map((c) => '${c.method} ${c.path}').join(', ')})',
      ),
    );

    String? bodyText;
    if (requestStream != null) {
      final chunks = <int>[];
      await for (final chunk in requestStream) {
        chunks.addAll(chunk);
      }
      bodyText = utf8.decode(chunks);
    }
    recorded.add(_RecordedRequest(
      method: method,
      path: path,
      body: bodyText,
      query: Map<String, dynamic>.from(options.queryParameters),
    ),);

    final bytes = match.body == null
        ? Uint8List(0)
        : utf8.encode(match.body is String
            ? match.body as String
            : jsonEncode(match.body),);
    return ResponseBody.fromBytes(
      bytes,
      match.status,
      headers: match.headers ??
          {
            'content-type': ['application/json'],
          },
    );
  }

  @override
  void close({bool force = false}) {}
}

class _ScriptedCall {
  _ScriptedCall({
    required this.path,
    required this.method,
    required this.status,
    required this.body,
    this.headers,
  });
  final String path;
  final String method;
  final int status;
  final Object? body;
  final Map<String, List<String>>? headers;
}

class _RecordedRequest {
  _RecordedRequest({
    required this.method,
    required this.path,
    this.body,
    this.query = const {},
  });
  final String method;
  final String path;
  final String? body;
  final Map<String, dynamic> query;
}
