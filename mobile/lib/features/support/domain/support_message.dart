/// Un message du fil de support (membre ↔ support coopérative).
class SupportMessage {
  const SupportMessage({
    required this.id,
    required this.sender,
    required this.body,
    required this.createdAt,
  });

  final int id;

  /// `'member'` (moi) ou `'staff'` (le support).
  final String sender;
  final String body;
  final DateTime createdAt;

  bool get isMine => sender == 'member';

  factory SupportMessage.fromJson(Map<String, dynamic> j) => SupportMessage(
        id: (j['id'] as num).toInt(),
        sender: j['sender'] as String? ?? 'staff',
        body: j['body'] as String? ?? '',
        createdAt:
            DateTime.tryParse(j['created_at'] as String? ?? '')?.toLocal() ??
                DateTime.now(),
      );
}
