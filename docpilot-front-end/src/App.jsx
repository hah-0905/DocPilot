import { useCallback, useEffect, useMemo, useState } from "react";
import { clearAuth, getStoredAuth, saveAuth } from "./api/auth";
import DashboardPage from "./pages/DashboardPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";

const KNOWN_PATHS = new Set(["/", "/login", "/register", "/dashboard"]);

function getCurrentPath() {
  const path = window.location.pathname;
  return KNOWN_PATHS.has(path) ? path : "/";
}

export default function App() {
  const [path, setPath] = useState(getCurrentPath);
  const [auth, setAuth] = useState(() => getStoredAuth());

  const navigate = useCallback((nextPath, options = {}) => {
    const target = KNOWN_PATHS.has(nextPath) ? nextPath : "/";
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
    if (path === "/") {
      navigate(auth?.token ? "/dashboard" : "/login", { replace: true });
      return;
    }

    if (path === "/dashboard" && !auth?.token) {
      navigate("/login", { replace: true });
      return;
    }

    if ((path === "/login" || path === "/register") && auth?.token) {
      navigate("/dashboard", { replace: true });
    }
  }, [auth?.token, navigate, path]);

  const handleAuthSuccess = useCallback(
    (authData, options = {}) => {
      saveAuth(authData, options.remember ?? true);
      setAuth(getStoredAuth());
      navigate("/dashboard", { replace: true });
    },
    [navigate]
  );

  const handleLogout = useCallback(() => {
    clearAuth();
    setAuth(null);
    navigate("/login", { replace: true });
  }, [navigate]);

  const currentPage = useMemo(() => {
    if (path === "/register") {
      return <RegisterPage onNavigate={navigate} onAuthSuccess={handleAuthSuccess} />;
    }

    if (path === "/dashboard" && auth?.token) {
      return <DashboardPage auth={auth} onLogout={handleLogout} />;
    }

    return <LoginPage onNavigate={navigate} onAuthSuccess={handleAuthSuccess} />;
  }, [auth, handleAuthSuccess, handleLogout, navigate, path]);

  return currentPage;
}
