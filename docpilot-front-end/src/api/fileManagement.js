import { getStoredAuth } from "./auth";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

function getAuthHeaders() {
  const auth = getStoredAuth();
  if (!auth?.token) throw new Error("未登录");
  return { Authorization: `Bearer ${auth.token}` };
}

async function request(path, options = {}) {
  const headers = { ...getAuthHeaders(), "Content-Type": "application/json", ...(options.headers || {}) };
  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401 || response.status === 403) {
      const err = new Error(payload?.detail || "登录已失效");
      err.code = response.status;
      throw err;
    }
    throw new Error(typeof payload.detail === "string" ? payload.detail : payload?.message || `请求失败（${response.status}）`);
  }
  if (payload?.code !== undefined && payload.code !== 200) throw new Error(payload.message || "请求失败");
  return payload?.data ?? payload;
}

/*
 * ===============================================================
 * 文件管理接口
 * Backend: 暂无专用的文件列表/上传/删除/下载/重试接口
 * TODO: 对接后端真实文件接口
 * ===============================================================
 */

/** 获取文件列表 */
export async function getFiles(_params = {}) {
  // TODO: replace with GET /api/kb/knowledge-bases/{kbId}/documents or GET /api/files
  console.warn("[TODO] getFiles — backend endpoint not available, using mock");
  return null; // returns null to signal caller should use fallback
}

/** 上传文件 */
export async function uploadFile(_kbId, _file) {
  // TODO: replace with POST /api/kb/knowledge-bases/{kbId}/upload or POST /api/files/upload
  console.warn("[TODO] uploadFile — backend endpoint not available");
  throw new Error("文件上传接口暂未开放");
}

/** 删除文件 */
export async function deleteFile(_fileId) {
  // TODO: replace with DELETE /api/files/{fileId}
  console.warn("[TODO] deleteFile — backend endpoint not available");
  throw new Error("文件删除接口暂未开放");
}

/** 下载文件 */
export async function downloadFile(_fileId) {
  // TODO: replace with GET /api/files/{fileId}/download
  console.warn("[TODO] downloadFile — backend endpoint not available");
  throw new Error("文件下载接口暂未开放");
}

/** 重试文件处理 */
export async function retryFile(_fileId) {
  // TODO: replace with POST /api/files/{fileId}/retry
  console.warn("[TODO] retryFile — backend endpoint not available");
  throw new Error("文件重试接口暂未开放");
}

/** 获取最近上传任务 */
export async function getRecentUploads() {
  // TODO: replace with GET /api/upload-tasks or similar
  console.warn("[TODO] getRecentUploads — backend endpoint not available");
  return null;
}
