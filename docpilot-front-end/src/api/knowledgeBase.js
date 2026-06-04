import { getStoredAuth } from "./auth";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

function getAuthHeaders() {
  const auth = getStoredAuth();
  if (!auth?.token) {
    throw new Error("未登录");
  }
  return {
    Authorization: `Bearer ${auth.token}`,
    "Content-Type": "application/json",
  };
}

/** 通用请求封装 */
async function request(path, options = {}) {
  const headers = { ...getAuthHeaders(), ...(options.headers || {}) };
  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    // Handle 401/403 — signal unauthorized
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

  // ApiResponse wrapper: { code, message, data }
  if (payload?.code !== undefined && payload.code !== 200) {
    throw new Error(payload.message || "请求失败");
  }

  return payload?.data ?? payload;
}

/* ===============================================================
   知识库接口
   Backend: GET /api/kb/knowledge-bases → list
            POST /api/kb/knowledge-bases → create
            DELETE /api/kb/knowledge-bases/{id} → soft delete
            GET /api/kb/knowledge-bases/{id} → detail
   =============================================================== */

/**
 * 获取知识库列表
 * 后端无 search/sort 参数，前端本地过滤排序
 */
export async function getKnowledgeBases() {
  return request("/api/kb/knowledge-bases");
}

/**
 * 获取单个知识库详情
 */
export async function getKnowledgeBase(id) {
  return request(`/api/kb/knowledge-bases/${id}`);
}

/**
 * 创建知识库
 * @param {{ name: string, description?: string, workspace_id: number }} data
 */
export async function createKnowledgeBase(data) {
  return request("/api/kb/knowledge-bases", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/**
 * 删除知识库（软删除）
 */
export async function deleteKnowledgeBase(id) {
  return request(`/api/kb/knowledge-bases/${id}`, { method: "DELETE" });
}

/**
 * 更新知识库
 */
export async function updateKnowledgeBase(id, data) {
  return request(`/api/kb/knowledge-bases/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

/* ===============================================================
   文档上传接口
   Backend: POST /api/kb/knowledge-bases/{kb_id}/documents/upload
           → multipart/form-data, field name: "files"
           → returns array of { id, title, original_file_name, file_ext,
             size_bytes, parse_status, index_status, chunk_count, ... }
   =============================================================== */

/**
 * 上传文件到知识库
 * @param {number|string} kbId - 知识库ID
 * @param {File|File[]} files - 单个文件或文件数组
 * @returns {Promise<Array>} 上传结果数组
 */
export async function uploadKnowledgeBaseFile(kbId, files) {
  const fileArray = Array.isArray(files) ? files : [files];
  if (fileArray.length === 0) throw new Error("请选择文件");

  const formData = new FormData();
  for (const file of fileArray) {
    formData.append("files", file);
  }

  const headers = { Authorization: `Bearer ${getStoredAuth()?.token}` };
  // Do NOT set Content-Type — browser sets it with boundary for FormData

  const response = await fetch(`${API_BASE_URL}/api/kb/knowledge-bases/${kbId}/documents/upload`, {
    method: "POST",
    headers,
    body: formData,
  });

  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    if (response.status === 401 || response.status === 403) {
      const err = new Error(payload?.detail || "登录已失效");
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

/** 重建知识库索引 */
export async function rebuildKnowledgeBaseIndex(kbId) {
  // TODO: replace with real rebuild endpoint when available
  console.log(`[TODO] rebuild index for KB ${kbId}`);
  await new Promise((r) => setTimeout(r, 500));
  return { success: true };
}

/** 获取知识库统计概览 */
export async function getKnowledgeBaseStats() {
  return null;
}

/* ===============================================================
   文档相关接口
   Backend: GET /api/kb/knowledge-bases/{kb_id}/documents → list
           POST /api/kb/knowledge-bases/{kb_id}/documents/upload → upload
           DELETE /api/kb/knowledge-bases/{kb_id}/documents/{document_id} → delete
   =============================================================== */

/**
 * 获取知识库文档列表
 * @returns {Promise<Array>} [{ id, name, type, status, updated_at, chunks }]
 */
export async function getDocuments(kbId) {
  return request(`/api/kb/knowledge-bases/${kbId}/documents`);
}

/**
 * 删除文档
 * @param {number|string} kbId
 * @param {number|string} documentId
 */
export async function deleteDocument(kbId, documentId) {
  return request(`/api/kb/knowledge-bases/${kbId}/documents/${documentId}`, {
    method: "DELETE",
  });
}

/** 重试文档处理 (TODO: endpoint not available yet) */
export async function retryDocument(_docId) {
  throw new Error("文档重试接口暂未开放");
}
