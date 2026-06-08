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

export async function createChatCompletion({ sessionId, message, stream = false }) {
  return request("/api/chat/completions", {
    method: "POST",
    body: JSON.stringify({
      session_id: sessionId,
      message,
      stream,
    }),
  });
}

export async function streamChatCompletion({ sessionId, message, onChunk }) {
  const response = await fetch(`${API_BASE_URL}/api/chat/completions`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({
      session_id: sessionId,
      message,
      stream: true,
    }),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(
      typeof payload.detail === "string"
        ? payload.detail
        : payload?.message || `请求失败（${response.status}）`
    );
  }

  if (!response.body) {
    throw new Error("浏览器不支持流式响应");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split(/\n\n/);
    buffer = events.pop() || "";

    for (const event of events) {
      const lines = event.split(/\r?\n/);
      const eventName = lines.find((line) => line.startsWith("event:"))?.slice(6).trim();
      const data = lines
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart())
        .join("\n");

      if (!data || data === "[DONE]") continue;
      if (eventName === "error") throw new Error(data);
      onChunk?.(data);
    }
  }
}

export async function listChatSessions() {
  return request("/api/chat/sessions", { method: "GET" });
}

export async function getChatMessages(sessionId) {
  return request(`/api/chat/sessions/${sessionId}/messages`);
}

export async function deleteChatSession(sessionId) {
  return request(`/api/chat/sessions/${sessionId}`, {
    method: "DELETE",
  });
}
