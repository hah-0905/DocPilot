export function normalizeStatus(value) {
  return String(value || "").trim().toLowerCase();
}

export function resolveDocumentStatus(parseStatusValue, indexStatusValue) {
  const parseStatus = normalizeStatus(parseStatusValue);
  const indexStatus = normalizeStatus(indexStatusValue);

  if (["failed", "error"].includes(parseStatus) || ["failed", "error"].includes(indexStatus)) return "failed";
  if (parseStatus === "pending") return "pending";
  if (["processing", "parsing", "splitting", "chunking"].includes(parseStatus)) return "processing";
  const parsed = ["success", "completed", "indexed", "vectorized"].includes(parseStatus);
  if (parsed && ["not_indexed", "pending"].includes(indexStatus)) return "pending";
  if (parsed && ["indexing", "processing", "embedding", ""].includes(indexStatus)) return "indexing";
  if (parsed && ["indexed", "success", "completed", "vectorized"].includes(indexStatus)) return "completed";
  return "pending";
}

export function matchesLocalUpload(serverDocument, localUpload) {
  if (!serverDocument || !localUpload) return false;
  if (localUpload.serverDocumentId) {
    return String(serverDocument.id) === String(localUpload.serverDocumentId);
  }
  if (localUpload.isLocalUpload && !localUpload.sha256 && !localUpload.allowFallbackMatch) return false;
  if (serverDocument.name !== localUpload.name) return false;
  if (serverDocument.kbId && localUpload.kbId && String(serverDocument.kbId) !== String(localUpload.kbId)) return false;

  if (serverDocument.sha256 && localUpload.sha256) return serverDocument.sha256 === localUpload.sha256;
  if (serverDocument.size !== undefined && serverDocument.size !== null && localUpload.size !== undefined && localUpload.size !== null) {
    return Number(serverDocument.size) === Number(localUpload.size);
  }
  return true;
}

export function findUploadedDocument(uploadResult, localUpload) {
  const documents = Array.isArray(uploadResult)
    ? uploadResult
    : Array.isArray(uploadResult?.items)
      ? uploadResult.items
      : uploadResult
        ? [uploadResult]
        : [];

  return documents.find((document) => {
    const name = document.name || document.original_file_name || document.title;
    if (name !== localUpload.name) return false;
    const size = document.size_bytes ?? document.size ?? document.file_size;
    return size === undefined || size === null || Number(size) === Number(localUpload.size);
  }) || null;
}

export function normalizeDocument(document, context = {}) {
  const parseStatus = normalizeStatus(document.parse_status || document.status);
  const indexStatus = normalizeStatus(document.index_status);
  const createdAt = document.created_at || document.uploaded_at || "";
  return {
    id: String(document.id ?? ""),
    kbId: context.kbId ?? document.kb_id ?? document.kbId,
    kbName: context.kbName ?? document.kb_name ?? document.kbName,
    name: document.name || document.original_file_name || document.title || "未命名文件",
    ext: document.type || document.file_ext || document.ext || document.extension || "",
    parseStatus,
    indexStatus,
    status: resolveDocumentStatus(parseStatus, indexStatus),
    size: document.size_bytes ?? document.size ?? document.file_size,
    sha256: document.sha256 || "",
    createdAt,
    updatedAt: document.updated_at || "",
    uploadedAt: createdAt,
    chunkCount: typeof document.chunks === "number" ? document.chunks : typeof document.chunk_count === "number" ? document.chunk_count : "--",
  };
}
