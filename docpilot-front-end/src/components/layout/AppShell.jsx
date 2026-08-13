import { useCallback, useEffect, useRef, useState } from "react";
import { getStoredAuth } from "../../api/auth";
import { deleteChatSession, listChatSessions } from "../../api/chat";
import { getKnowledgeBases } from "../../api/knowledgeBase";

function ShellIcon({ name, size = 20 }) {
  const paths = {
    plus: <><path d="M12 5v14M5 12h14" /></>,
    layers: <><path d="m12 3 9 5-9 5-9-5 9-5Z" /><path d="m4 12 8 4.5 8-4.5" /><path d="m4 16 8 4.5 8-4.5" /></>,
    file: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Z" /><path d="M14 2v6h6" /></>,
    report: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" /><path d="M14 2v6h6M8 13h8M8 17h5" /></>,
    settings: <><circle cx="12" cy="12" r="3" /><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" /></>,
    search: <><circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" /></>,
    menu: <><path d="M4 7h16M4 12h16M4 17h16" /></>,
    close: <><path d="m6 6 12 12M18 6 6 18" /></>,
    "chevron-down": <><path d="m6 9 6 6 6-6" /></>,
    "log-out": <><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><path d="m16 17 5-5-5-5M21 12H9" /></>,
    trash: <><path d="M3 6h18M8 6V4h8v2M19 6l-1 15H6L5 6" /></>,
  };
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[name] || paths.file}
    </svg>
  );
}

