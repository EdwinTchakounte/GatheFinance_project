import 'package:flutter/foundation.dart';

import '../../../../core/usecases/usecase.dart';
import '../repositories/loans_repository.dart';

@immutable
class UploadLoanRequestAttachmentParams {
  const UploadLoanRequestAttachmentParams({
    required this.loanRequestId,
    required this.schemaFieldId,
    required this.filePath,
    required this.fileName,
  });

  final int loanRequestId;
  final String schemaFieldId;
  final String filePath;
  final String fileName;
}

/// CH-5 — Upload multipart d'une pièce jointe sur un LoanRequest existant.
/// Idempotent côté backend par `schema_field_id` (re-upload remplace).
class UploadLoanRequestAttachment
    extends UseCase<void, UploadLoanRequestAttachmentParams> {
  const UploadLoanRequestAttachment(this._repo);
  final LoansRepository _repo;

  @override
  Future<void> call(UploadLoanRequestAttachmentParams params) =>
      _repo.uploadLoanRequestAttachment(
        loanRequestId: params.loanRequestId,
        schemaFieldId: params.schemaFieldId,
        filePath: params.filePath,
        fileName: params.fileName,
      );
}
