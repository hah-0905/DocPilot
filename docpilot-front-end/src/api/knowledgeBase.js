import { getStoredAuth } from "./auth";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

function getAuthHeaders() {
  const auth = getStoredAuth();
  if (!auth?.token) throw new Error("未登录");
  return {
    Authorization: `Bearer ${auth.token}`,
    "Content-Type": "application/json",
  };
}

async function request(path, options = {}) {
  const headers = { ...getAuthHeaders(), ...(options.headers || {}) };
  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    if (response.status === 401 || response.status === 403) {
      const err = new Error(payload?.detail || "登录已失效，请重新登录");
      err.code = response.status;
      throw err;
    }
    throw new Error(
      typeof payload.detail === "string"
        ? payload.detail
        : payload?.message || `请求失败（${response.status}）`
    );
  }

  if (payload?.code !== undefined && payload.code !== 200) {
    throw new Error(payload.message || "请求失败");
  }

  return payload?.data ?? payload;
}

export async function getKnowledgeBases() {
  return request("/api/kb/knowledge-bases");
}

export async function getKnowledgeBase(id) {
  return request(`/api/kb/knowledge-bases/${id}`);
}

export async function createKnowledgeBase(data) {
  return request("/api/kb/knowledge-bases", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function deleteKnowledgeBase(id) {
  return request(`/api/kb/knowledge-bases/${id}`, { method: "DELETE" });
}

export async function updateKnowledgeBase(id, data) {
  return request(`/api/kb/knowledge-bases/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function uploadKnowledgeBaseFile(kbId, files) {
  const fileArray = Array.isArray(files) ? files : [files];
  if (fileArray.length === 0) throw new Error("请选择文件");

  const auth = getStoredAuth();
  if (!auth?.token) throw new Error("未登录");

  const formData = new FormData();
  for (const file of fileArray) {
    formData.append("files", file);
  }

  const response = await fetch(`${API_BASE_URL}/api/kb/knowledge-bases/${kbId}/documents/upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${auth.token}` },
    body: formData,
  });

  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    if (response.status === 401 || response.status === 403) {
      const err = new Error(payload?.detail || "登录已失效，请重新登录");
      err.code = response.status;
      throw err;
    }
    throw new Error(
      typeof payload.detail === "string"
        ? payload.detail
        : payload?.message || `上传失败（${response.status}）`
    );
  }

  if (payload?.code !== undefined && payload.code !== 200) {
    throw new Error(payload.message || "上传失败");
  }

  return payload?.data ?? payload;
}

export async function rebuildKnowledgeBaseIndex(kbId) {
  console.log(`[TODO] rebuild index for KB ${kbId}`);
  await new Promise((resolve) => setTimeout(resolve, 500));
  return { success: true };
}

export async function getKnowledgeBaseStats() {
  return null;
}

export async function getDocuments(kbId) {
  return request(`/api/kb/knowledge-bases/${kbId}/documents`);
}

export async function getDocumentChunks(kbId, documentId) {
  return request(`/api/kb/knowledge-bases/${kbId}/documents/${documentId}/chunks`);
}

export async function deleteDocument(kbId, documentId) {
  return request(`/api/kb/knowledge-bases/${kbId}/documents/${documentId}`, {
    method: "DELETE",
  });
}

function getDownloadFileName(response, fallbackName) {
  const disposition = response.headers.get("Content-Disposition") || response.headers.get("content-disposition") || "";
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) return decodeURIComponent(utf8Match[1]);

  const plainMatch = disposition.match(/filename="?([^";]+)"?/i);
  if (plainMatch?.[1]) return plainMatch[1];

  return fallbackName || "download";
}

export async function downloadDocument(kbId, documentId, fallbackName) {
  const auth = getStoredAuth();
  if (!auth?.token) throw new Error("未登录");

  const response = await fetch(`${API_BASE_URL}/api/kb/knowledge-bases/${kbId}/documents/${documentId}/download`, {
    method: "GET",
    headers: { Authorization: `Bearer ${auth.token}` },
  });

  const contentType = response.headers.get("Content-Type") || "";
  if (!response.ok || contentType.includes("application/json")) {
    const payload = await response.json().catch(() => ({}));
    const reason = typeof payload.detail === "string"
      ? payload.detail
      : payload?.message || `HTTP ${response.status}`;

    throw new Error(
      reason === "File not found"
        ? "下载失败：服务器未找到原始文件"
        : reason === "Document version not found"
          ? "下载失败：文档版本不存在"
          : reason === "Original file not saved"
            ? "下载失败：原始文件未保存"
            : `下载失败：${reason}`
    );
  }

  const blob = await response.blob();
  const fileName = getDownloadFileName(response, fallbackName);
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export async function retryDocument(_docId) {
  throw new Error("文档重试接口暂未开放");
}
