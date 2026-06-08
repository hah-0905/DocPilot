import { useEffect, useMemo, useState } from "react";
import { deleteChatSession, listChatSessions } from "../../api/chat";
import { getKnowledgeBases } from "../../api/knowledgeBase";

function ShellIcon({ name, size = 20 }) {
  const paths = {
    plus: <><circle cx="12" cy="12" r="10" /><path d="M8 12h8M12 8v8" /></>,
    layers: <><path d="m12 3 9 5-9 5-9-5 9-5Z" /><path d="m4 12 8 4.5 8-4.5" /><path d="m4 16 8 4.5 8-4.5" /></>,
    file: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Z" /><path d="M14 2v6h6" /></>,
    settings: <><circle cx="12" cy="12" r="3" /><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" /></>,
    chat: <><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10Z" /><circle cx="12" cy="10" r="1" /></>,
    search: <><circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" /></>,
    "chevron-down": <><path d="m6 9 6 6 6-6" /></>,
    "log-out": <><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" /></>,
    trash: <><polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /></>,
  };

  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[name] || paths.file}
    </svg>
  );
}

function toList(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.items)) return data.items;
  if (Array.isArray(data?.list)) return data.list;
  if (Array.isArray(data?.records)) return data.records;
  return [];
}

function normalizeKnowledgeBases(data) {
  return toList(data)
    .filter((kb) => kb?.id !== undefined && kb?.id !== null)
    .map((kb) => ({ id: String(kb.id), name: kb.name || "未命名知识库" }));
}

function normalizeChatSessions(data) {
  const list = Array.isArray(data?.sessions) ? data.sessions : Array.isArray(data) ? data : [];
  return list
    .filter((session) => session?.session_id !== undefined && session?.session_id !== null)
    .map((session) => ({
      ...session,
      session_id: String(session.session_id),
      title: session.title || `对话 ${session.session_id}`,
    }));
}