function UserAvatar({ user, className = "app-avatar" }) {
  const userName = user?.display_name || user?.username || user?.email || "\u7528\u6237";
  const avatarUrl = /^https?:\/\//i.test(user?.avatar_url || "") ? user.avatar_url : "";

  return (
    <span className={className} aria-label={`${userName} avatar`}>
      {userName.slice(0, 1).toUpperCase()}
      {avatarUrl && (
        <img
          src={avatarUrl}
          alt=""
          onError={(event) => { event.currentTarget.style.display = "none"; }}
        />
      )}
    </span>
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
    .filter((item) => item?.id !== undefined && item?.id !== null)
    .map((item) => ({ id: String(item.id), name: item.name || "未命名知识库" }));
}

function normalizeChatSessions(data) {
  const list = Array.isArray(data?.sessions) ? data.sessions : Array.isArray(data) ? data : [];
  return list
    .filter((item) => item?.session_id !== undefined && item?.session_id !== null)
    .map((item) => ({ ...item, session_id: String(item.session_id), title: item.title || `对话 ${item.session_id}` }));
}

function NavLink({ active, href, icon, onNavigate, children }) {
  return (
    <a className={`app-nav-item${active ? " app-nav-item--active" : ""}`} href={href} onClick={(event) => { event.preventDefault(); onNavigate(href); }}>
      <ShellIcon name={icon} size={17} /><span>{children}</span>
    </a>
  );
}

export function Sidebar({ activePath, onNavigate, onClose, onLogout }) {
  const [kbOpen, setKbOpen] = useState(true);
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const accountMenuRef = useRef(null);
  const [knowledgeBases, setKnowledgeBases] = useState([]);
  const [kbState, setKbState] = useState({ loading: true, error: "" });
  const [chatSessions, setChatSessions] = useState([]);
  const [chatState, setChatState] = useState({ loading: true, error: "" });
  const [activeSessionId, setActiveSessionId] = useState(null);
  const auth = getStoredAuth();
  const userName = auth?.user?.display_name || auth?.user?.username || auth?.user?.email || "用户";

  const navigateAndClose = useCallback((path) => {
    onNavigate(path);
    onClose?.();
  }, [onClose, onNavigate]);

  const navigateFromAccountMenu = useCallback((path) => {
    setAccountMenuOpen(false);
    navigateAndClose(path);
  }, [navigateAndClose]);

  const logoutFromAccountMenu = useCallback(() => {
    setAccountMenuOpen(false);
    onClose?.();
    onLogout();
  }, [onClose, onLogout]);

  const loadKnowledgeBases = useCallback(async () => {
    setKbState({ loading: true, error: "" });
    try {
      setKnowledgeBases(normalizeKnowledgeBases(await getKnowledgeBases()));
      setKbState({ loading: false, error: "" });
    } catch (error) {
      setKbState({ loading: false, error: error.message || "知识库加载失败" });
    }
  }, []);

  const loadChatSessions = useCallback(async () => {
    setChatState({ loading: true, error: "" });
    try {
      setChatSessions(normalizeChatSessions(await listChatSessions()));
      setChatState({ loading: false, error: "" });
    } catch (error) {
      setChatState({ loading: false, error: error.message || "对话列表加载失败" });
    }
  }, []);

  useEffect(() => {
    loadKnowledgeBases();
    loadChatSessions();
  }, [loadChatSessions, loadKnowledgeBases]);

  useEffect(() => {
    if (!accountMenuOpen) return undefined;
    const closeAccountMenu = (event) => {
      if (event.key === "Escape") {
        setAccountMenuOpen(false);
        return;
      }
      if (event.type === "pointerdown" && !accountMenuRef.current?.contains(event.target)) {
        setAccountMenuOpen(false);
      }
    };
    window.addEventListener("pointerdown", closeAccountMenu);
    window.addEventListener("keydown", closeAccountMenu);
    return () => {
      window.removeEventListener("pointerdown", closeAccountMenu);
      window.removeEventListener("keydown", closeAccountMenu);
    };
  }, [accountMenuOpen]);

  useEffect(() => {
    setAccountMenuOpen(false);
  }, [activePath]);

  useEffect(() => {
    const sessionsChanged = () => loadChatSessions();
    const knowledgeBasesChanged = () => loadKnowledgeBases();
    const activeSessionChanged = (event) => setActiveSessionId(event.detail?.session_id ? String(event.detail.session_id) : null);
    window.addEventListener("docpilot:chat-sessions-changed", sessionsChanged);
    window.addEventListener("docpilot:knowledge-bases-changed", knowledgeBasesChanged);
    window.addEventListener("docpilot:active-chat-session", activeSessionChanged);
    return () => {
      window.removeEventListener("docpilot:chat-sessions-changed", sessionsChanged);
      window.removeEventListener("docpilot:knowledge-bases-changed", knowledgeBasesChanged);
      window.removeEventListener("docpilot:active-chat-session", activeSessionChanged);
    };
  }, [loadChatSessions, loadKnowledgeBases]);

  const newChat = () => {
    if (activePath === "/chat") window.dispatchEvent(new CustomEvent("docpilot:new-chat"));
    else onNavigate("/chat");
    onClose?.();
  };

  const openSession = (session) => {
    if (activePath === "/chat") window.dispatchEvent(new CustomEvent("docpilot:open-chat-session", { detail: session }));
    else {
      sessionStorage.setItem("docpilot_pending_chat_session", JSON.stringify(session));
      onNavigate("/chat");
    }
    onClose?.();
  };

  const deleteSession = async (event, session) => {
    event.preventDefault();
    event.stopPropagation();
    if (!window.confirm(`确定删除「${session.title}」吗？`)) return;
    try {
      await deleteChatSession(session.session_id);
      setChatSessions((items) => items.filter((item) => item.session_id !== session.session_id));
      window.dispatchEvent(new CustomEvent("docpilot:chat-session-deleted", { detail: session }));
      window.dispatchEvent(new CustomEvent("docpilot:chat-sessions-changed"));
    } catch (error) {
      setChatState({ loading: false, error: error.message || "删除对话失败" });
    }
  };

  const isKbActive = activePath === "/knowledge-base" || activePath.startsWith("/knowledge-base/");

  return (
    <aside className="app-sidebar" aria-label="DocPilot 主导航">
      <div className="app-sidebar__brand">
        <button className="app-sidebar__brand-button" type="button" onClick={() => navigateAndClose("/knowledge-base")}>
          <span className="app-sidebar__logo" aria-hidden="true"><span /></span><span className="app-sidebar__name">DocPilot</span>
        </button>
        <button className="app-sidebar__mobile-close" type="button" aria-label="关闭导航" onClick={onClose}><ShellIcon name="close" size={20} /></button>
      </div>

      <button className="app-sidebar__new-btn" type="button" onClick={newChat}><ShellIcon name="plus" size={18} /><span>新建对话</span></button>

      <nav className="app-sidebar__nav" aria-label="工作区导航">
        <section className="app-sidebar__section">
          <div className="app-nav-row">
            <a className={`app-nav-item app-nav-item--with-toggle${isKbActive ? " app-nav-item--active" : ""}`} href="/knowledge-base" onClick={(event) => { event.preventDefault(); navigateAndClose("/knowledge-base"); }}>
              <ShellIcon name="layers" size={17} /><span>知识库</span>
            </a>
            <button type="button" className={`app-nav-toggle${kbOpen ? " app-nav-toggle--open" : ""}`} aria-label={kbOpen ? "收起知识库" : "展开知识库"} aria-expanded={kbOpen} onClick={() => setKbOpen((value) => !value)}><ShellIcon name="chevron-down" size={14} /></button>
          </div>
          {kbOpen && <div className="app-kb-sublist">
            {kbState.loading ? <div className="app-kb-subitem app-kb-subitem--muted">加载中...</div>
              : kbState.error ? <button type="button" className="app-kb-subitem app-kb-subitem--error" onClick={loadKnowledgeBases}>{kbState.error}</button>
                : knowledgeBases.length === 0 ? <div className="app-kb-subitem app-kb-subitem--muted">暂无知识库</div>
                  : <>{knowledgeBases.slice(0, 6).map((kb) => <button key={kb.id} type="button" className={`app-kb-subitem${activePath === `/knowledge-base/${kb.id}` ? " app-kb-subitem--active" : ""}`} onClick={() => navigateAndClose(`/knowledge-base/${kb.id}`)}><span>{kb.name}</span></button>)}{knowledgeBases.length > 6 && <button type="button" className="app-kb-subitem app-kb-subitem--all" onClick={() => navigateAndClose("/knowledge-base")}>查看全部 {knowledgeBases.length} 个</button>}</>}
          </div>}
        </section>


        <section className="app-sidebar__section">
          <div className="app-sidebar__section-title">最近对话</div>
          <div className="app-chat-sublist">
            {chatState.loading ? <div className="app-chat-subitem app-chat-subitem--muted">加载中...</div>
              : chatState.error ? <button type="button" className="app-chat-subitem app-chat-subitem--error" onClick={loadChatSessions}>{chatState.error}</button>
                : chatSessions.length === 0 ? <div className="app-chat-subitem app-chat-subitem--muted">暂无对话</div>
                  : chatSessions.map((session) => (
                    <div key={session.session_id} className={`app-chat-subitem${activePath === "/chat" && activeSessionId === session.session_id ? " app-chat-subitem--active" : ""}`} role="button" tabIndex={0} onClick={() => openSession(session)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") openSession(session); }}>
                      <span className="app-chat-subitem__title">{session.title}</span>
                      <button type="button" className="app-chat-subitem__delete" aria-label={`删除对话 ${session.title}`} onClick={(event) => deleteSession(event, session)}><ShellIcon name="trash" size={13} /></button>
                    </div>
                  ))}
          </div>
        </section>

      </nav>

      <nav className="app-sidebar__bottom-nav" aria-label="业务导航">
        <NavLink active={activePath === "/files"} href="/files" icon="file" onNavigate={navigateAndClose}>文件管理</NavLink>
        <NavLink active={activePath === "/report"} href="/report" icon="report" onNavigate={navigateAndClose}>报告生成</NavLink>
      </nav>

      <div className="app-sidebar__account-menu" ref={accountMenuRef}>
        {accountMenuOpen && (
          <div className="app-sidebar__account-popover" role="menu" aria-label="账户快捷入口">
            <NavLink active={activePath === "/settings"} href="/settings" icon="settings" onNavigate={navigateFromAccountMenu}>设置</NavLink>
            <button type="button" className="app-user-menu__item app-user-menu__item--danger" onClick={logoutFromAccountMenu}><ShellIcon name="log-out" size={16} /><span>退出登录</span></button>
          </div>
        )}
        <button
          className={`app-sidebar__account${accountMenuOpen ? " app-sidebar__account--open" : ""}`}
          type="button"
          aria-haspopup="menu"
          aria-expanded={accountMenuOpen}
          onClick={() => setAccountMenuOpen((value) => !value)}
        >
          <UserAvatar user={auth?.user} />
          <span className="app-sidebar__account-copy"><strong>{userName}</strong><small>个人设置</small></span>
          <span className="app-sidebar__account-chevron"><ShellIcon name="chevron-down" size={14} /></span>
        </button>
      </div>
    </aside>
  );
}

export function TopBar({ title, showSearch = true, onNavigate, onLogout, onOpenMenu }) {
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const auth = getStoredAuth();
  const userName = auth?.user?.display_name || auth?.user?.username || auth?.user?.email || "用户";

  useEffect(() => {
    if (!userMenuOpen) return undefined;
    const close = (event) => { if (!event.target.closest(".app-user-menu")) setUserMenuOpen(false); };
    window.addEventListener("click", close);
    return () => window.removeEventListener("click", close);
  }, [userMenuOpen]);

  const focusSearch = () => {
    const input = document.querySelector('input[type="search"], .kb-search-box input, .fm-search input');
    if (input) input.focus();
    else window.dispatchEvent(new CustomEvent("docpilot:focus-search"));
  };

  return (
    <header className="app-topbar">
      <button className="app-topbar__menu-btn" type="button" aria-label="打开导航" onClick={onOpenMenu}><ShellIcon name="menu" size={21} /></button>
      <h1 className="app-topbar__title">{title}</h1>
      <div className="app-topbar__actions">
        {showSearch && <button className="app-topbar__icon-btn" type="button" aria-label="搜索当前页面" onClick={focusSearch}><ShellIcon name="search" size={18} /></button>}
        <div className="app-user-menu">
          <button type="button" className={`app-user-menu__trigger${userMenuOpen ? " app-user-menu__trigger--open" : ""}`} aria-expanded={userMenuOpen} aria-label="打开用户菜单" onClick={(event) => { event.stopPropagation(); setUserMenuOpen((value) => !value); }}>
            <UserAvatar user={auth?.user} /><ShellIcon name="chevron-down" size={14} />
          </button>
          {userMenuOpen && <div className="app-user-menu__dropdown">
            <div className="app-user-menu__identity"><strong>{userName}</strong>{auth?.user?.email && <span>{auth.user.email}</span>}</div>
            <button type="button" className="app-user-menu__item" onClick={() => { setUserMenuOpen(false); onNavigate("/settings"); }}><ShellIcon name="settings" size={16} /><span>设置</span></button>
            <button type="button" className="app-user-menu__item app-user-menu__item--danger" onClick={() => { setUserMenuOpen(false); onLogout(); }}><ShellIcon name="log-out" size={16} /><span>退出登录</span></button>
          </div>}
        </div>
      </div>
    </header>
  );
}

export default function AppShell({ activePath, title, onNavigate, onLogout, children }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [chatTitle, setChatTitle] = useState("新建对话");
  useEffect(() => { setMobileOpen(false); }, [activePath]);
  useEffect(() => {
    if (activePath !== "/chat") {
      setChatTitle("新建对话");
      return undefined;
    }

    setChatTitle(title || "新建对话");
    const handleChatTitleChanged = (event) => {
      setChatTitle(event.detail?.title?.trim() || "新建对话");
    };
    window.addEventListener("docpilot:chat-title-changed", handleChatTitleChanged);
    return () => window.removeEventListener("docpilot:chat-title-changed", handleChatTitleChanged);
  }, [activePath, title]);
  useEffect(() => {
    if (!mobileOpen) return undefined;
    const close = (event) => { if (event.key === "Escape") setMobileOpen(false); };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [mobileOpen]);
  return (
    <div className={`app-shell${mobileOpen ? " app-shell--mobile-open" : ""}`}>
      <Sidebar activePath={activePath} onNavigate={onNavigate} onClose={() => setMobileOpen(false)} onLogout={onLogout} />
      <button className="app-shell__scrim" type="button" aria-label="关闭导航" onClick={() => setMobileOpen(false)} />
      <div className="app-main-layout">
        <TopBar title={activePath === "/chat" ? chatTitle : title} showSearch={activePath !== "/chat"} onNavigate={onNavigate} onLogout={onLogout} onOpenMenu={() => setMobileOpen(true)} />
        <main className={`app-main-scroll${activePath === "/chat" ? " app-main-scroll--chat" : ""}`}>{children}</main>
      </div>
    </div>
  );
}
