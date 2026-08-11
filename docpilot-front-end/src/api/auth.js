const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

export const TOKEN_KEY = "docpilot_token";
export const USER_KEY = "docpilot_user";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {})
    },
    ...options
  });

  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(getErrorMessage(payload, `请求失败（${response.status}）`));
  }

  if (payload?.code && payload.code !== 200) {
    throw new Error(getErrorMessage(payload, "请求失败"));
  }

  return payload?.data ?? payload;
}

function getErrorMessage(payload, fallback) {
  if (!payload) {
    return fallback;
  }

  if (typeof payload.detail === "string") {
    return payload.detail;
  }

  if (Array.isArray(payload.detail)) {
    return payload.detail.map((item) => item.msg).filter(Boolean).join("；") || fallback;
  }

  return payload.message || fallback;
}

export function loginUser(data) {
  return request("/api/user/login", {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export function registerUser(data) {
  return request("/api/user/register", {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export function saveAuth(authData, remember = true) {
  const storage = remember ? localStorage : sessionStorage;
  const otherStorage = remember ? sessionStorage : localStorage;
  const token = authData?.token;
  const user = authData?.user_info || null;

  if (!token) {
    throw new Error("登录响应中缺少 token");
  }

  storage.setItem(TOKEN_KEY, token);
  storage.setItem(USER_KEY, JSON.stringify(user));
  otherStorage.removeItem(TOKEN_KEY);
  otherStorage.removeItem(USER_KEY);
}

export function getStoredAuth() {
  const token = localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY);
  const rawUser = localStorage.getItem(USER_KEY) || sessionStorage.getItem(USER_KEY);

  if (!token) {
    return null;
  }

  try {
    return {
      token,
      user: rawUser ? JSON.parse(rawUser) : null
    };
  } catch {
    return { token, user: null };
  }
}

/** Update the cached user information without changing the login token. */
export function updateStoredUser(userData) {
  const auth = getStoredAuth();
  if (!auth?.token) {
    throw new Error("未登录");
  }

  const user = { ...(auth.user || {}), ...userData };
  const storage = localStorage.getItem(TOKEN_KEY) ? localStorage : sessionStorage;
  storage.setItem(USER_KEY, JSON.stringify(user));
  return user;
}
export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(USER_KEY);
}

export async function logoutUser() {
  const auth = getStoredAuth();
  if (!auth?.token) return;

  await fetch(`${API_BASE_URL}/api/user/logout`, {
    method: "POST",
    headers: { Authorization: `Bearer ${auth.token}` },
  });
}
