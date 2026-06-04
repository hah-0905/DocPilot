import { getStoredAuth } from "./auth";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

function getAuthHeaders() {
  const auth = getStoredAuth();
  if (!auth?.token) throw new Error("未登录");
  return { Authorization: `Bearer ${auth.token}`, "Content-Type": "application/json" };
}

async function request(path, options = {}) {
  const headers = { ...getAuthHeaders(), ...(options.headers || {}) };
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
 * 设置相关接口 — 后端暂无对应 endpoint
 * TODO: 待后端提供设置/密码修改接口后对接
 * ===============================================================
 */

/** 获取用户信息 — 目前从 localStorage 读取 */
export function getLocalUser() {
  const auth = getStoredAuth();
  return auth?.user || null;
}

/** 更新用户资料 */
export async function updateProfile(_data) {
  // TODO: replace with PUT /api/user/profile
  console.warn("[TODO] updateProfile — backend endpoint not available");
  throw new Error("个人资料编辑接口暂未开放");
}

/** 保存模型设置 */
export async function saveModelSettings(_data) {
  // TODO: replace with PUT /api/settings/model
  console.warn("[TODO] saveModelSettings — backend endpoint not available");
  throw new Error("模型设置保存接口暂未开放");
}

/** 保存检索设置 */
export async function saveRetrievalSettings(_data) {
  // TODO: replace with PUT /api/settings/retrieval
  console.warn("[TODO] saveRetrievalSettings — backend endpoint not available");
  throw new Error("检索设置保存接口暂未开放");
}

/** 保存报告设置 */
export async function saveReportSettings(_data) {
  // TODO: replace with PUT /api/settings/report
  console.warn("[TODO] saveReportSettings — backend endpoint not available");
  throw new Error("报告设置保存接口暂未开放");
}

/** 修改密码 */
export async function changePassword(_data) {
  // TODO: replace with POST /api/user/change-password
  console.warn("[TODO] changePassword — backend endpoint not available");
  throw new Error("修改密码接口暂未开放");
}
