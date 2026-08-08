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

function getDownloadHeaders() {
  const auth = getStoredAuth();
  if (!auth?.token) throw new Error("未登录");
  return {
    Authorization: `Bearer ${auth.token}`,
  };
}

function getErrorMessage(payload, fallback) {
  if (!payload) return fallback;
  if (typeof payload.detail === "string") return payload.detail;
  if (Array.isArray(payload.detail)) {
    return payload.detail.map((item) => item.msg).filter(Boolean).join("，") || fallback;
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

function getDownloadFileName(response, fallbackName) {
  const disposition = response.headers.get("Content-Disposition") || response.headers.get("content-disposition") || "";
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) return decodeURIComponent(utf8Match[1]);

  const plainMatch = disposition.match(/filename="?([^";]+)"?/i);
  if (plainMatch?.[1]) return plainMatch[1];

  return fallbackName || "report.md";
}

async function parseDownloadError(response, fallback) {
  const payload = await response.json().catch(() => ({}));
  return getErrorMessage(payload, `${fallback}：HTTP ${response.status}`);
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

export async function createReportExport(taskId, exportFormat = "markdown") {
  return request(`/api/report/tasks/${taskId}/export`, {
    method: "POST",
    body: JSON.stringify({ export_format: exportFormat }),
  }, "报告导出失败");
}

export async function getReportExports(taskId) {
  return request(`/api/report/tasks/${taskId}/exports`, { method: "GET" }, "导出记录加载失败");
}

export async function downloadReportExport(exportId, fallbackName) {
  const response = await fetch(`${API_BASE_URL}/api/report/exports/${exportId}/download`, {
    method: "GET",
    headers: getDownloadHeaders(),
  });

  const contentType = response.headers.get("Content-Type") || "";
  if (!response.ok || contentType.includes("application/json")) {
    throw new Error(await parseDownloadError(response, "导出文件下载失败"));
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
