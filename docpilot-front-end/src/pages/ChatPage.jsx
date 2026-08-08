import { useEffect, useMemo, useRef, useState } from "react";
import { createChatCompletion, deleteChatSession, getChatMessages, listChatSessions, streamChatCompletion } from "../api/chat";
import { getKnowledgeBases } from "../api/knowledgeBase";

function SvgIcon({ name, size = 20 }) {
  const paths = {
    plus: <><circle cx="12" cy="12" r="10" /><path d="M8 12h8M12 8v8" /></>,
    layers: <><path d="m12 3 9 5-9 5-9-5 9-5Z" /><path d="m4 12 8 4.5 8-4.5" /><path d="m4 16 8 4.5 8-4.5" /></>,
    file: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Z" /><path d="M14 2v6h6" /></>,
    settings: <><circle cx="12" cy="12" r="3" /><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" /></>,
    "chat-dot": <><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10Z" /><circle cx="12" cy="10" r="1" /></>,
    search: <><circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" /></>,
    "chevron-down": <><path d="m6 9 6 6 6-6" /></>,
    send: <><path d="m22 2-7 20-4-9-9-4 20-7Z" /><path d="M22 2 11 13" /></>,
    sparkles: <><path d="m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z" /><path d="M5 3v4M3 5h4M19 17v4M17 19h4" /></>,
    refresh: <><path d="M21 12a9 9 0 1 1-2.64-6.36" /><path d="M21 3v6h-6" /></>,
    trash: <><polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /></>,
    user: <><circle cx="12" cy="8" r="4" /><path d="M20 21a8 8 0 0 0-16 0" /></>,
  };

  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}

const WELCOME_MESSAGE = "你好，我是 DocPilot。你可以直接问问题，也可以让我帮你总结文档、梳理报告结构或生成写作草稿。";

const SUGGESTIONS = [
  "帮我总结这个知识库里的核心内容",
  "把上传的文档整理成一份报告大纲",
  "分析一下合同里可能存在的风险",
  "根据资料生成一段汇报开场白",
];

function normalizeKnowledgeBases(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.knowledge_bases)) return data.knowledge_bases;
  if (Array.isArray(data?.items)) return data.items;
  return [];
}

function toUiMessages(sessionId, messages) {
  return messages.map((message, index) => ({
    id: `${sessionId}-${index}-${message.role}`,
    role: message.role,
    content: message.content,
    chunks: normalizeUsedChunks(message.chunks || message.used_chunks || message.references || message.metadata?.used_chunks || []),
  }));
}

function normalizeUsedChunks(chunks) {
  if (!Array.isArray(chunks)) return [];
  return chunks
    .map((chunk, index) => ({
      id: String(chunk.chunk_id ?? chunk.id ?? index + 1),
      documentId: chunk.document_id ?? chunk.documentId ?? chunk.metadata?.document_id ?? "--",
      index: chunk.chunk_index ?? chunk.chunk_no ?? chunk.index ?? index + 1,
      score: chunk.score,
      content: chunk.content || chunk.text || "",
    }))
    .filter((chunk) => chunk.content || chunk.id);
}

function getLatestAssistantChunks(messages) {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message.role === "assistant" && Array.isArray(message.chunks) && message.chunks.length > 0) {
      return message.chunks;
    }
  }
  return [];
}

