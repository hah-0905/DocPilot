import { getStoredAuth, updateStoredUser } from "./auth";

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
    const validationMessage = Array.isArray(payload?.detail)
      ? payload.detail.map((item) => item?.msg).filter(Boolean).join("；")
      : "";
    throw new Error(
      typeof payload.detail === "string"
        ? payload.detail
        : validationMessage || payload?.message || `请求失败（${response.status}）`
    );
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
export async function updateProfile(userId, data) {
  if (!userId) {
    throw new Error("缺少用户 ID，无法保存资料");
  }

  const user = await request(`/api/settings/userInfo/${userId}`, {
    method: "PUT",
    body: JSON.stringify({
      username: data.username?.trim() || undefined,
      email: data.email?.trim() || undefined,
    }),
  });

  return updateStoredUser(user?.user_info || user);
}

/**
 * 获取当前账号可从知识库中识别出的工作空间。
 * 后端暂未提供独立的工作空间列表接口，因此按 workspace_id 去重。
 */
export async function getModelSettingWorkspaces() {
  const knowledgeBases = await request("/api/kb/knowledge-bases", { cache: "no-store" });
  const workspaceMap = new Map();

  for (const knowledgeBase of Array.isArray(knowledgeBases) ? knowledgeBases : []) {
    const workspaceId = Number(knowledgeBase?.workspace_id);
    if (Number.isInteger(workspaceId) && workspaceId > 0 && !workspaceMap.has(workspaceId)) {
      workspaceMap.set(workspaceId, {
        id: workspaceId,
        label: `工作空间 #${workspaceId}`,
      });
    }
  }

  return [...workspaceMap.values()];
}

/** 保存工作空间模型设置 */
export async function saveModelSettings(workspaceId, data) {
  const normalizedWorkspaceId = Number(workspaceId);
  if (!Number.isInteger(normalizedWorkspaceId) || normalizedWorkspaceId <= 0) {
    throw new Error("请选择有效的工作空间");
  }

  return request(`/api/settings/model/${normalizedWorkspaceId}`, {
    method: "PUT",
    body: JSON.stringify({
      model_key: data.modelKey,
      temperature: Number(data.temperature),
      max_tokens: Number(data.maxTokens),
      response_language: data.responseLanguage,
    }),
  });
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
