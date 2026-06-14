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

export async function createReportTask(data) {
  const response = await fetch(`${API_BASE_URL}/api/report/tasks`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(data),
  });

  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(getErrorMessage(payload, `报告生成失败：HTTP ${response.status}`));
  }

  if (payload?.code !== undefined && payload.code !== 200) {
    throw new Error(getErrorMessage(payload, "报告生成失败"));
  }

  return payload?.data ?? payload;
}
