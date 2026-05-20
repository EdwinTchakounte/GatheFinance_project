/// Exceptions techniques levées par la couche `data` (datasources).
/// Sont traduites en `Failure` par les repository implementations.
class ServerException implements Exception {
  const ServerException([this.message = 'Server error', this.statusCode]);
  final String message;
  final int? statusCode;

  @override
  String toString() => 'ServerException($statusCode): $message';
}

class NetworkException implements Exception {
  const NetworkException([this.message = 'Network error']);
  final String message;

  @override
  String toString() => 'NetworkException: $message';
}

class CacheException implements Exception {
  const CacheException([this.message = 'Cache error']);
  final String message;

  @override
  String toString() => 'CacheException: $message';
}

/// Levée par les mock data sources pour simuler des erreurs serveur attendues.
class CredentialsException implements Exception {
  const CredentialsException([this.message = 'Identifiants invalides']);
  final String message;

  @override
  String toString() => message;
}
