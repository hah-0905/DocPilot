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

function getErrorMessage(payload, fallback) {
  if (!payload) return fallback;
  if (typeof payload.detail === "string") return payload.detail;
  if (Array.isArray(payload.detail)) {
    return payload.detail.map((item) => item.msg).filter(Boolean).join("；") || fallback;
  }
  return payload.message || fallback;
}

async function request(path, options = {}, fallback = "请求失败") {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      ...getAuthHeaders(),
      ...(options.headers || {}),
    },
  });

  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(getErrorMessage(payload, `${fallback}：HTTP ${response.status}`));
  }

  if (payload?.code !== undefined && payload.code !== 200) {
    throw new Error(getErrorMessage(payload, fallback));
  }

  return payload?.data ?? payload;
}

export async function createReportTask(data) {
  return request("/api/report/tasks", {
    method: "POST",
    body: JSON.stringify(data),
  }, "报告生成失败");
}

export async function getReportTasks() {
  return request("/api/report/tasks", { method: "GET" }, "报告列表加载失败");
}

export async function getReportTask(taskId) {
  return request(`/api/report/tasks/${taskId}`, { method: "GET" }, "报告详情加载失败");
}

export async function deleteReportTask(taskId) {
  return request(`/api/report/tasks/${taskId}`, { method: "DELETE" }, "报告删除失败");
}