export default function ChatPage({ onNavigate }) {
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([
    {
      id: "welcome",
      role: "assistant",
      content: WELCOME_MESSAGE,
    },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [chatSessions, setChatSessions] = useState([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [knowledgeBases, setKnowledgeBases] = useState([]);
  const [selectedKbId, setSelectedKbId] = useState("");
  const [kbLoading, setKbLoading] = useState(false);
  const [streamMode, setStreamMode] = useState(false);
  const [usedChunks, setUsedChunks] = useState([]);
  const endRef = useRef(null);

  const canSend = input.trim().length > 0 && !sending;
  const currentSession = useMemo(
    () => chatSessions.find((session) => String(session.session_id) === String(sessionId)),
    [chatSessions, sessionId]
  );
  const chatTitle = useMemo(() => {
    if (currentSession?.title) return currentSession.title;
    const firstUserMessage = messages.find((message) => message.role === "user");
    return firstUserMessage?.content.slice(0, 18) || "新建对话";
  }, [currentSession, messages]);

  const refreshChatSessions = async () => {
    setSessionsLoading(true);
    try {
      const data = await listChatSessions();
      setChatSessions(Array.isArray(data?.sessions) ? data.sessions : []);
    } catch (err) {
      setError(err.message || "加载历史对话失败");
    } finally {
      setSessionsLoading(false);
    }
  };

  useEffect(() => {
    refreshChatSessions();
  }, []);

  useEffect(() => {
    let ignore = false;

    const loadKnowledgeBases = async () => {
      setKbLoading(true);
      try {
        const data = await getKnowledgeBases();
        const list = normalizeKnowledgeBases(data);
        if (!ignore) {
          setKnowledgeBases(list);
          setSelectedKbId((current) => current);
        }
      } catch (err) {
        if (!ignore) setError(err.message || "加载知识库失败");
      } finally {
        if (!ignore) setKbLoading(false);
      }
    };

    loadKnowledgeBases();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, sending]);

  const startNewChat = () => {
    setSessionId(null);
    setInput("");
    setError("");
    setUsedChunks([]);
    setMessages([
      {
        id: "welcome",
        role: "assistant",
        content: "新的对话已开始。把问题、文档目标或报告需求发给我就行。",
      },
    ]);
  };

  useEffect(() => {
    window.addEventListener("docpilot:new-chat", startNewChat);
    return () => window.removeEventListener("docpilot:new-chat", startNewChat);
  }, []);

  useEffect(() => {
    const handleDeletedSession = (event) => {
      if (String(event.detail?.session_id) === String(sessionId)) {
        startNewChat();
      }
    };

    window.addEventListener("docpilot:chat-session-deleted", handleDeletedSession);
    return () => window.removeEventListener("docpilot:chat-session-deleted", handleDeletedSession);
  }, [sessionId]);

  const openChatSession = async (session) => {
    setSessionId(session.session_id);
    setInput("");
    setError("");

    try {
      const data = await getChatMessages(session.session_id);
      const historyMessages = Array.isArray(data?.messages) ? data.messages : [];
      const historyUiMessages = toUiMessages(session.session_id, historyMessages);
      setMessages(
        historyMessages.length
          ? toUiMessages(session.session_id, historyMessages)
          : [
              {
                id: "empty-history",
                role: "assistant",
                content: "这个历史对话还没有消息记录。",
              },
            ]
      );
      setUsedChunks(getLatestAssistantChunks(historyUiMessages));
    } catch (err) {
      setError(err.message || "加载历史消息失败");
    }
  };

  useEffect(() => {
    const openPendingSession = () => {
      const raw = sessionStorage.getItem("docpilot_pending_chat_session");
      if (!raw) return;
      sessionStorage.removeItem("docpilot_pending_chat_session");
      try {
        const session = JSON.parse(raw);
        if (session?.session_id) openChatSession(session);
      } catch (_err) {
        // Ignore stale local navigation payloads.
      }
    };

    const handleOpenSession = (event) => {
      if (event.detail?.session_id) openChatSession(event.detail);
    };

    openPendingSession();
    window.addEventListener("docpilot:open-chat-session", handleOpenSession);
    return () => window.removeEventListener("docpilot:open-chat-session", handleOpenSession);
  }, [chatSessions]);

  const handleDeleteSession = async (event, session) => {
    event.preventDefault();
    event.stopPropagation();

    try {
      await deleteChatSession(session.session_id);
      setChatSessions((current) => current.filter((item) => String(item.session_id) !== String(session.session_id)));
      if (String(session.session_id) === String(sessionId)) {
        startNewChat();
      }
      window.dispatchEvent(new CustomEvent("docpilot:chat-sessions-changed"));
    } catch (err) {
      setError(err.message || "删除对话失败");
    }
  };

  const sendMessage = async (nextInput = input) => {
    const text = nextInput.trim();
    if (!text || sending) return;

    const userMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: text,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setError("");
    setUsedChunks([]);
    setSending(true);

    try {
      if (streamMode) {
        const assistantId = `assistant-${Date.now()}`;
        let streamedAnswer = "";

        setMessages((prev) => [
          ...prev,
          {
            id: assistantId,
            role: "assistant",
            content: "",
          },
        ]);

        await streamChatCompletion({
          sessionId,
          message: text,
          kbId: selectedKbId,
          onMeta: (meta) => {
            if (meta?.session_id) {
              setSessionId(meta.session_id);
            }
            const normalizedChunks = normalizeUsedChunks(meta?.used_chunks || meta?.chunks || []);
            if (normalizedChunks.length > 0) setUsedChunks(normalizedChunks);
          },
          onChunk: (chunk, chunks) => {
            const normalizedChunks = normalizeUsedChunks(chunks);
            if (normalizedChunks.length > 0) setUsedChunks(normalizedChunks);
            streamedAnswer += chunk;
            setMessages((prev) =>
              prev.map((message) =>
                message.id === assistantId
                  ? { ...message, content: streamedAnswer }
                  : message
              )
            );
          },
        });

        if (!streamedAnswer.trim()) {
          setMessages((prev) =>
            prev.map((message) =>
              message.id === assistantId
                ? { ...message, content: "我没有收到有效回答，请稍后再试。" }
                : message
            )
          );
        }
        refreshChatSessions();
        window.dispatchEvent(new CustomEvent("docpilot:chat-sessions-changed"));
        return;
      }

      const result = await createChatCompletion({
        sessionId,
        message: text,
        stream: false,
        kbId: selectedKbId,
      });
      if (result?.session_id) {
        setSessionId(result.session_id);
      }
      const normalizedChunks = normalizeUsedChunks(result?.used_chunks || result?.chunks || result?.references || []);
      setUsedChunks(normalizedChunks);
      setMessages((prev) => [
        ...prev,
        {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: result?.answer || "我没有收到有效回答，请稍后再试。",
        },
      ]);
      refreshChatSessions();
      window.dispatchEvent(new CustomEvent("docpilot:chat-sessions-changed"));
    } catch (err) {
      setError(err.message || "发送失败");
      setMessages((prev) => [
        ...prev,
        {
          id: `assistant-error-${Date.now()}`,
          role: "assistant",
          content: "这次请求没有成功。请检查后端服务和模型配置后再试一次。",
          error: true,
        },
      ]);
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="kb-page chat-page">
      <aside className="kb-sidebar">
        <div className="kb-sidebar__brand">
          <span className="kb-sidebar__logo" aria-hidden="true"><span /></span>
          <span className="kb-sidebar__name">DocPilot</span>
        </div>
        <button className="kb-sidebar__new-btn" onClick={startNewChat}>
          <SvgIcon name="plus" size={18} />
          <span>新建对话</span>
        </button>
        <nav className="kb-sidebar__nav">
          <a className="kb-nav-item" href="#" onClick={(e) => { e.preventDefault(); onNavigate("/knowledge-base"); }}>
            <SvgIcon name="layers" size={18} />
            <span>知识库</span>
          </a>
        </nav>
        <div className="kb-sidebar__section">
          <div className="kb-sidebar__divider" />
          <div className="kb-sidebar__section-title">最近对话</div>
          {sessionsLoading ? (
            <a className="kb-nav-item kb-nav-item--sub" href="#" onClick={(e) => e.preventDefault()}>
              <SvgIcon name="chat-dot" size={16} />
              <span>加载中...</span>
            </a>
          ) : chatSessions.length > 0 ? (
            chatSessions.map((session) => (
              <div
                key={session.session_id}
                className={`kb-nav-item kb-nav-item--sub chat-session-item${String(session.session_id) === String(sessionId) ? " kb-nav-item--active" : ""}`}
                role="button"
                tabIndex={0}
                onClick={(event) => {
                  event.preventDefault();
                  openChatSession(session);
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    openChatSession(session);
                  }
                }}
              >
                <SvgIcon name="chat-dot" size={16} />
                <span className="chat-session-title">{session.title || `对话 ${session.session_id}`}</span>
                <button
                  className="chat-session-delete"
                  type="button"
                  title="删除对话"
                  aria-label="删除对话"
                  onClick={(event) => handleDeleteSession(event, session)}
                >
                  <SvgIcon name="trash" size={14} />
                </button>
              </div>
            ))
          ) : (
            <div className="kb-nav-item kb-nav-item--sub kb-nav-item--active chat-session-item" role="button" tabIndex={0}>
              <SvgIcon name="chat-dot" size={16} />
              <span className="chat-session-title">{chatTitle}</span>
              <button
                className="chat-session-delete"
                type="button"
                title="删除对话"
                aria-label="删除对话"
                onClick={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  startNewChat();
                }}
              >
                <SvgIcon name="trash" size={14} />
              </button>
            </div>
          )}
        </div>
        <div className="kb-sidebar__footer">
          <div className="kb-sidebar__divider" />
          <a className="kb-nav-item" href="#" onClick={(e) => { e.preventDefault(); onNavigate("/files"); }}>
            <SvgIcon name="file" size={18} />
            <span>文件管理</span>
          </a>
          <a className="kb-nav-item" href="#" onClick={(e) => { e.preventDefault(); onNavigate("/settings"); }}>
            <SvgIcon name="settings" size={18} />
            <span>设置</span>
          </a>
        </div>
      </aside>

      <div className="kb-main">
        <header className="kb-topbar">
          <div className="kb-topbar__left">
            <span className="kb-topbar__label">当前对话：</span>
            <span className="kb-topbar__value">{chatTitle}</span>
          </div>
          <div className="kb-topbar__center">
            <span className="kb-topbar__label">接口：</span>
            <span className="kb-topbar__value">/api/chat/completions</span>
          </div>
          <div className="kb-topbar__right">
            <button className="kb-topbar__icon-btn" title="搜索"><SvgIcon name="search" size={20} /></button>
            <span className="kb-avatar" />
            <SvgIcon name="chevron-down" size={16} />
          </div>
        </header>

        <main className="chat-main">
          <div className="chat-layout">
          <section className="chat-panel">
            <div className="chat-hero">
              <span className="chat-hero__icon"><SvgIcon name="sparkles" size={24} /></span>
              <div>
                <h1>新建对话</h1>
                <p>围绕知识库问答、文档总结、报告生成开始一次新的协作。</p>
              </div>
              <button className="kb-btn kb-btn--outline" onClick={startNewChat}>
                <SvgIcon name="refresh" size={15} />
                <span>重置</span>
              </button>
            </div>

            <div className="chat-messages">
              {messages.map((message) => (
                <div key={message.id} className={`chat-message chat-message--${message.role}${message.error ? " chat-message--error" : ""}`}>
                  <div className="chat-message__avatar">
                    {message.role === "assistant" ? <SvgIcon name="sparkles" size={16} /> : <SvgIcon name="user" size={16} />}
                  </div>
                  <div className="chat-message__body">
                    <div className="chat-message__name">{message.role === "assistant" ? "DocPilot" : "你"}</div>
                    <div className="chat-message__content">{message.content}</div>
                  </div>
                </div>
              ))}
              {sending && (
                <div className="chat-message chat-message--assistant">
                  <div className="chat-message__avatar"><SvgIcon name="sparkles" size={16} /></div>
                  <div className="chat-message__body">
                    <div className="chat-message__name">DocPilot</div>
                    <div className="chat-typing"><span /><span /><span /></div>
                  </div>
                </div>
              )}
              <div ref={endRef} />
            </div>

            {messages.length <= 1 && (
              <div className="chat-suggestions">
                {SUGGESTIONS.map((suggestion) => (
                  <button key={suggestion} onClick={() => sendMessage(suggestion)}>
                    {suggestion}
                  </button>
                ))}
              </div>
            )}

            <div className="chat-composer">
              {error && <div className="chat-composer__error">{error}</div>}
              <div className="chat-composer__shell">
                <textarea
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="输入你的问题，按 Enter 发送，Shift + Enter 换行"
                  rows={1}
                />
                <div className="chat-composer__tools">
                  <select
                    className="chat-kb-select"
                    value={selectedKbId}
                    onChange={(event) => setSelectedKbId(event.target.value)}
                    disabled={kbLoading || knowledgeBases.length === 0}
                    title="选择知识库"
                  >
                    <option value="">{kbLoading ? "加载中" : "选择知识库"}</option>
                    {knowledgeBases.map((kb) => (
                      <option key={kb.id} value={String(kb.id)}>
                        {kb.name || kb.title || `知识库 ${kb.id}`}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className={`chat-stream-toggle${streamMode ? " is-active" : ""}`}
                    onClick={() => setStreamMode((current) => !current)}
                    aria-pressed={streamMode}
                    title="选择流式输出接口"
                  >
                    <span className="chat-stream-toggle__dot" />
                    {streamMode ? "流式" : "普通"}
                  </button>
                </div>
                <button className="chat-send-btn" disabled={!canSend} onClick={() => sendMessage()}>
                  <SvgIcon name="send" size={18} />
                </button>
              </div>
            </div>
          </section>
          <aside className="chat-chunks-panel" aria-label="Used chunks">
            <div className="chat-chunks-panel__header">
              <div>
                <h2>引用切片</h2>
                <p>本轮回答使用的 chunks</p>
              </div>
              <span>{usedChunks.length}</span>
            </div>
            <div className="chat-chunks-list">
              {usedChunks.length === 0 ? (
                <div className="chat-chunks-empty">
                  <p>暂无引用切片</p>
                  <span>发送知识库问题后，这里会显示检索到的 chunks。</span>
                </div>
              ) : (
                usedChunks.map((chunk, index) => (
                  <article className="chat-chunk-card" key={`${chunk.id}-${index}`}>
                    <div className="chat-chunk-card__top">
                      <span>Chunk #{chunk.index}</span>
                      {chunk.score !== undefined && chunk.score !== null && (
                        <em>{Number(chunk.score).toFixed(3)}</em>
                      )}
                    </div>
                    <div className="chat-chunk-card__meta">文档 ID：{chunk.documentId}</div>
                    <p>{chunk.content}</p>
                  </article>
                ))
              )}
            </div>
          </aside>
          </div>
        </main>
      </div>
    </div>
  );
}