export function Sidebar({ activePath, onNavigate }) {
  const [kbOpen, setKbOpen] = useState(false);
  const [knowledgeBases, setKnowledgeBases] = useState([]);
  const [kbLoading, setKbLoading] = useState(false);
  const [kbError, setKbError] = useState("");
  const [chatSessions, setChatSessions] = useState([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState("");

  const handleNewChat = () => {
    if (activePath === "/chat") {
      window.dispatchEvent(new CustomEvent("docpilot:new-chat"));
      return;
    }
    onNavigate("/chat");
  };

  const handleOpenChatSession = (session) => {
    if (activePath === "/chat") {
      window.dispatchEvent(new CustomEvent("docpilot:open-chat-session", { detail: session }));
      return;
    }
    sessionStorage.setItem("docpilot_pending_chat_session", JSON.stringify(session));
    onNavigate("/chat");
  };

  const handleDeleteChatSession = async (event, session) => {
    event.preventDefault();
    event.stopPropagation();
    if (!window.confirm(`确定删除「${session.title}」吗？`)) return;

    try {
      await deleteChatSession(session.session_id);
      setChatSessions((current) => current.filter((item) => String(item.session_id) !== String(session.session_id)));
      window.dispatchEvent(new CustomEvent("docpilot:chat-session-deleted", { detail: session }));
      window.dispatchEvent(new CustomEvent("docpilot:chat-sessions-changed"));
    } catch (err) {
      setChatError(err.message || "删除对话失败");
    }
  };

  useEffect(() => {
    if (!kbOpen || knowledgeBases.length > 0 || kbLoading) return;

    let ignore = false;
    const loadKnowledgeBases = async () => {
      setKbLoading(true);
      setKbError("");
      try {
        const data = await getKnowledgeBases();
        if (!ignore) setKnowledgeBases(normalizeKnowledgeBases(data));
      } catch (err) {
        if (!ignore) setKbError(err.message || "知识库加载失败");
      } finally {
        if (!ignore) setKbLoading(false);
      }
    };

    loadKnowledgeBases();
    return () => {
      ignore = true;
    };
  }, [kbLoading, kbOpen, knowledgeBases.length]);

  useEffect(() => {
    let ignore = false;
    const loadChatSessions = async () => {
      setChatLoading(true);
      setChatError("");
      try {
        const data = await listChatSessions();
        if (!ignore) setChatSessions(normalizeChatSessions(data));
      } catch (err) {
        if (!ignore) setChatError(err.message || "对话列表加载失败");
      } finally {
        if (!ignore) setChatLoading(false);
      }
    };

    loadChatSessions();
    const handleSessionsChanged = () => loadChatSessions();
    window.addEventListener("docpilot:chat-sessions-changed", handleSessionsChanged);
    return () => {
      ignore = true;
      window.removeEventListener("docpilot:chat-sessions-changed", handleSessionsChanged);
    };
  }, []);

  const isKnowledgeBaseActive = activePath === "/knowledge-base" || activePath.startsWith("/knowledge-base/");

  return (
    <aside className="app-sidebar">
      <div className="app-sidebar__brand">
        <span className="app-sidebar__logo" aria-hidden="true"><span /></span>
        <span className="app-sidebar__name">DocPilot</span>
      </div>

      <button className="app-sidebar__new-btn" onClick={handleNewChat}>
        <ShellIcon name="plus" size={18} />
        <span>新建对话</span>
      </button>

      <nav className="app-sidebar__nav" aria-label="主导航">
        <div className="app-nav-group">
          <div className={`app-nav-row${isKnowledgeBaseActive ? " app-nav-row--active" : ""}`}>
            <a
              className="app-nav-item app-nav-item--with-toggle"
              href="/knowledge-base"
              onClick={(event) => {
                event.preventDefault();
                onNavigate("/knowledge-base");
              }}
            >
              <ShellIcon name="layers" size={18} />
              <span>知识库</span>
            </a>
            <button
              type="button"
              className={`app-nav-toggle${kbOpen ? " app-nav-toggle--open" : ""}`}
              title={kbOpen ? "收起知识库文件列表" : "展开知识库文件列表"}
              aria-label={kbOpen ? "收起知识库文件列表" : "展开知识库文件列表"}
              aria-expanded={kbOpen}
              onClick={() => setKbOpen((current) => !current)}
            >
              <ShellIcon name="chevron-down" size={15} />
            </button>
          </div>

          {kbOpen && (
            <div className="app-kb-sublist">
              {kbLoading ? (
                <div className="app-kb-subitem app-kb-subitem--muted">加载中...</div>
              ) : kbError ? (
                <div className="app-kb-subitem app-kb-subitem--error">{kbError}</div>
              ) : knowledgeBases.length === 0 ? (
                <div className="app-kb-subitem app-kb-subitem--muted">暂无知识库</div>
              ) : knowledgeBases.map((kb) => (
                <button
                  key={kb.id}
                  type="button"
                  className="app-kb-subitem"
                  onClick={() => onNavigate(`/knowledge-base/${kb.id}`)}
                >
                  <span className="app-kb-subitem__dot" />
                  <span>{kb.name}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="app-nav-divider" aria-hidden="true" />

        <a
          className={`app-nav-item${activePath === "/chat" ? " app-nav-item--active" : ""}`}
          href="/chat"
          onClick={(event) => {
            event.preventDefault();
            onNavigate("/chat");
          }}
        >
          <ShellIcon name="chat" size={18} />
          <span>智能问答</span>
        </a>

        <div className="app-chat-sublist">
          {chatLoading ? (
            <div className="app-chat-subitem app-chat-subitem--muted">加载中...</div>
          ) : chatError ? (
            <div className="app-chat-subitem app-chat-subitem--error">{chatError}</div>
          ) : chatSessions.length === 0 ? (
            <div className="app-chat-subitem app-chat-subitem--muted">暂无对话</div>
          ) : chatSessions.map((session) => (
            <div
              key={session.session_id}
              className="app-chat-subitem"
              role="button"
              tabIndex={0}
              onClick={() => handleOpenChatSession(session)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  handleOpenChatSession(session);
                }
              }}
            >
              <span className="app-chat-subitem__dot" />
              <span>{session.title}</span>
              <button
                type="button"
                className="app-chat-subitem__delete"
                title="删除对话"
                aria-label="删除对话"
                onClick={(event) => handleDeleteChatSession(event, session)}
              >
                <ShellIcon name="trash" size={13} />
              </button>
            </div>
          ))}
        </div>
      </nav>

      <div className="app-sidebar__footer">
        <a
          className={`app-nav-item${activePath === "/files" ? " app-nav-item--active" : ""}`}
          href="/files"
          onClick={(event) => {
            event.preventDefault();
            onNavigate("/files");
          }}
        >
          <ShellIcon name="file" size={18} />
          <span>文件管理</span>
        </a>
        <a
          className={`app-nav-item${activePath === "/settings" ? " app-nav-item--active" : ""}`}
          href="/settings"
          onClick={(event) => {
            event.preventDefault();
            onNavigate("/settings");
          }}
        >
          <ShellIcon name="settings" size={18} />
          <span>设置</span>
        </a>
      </div>
    </aside>
  );
}

export function TopBar({ title, breadcrumb, actions, meta, onNavigate, onLogout }) {
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  useEffect(() => {
    if (!userMenuOpen) return undefined;
    const handleClickAway = (event) => {
      if (!event.target.closest(".app-user-menu")) setUserMenuOpen(false);
    };

    window.addEventListener("click", handleClickAway);
    return () => window.removeEventListener("click", handleClickAway);
  }, [userMenuOpen]);

  const handleSettings = () => {
    setUserMenuOpen(false);
    onNavigate?.("/settings");
  };

  const handleLogout = () => {
    setUserMenuOpen(false);
    onLogout?.();
  };

  return (
    <header className="app-topbar">
      <div className="app-topbar__title-group">
        {breadcrumb && <div className="app-topbar__breadcrumb">{breadcrumb}</div>}
        <div className="app-topbar__title-row">
          <span className="app-topbar__label">当前页面：</span>
          <h1 className="app-topbar__title">{title}</h1>
        </div>
      </div>
      {meta && <div className="app-topbar__meta">{meta}</div>}
      <div className="app-topbar__actions">
        {actions}
        <button className="app-topbar__icon-btn" title="搜索">
          <ShellIcon name="search" size={18} />
        </button>
        <div className="app-user-menu">
          <button
            type="button"
            className={`app-user-menu__trigger${userMenuOpen ? " app-user-menu__trigger--open" : ""}`}
            aria-expanded={userMenuOpen}
            aria-label="打开用户菜单"
            onClick={(event) => {
              event.stopPropagation();
              setUserMenuOpen((current) => !current);
            }}
          >
            <span className="app-avatar" />
            <ShellIcon name="chevron-down" size={16} />
          </button>
          {userMenuOpen && (
            <div className="app-user-menu__dropdown">
              <button type="button" className="app-user-menu__item" onClick={handleSettings}>
                <ShellIcon name="settings" size={16} />
                <span>设置</span>
              </button>
              <button type="button" className="app-user-menu__item app-user-menu__item--danger" onClick={handleLogout}>
                <ShellIcon name="log-out" size={16} />
                <span>退出登录</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

export function RightPanel({ children, className = "" }) {
  if (!children) return null;
  return <aside className={`app-right-panel${className ? ` ${className}` : ""}`}>{children}</aside>;
}

export function PageLayout({ children, rightPanel, className = "" }) {
  return (
    <div className={`app-page-layout${className ? ` ${className}` : ""}`}>
      <main className="app-page-main">{children}</main>
      <RightPanel>{rightPanel}</RightPanel>
    </div>
  );
}

export function MainLayout({ topBar, children }) {
  return (
    <div className="app-main-layout">
      {topBar}
      <div className="app-main-scroll">{children}</div>
    </div>
  );
}

export default function AppShell({ activePath, title, breadcrumb, actions, meta, onNavigate, onLogout, children }) {
  const topBar = useMemo(
    () => <TopBar title={title} breadcrumb={breadcrumb} actions={actions} meta={meta} onNavigate={onNavigate} onLogout={onLogout} />,
    [actions, breadcrumb, meta, onLogout, onNavigate, title]
  );

  return (
    <div className="app-shell">
      <Sidebar activePath={activePath} onNavigate={onNavigate} />
      <MainLayout topBar={topBar}>{children}</MainLayout>
    </div>
  );
}
