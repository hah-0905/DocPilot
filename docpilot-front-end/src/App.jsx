import { useCallback, useEffect, useMemo, useState } from "react";
import { clearAuth, getStoredAuth, saveAuth } from "./api/auth";
import DashboardPage from "./pages/DashboardPage";
import KnowledgeBasePage from "./pages/KnowledgeBasePage";
import KnowledgeBaseDetailPage from "./pages/KnowledgeBaseDetailPage";
import FileManagementPage from "./pages/FileManagementPage";
import SettingsPage from "./pages/SettingsPage";
import ChatPage from "./pages/ChatPage";
import ReportPage from "./pages/ReportPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import AppShell from "./components/layout/AppShell";

const KNOWN_PATHS = new Set(["/", "/login", "/register", "/dashboard", "/knowledge-base", "/files", "/settings", "/chat", "/report"]);

/** Check if path is a KB detail route: /knowledge-base/<id> */
function isKBDetailPath(path) {
  return /^\/knowledge-base\/[^/]+$/.test(path);
}

/** Get normalized path — returns full path for KB detail, otherwise exact match or "/" */
function getCurrentPath() {
  const raw = window.location.pathname;
  if (KNOWN_PATHS.has(raw)) return raw;
  if (isKBDetailPath(raw)) return raw;
  return "/";
}

export default function App() {
  const [path, setPath] = useState(getCurrentPath);
  const [auth, setAuth] = useState(() => getStoredAuth());

  const navigate = useCallback((nextPath, options = {}) => {
    // Allow dynamic paths like /knowledge-base/123
    const target = KNOWN_PATHS.has(nextPath) || isKBDetailPath(nextPath) ? nextPath : "/";
    const method = options.replace ? "replaceState" : "pushState";

    if (window.location.pathname !== target) {
      window.history[method]({}, "", target);
    }

    setPath(target);
  }, []);

  useEffect(() => {
    const handlePopState = () => setPath(getCurrentPath());
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  useEffect(() => {
    const isAuthPage = path === "/login" || path === "/register";
    const isProtectedPage = path === "/knowledge-base" || isKBDetailPath(path) || path === "/dashboard" || path === "/files" || path === "/settings" || path === "/chat" || path === "/report";

    if (path === "/") {
      navigate(auth?.token ? "/knowledge-base" : "/login", { replace: true });
      return;
    }

    if (isProtectedPage && !auth?.token) {
      navigate("/login", { replace: true });
      return;
    }

    if (isAuthPage && auth?.token) {
      navigate("/knowledge-base", { replace: true });
    }
  }, [auth?.token, navigate, path]);

  const handleAuthSuccess = useCallback(
    (authData, options = {}) => {
      saveAuth(authData, options.remember ?? true);
      setAuth(getStoredAuth());
      navigate("/knowledge-base", { replace: true });
    },
    [navigate]
  );

  const handleLogout = useCallback(() => {
    clearAuth();
    setAuth(null);
    navigate("/login", { replace: true });
  }, [navigate]);

  const shellMeta = useMemo(() => {
    if (path === "/chat") {
      return { title: "智能问答", breadcrumb: "首页 / 智能问答", meta: "接口：/api/chat/completions" };
    }
    if (path === "/report") {
      return { title: "报告生成", breadcrumb: "首页 / 报告生成", meta: "接口：/api/report/tasks" };
    }
    if (path === "/files") {
      return { title: "我上传的文件", breadcrumb: "首页 / 文件管理", meta: "模型：DeepSeek / GPT" };
    }
    if (path === "/settings") {
      return { title: "设置", breadcrumb: "首页 / 设置", meta: "偏好与账号" };
    }
    if (isKBDetailPath(path)) {
      return { title: "知识库详情", breadcrumb: "首页 / 知识库 / 详情", meta: "模型：DeepSeek / GPT" };
    }
    if (path === "/dashboard") {
      return { title: "工作台", breadcrumb: "首页 / 工作台", meta: "DocPilot" };
    }
    return { title: "知识库", breadcrumb: "首页 / 知识库", meta: "模型：DeepSeek / GPT" };
  }, [path]);

  const currentPage = useMemo(() => {
    if (path === "/register") {
      return <RegisterPage onNavigate={navigate} onAuthSuccess={handleAuthSuccess} />;
    }

    if (path === "/knowledge-base" && auth?.token) {
      return <KnowledgeBasePage onNavigate={navigate} />;
    }

    if (isKBDetailPath(path) && auth?.token) {
      return <KnowledgeBaseDetailPage onNavigate={navigate} />;
    }

    if (path === "/files" && auth?.token) {
      return <FileManagementPage onNavigate={navigate} />;
    }

    if (path === "/settings" && auth?.token) {
      return <SettingsPage onNavigate={navigate} onLogout={handleLogout} />;
    }

    if (path === "/chat" && auth?.token) {
      return <ChatPage onNavigate={navigate} />;
    }

    if (path === "/report" && auth?.token) {
      return <ReportPage />;
    }

    if (path === "/dashboard" && auth?.token) {
      return <DashboardPage auth={auth} onLogout={handleLogout} />;
    }

    return <LoginPage onNavigate={navigate} onAuthSuccess={handleAuthSuccess} />;
  }, [auth, handleAuthSuccess, handleLogout, navigate, path]);

  const isProtectedPage = auth?.token && (
    path === "/knowledge-base" ||
    isKBDetailPath(path) ||
    path === "/dashboard" ||
    path === "/files" ||
    path === "/settings" ||
    path === "/chat" ||
    path === "/report"
  );

  if (!isProtectedPage) return currentPage;

  return (
    <AppShell
      activePath={isKBDetailPath(path) ? "/knowledge-base" : path}
      title={shellMeta.title}
      breadcrumb={shellMeta.breadcrumb}
      meta={shellMeta.meta}
      onNavigate={navigate}
      onLogout={handleLogout}
    >
      {currentPage}
    </AppShell>
  );
}
