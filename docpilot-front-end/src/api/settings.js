import { getStoredAuth, updateStoredUser } from "./auth";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

function getAuthHeaders() {
  const auth = getStoredAuth();
  if (!auth?.token) throw new Error("未登录");
  return { Authorization: `Bearer ${auth.token}`, "Content-Type": "application/json" };
}

async function request(path, options = {}) {
  const headers = { ...getAuthHeaders(), ...(options.headers || {}) };
  if (options.body instanceof FormData) {
    delete headers["Content-Type"];
  }
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

  const nextUser = user?.user_info || user;
  const currentUser = getStoredAuth()?.user;

  if (
    nextUser?.avatar_url &&
    !/^https?:\/\//i.test(nextUser.avatar_url) &&
    currentUser?.avatar_key === nextUser.avatar_url &&
    /^https?:\/\//i.test(currentUser?.avatar_url || "")
  ) {
    nextUser.avatar_key = nextUser.avatar_url;
    nextUser.avatar_url = currentUser.avatar_url;
  }

  return updateStoredUser(nextUser);
}

/** Upload and update the current user's avatar. */
export async function uploadAvatar(file) {
  if (!(file instanceof File)) {
    throw new Error("\u8bf7\u9009\u62e9\u5934\u50cf\u6587\u4ef6");
  }

  const formData = new FormData();
  formData.append("file", file);

  const result = await request("/api/settings/avatar", {
    method: "PUT",
    body: formData,
  });

  if (!result?.avatar_url) {
    throw new Error("\u5934\u50cf\u4e0a\u4f20\u6210\u529f\uff0c\u4f46\u540e\u7aef\u672a\u8fd4\u56de\u8bbf\u95ee\u5730\u5740");
  }

  return updateStoredUser({
    avatar_key: result.avatar_key,
    avatar_url: result.avatar_url,
  });
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

function normalizeWorkspaceId(workspaceId) {
  const value = Number(workspaceId);
  if (!Number.isInteger(value) || value <= 0) {
    throw new Error("请选择有效的工作空间");
  }
  return value;
}

/** 保存工作空间检索设置 */
export async function saveRetrievalSettings(workspaceId, data) {
  const normalizedWorkspaceId = normalizeWorkspaceId(workspaceId);

  return request(`/api/settings/retrieval/${normalizedWorkspaceId}`, {
    method: "PUT",
    body: JSON.stringify({
      top_k: Number(data.topK),
      similarity_threshold: Number(data.similarityThreshold),
      enable_rerank: Boolean(data.enableRerank),
      show_sources: Boolean(data.showSources),
    }),
  });
}

/** 保存工作空间报告设置 */
export async function saveReportSettings(workspaceId, data) {
  const normalizedWorkspaceId = normalizeWorkspaceId(workspaceId);

  return request(`/api/settings/report/${normalizedWorkspaceId}`, {
    method: "PUT",
    body: JSON.stringify({
      report_type: data.defaultReportType,
      length: data.defaultLength,
      citation_style: data.citationStyle,
      export_format: data.exportFormat,
    }),
  });
}

/** 修改密码 */
export async function changePassword(_data) {
  // TODO: replace with POST /api/user/change-password
  console.warn("[TODO] changePassword — backend endpoint not available");
  throw new Error("修改密码接口暂未开放");
}
