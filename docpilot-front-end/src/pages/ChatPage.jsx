import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { getChatMessages, listChatSessions, streamChatCompletion } from "../api/chat";
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

const MARKDOWN_COMPONENTS = {
  table: ({ node: _node, ...props }) => (
    <div className="chat-markdown__table-wrap">
      <table {...props} />
    </div>
  ),
  a: ({ node: _node, href, children, ...props }) => {
    const isExternalLink = typeof href === "string" && /^(?:https?:)?\/\//i.test(href);
    return (
      <a
        {...props}
        href={href}
        target={isExternalLink ? "_blank" : undefined}
        rel={isExternalLink ? "noopener noreferrer" : undefined}
      >
        {children}
      </a>
    );
  },
};

function MarkdownMessage({ content }) {
  return (
    <div className="chat-message__content chat-markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        components={MARKDOWN_COMPONENTS}
      >
        {content}
      </ReactMarkdown>
    </div>
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
    status: "completed",
    chunks: normalizeUsedChunks(message.chunks || message.used_chunks || message.references || message.metadata?.used_chunks || []),
  }));
}

function normalizeUsedChunks(chunks) {
  if (!Array.isArray(chunks)) return [];
  return chunks
    .map((chunk, index) => {
      const rawChunkId = chunk.chunk_id ?? chunk.id;
      const rawDocumentId = chunk.document_id ?? chunk.documentId ?? chunk.metadata?.document_id;
      return {
        id: rawChunkId === undefined || rawChunkId === null || rawChunkId === ""
          ? String(index + 1)
          : String(rawChunkId),
        documentId: rawDocumentId === undefined || rawDocumentId === null || rawDocumentId === ""
          ? null
          : String(rawDocumentId),
        score: chunk.score,
        content: chunk.content || chunk.text || "",
      };
    })
    .filter((chunk) => chunk.content || chunk.id);
}

function formatChunkScore(score) {
  const numericScore = Number(score);
  return Number.isFinite(numericScore) ? numericScore.toFixed(3) : null;
}

export default function ChatPage({ onNavigate }) {
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([
    {
      id: "welcome",
      role: "assistant",
      content: WELCOME_MESSAGE,
      status: "completed",
    },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [chatSessions, setChatSessions] = useState([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [sessionTitleHint, setSessionTitleHint] = useState("");
  const [knowledgeBases, setKnowledgeBases] = useState([]);
  const [selectedKbId, setSelectedKbId] = useState("");
  const [kbLoading, setKbLoading] = useState(true);
  const [kbLoadFailed, setKbLoadFailed] = useState(false);
  const [sourceMessageId, setSourceMessageId] = useState(null);
  const [copyFeedback, setCopyFeedback] = useState(null);
  const endRef = useRef(null);
  const copyFeedbackTimerRef = useRef(null);

  const canSend = input.trim().length > 0 && !sending;
  const currentSession = useMemo(
    () => chatSessions.find((session) => String(session.session_id) === String(sessionId)),
    [chatSessions, sessionId]
  );
  const chatTitle = useMemo(() => {
    if (currentSession?.title?.trim()) return currentSession.title.trim();
    if (sessionTitleHint) return sessionTitleHint;
    const firstUserMessage = messages.find((message) => message.role === "user");
    return firstUserMessage?.content.trim().slice(0, 18) || "新建对话";
  }, [currentSession, messages, sessionTitleHint]);
  const hasConversation = useMemo(
    () => messages.some((message) => message.role === "user"),
    [messages]
  );
  const sourceMessage = useMemo(
    () => messages.find((message) => message.id === sourceMessageId),
    [messages, sourceMessageId]
  );
  const sourceChunks = Array.isArray(sourceMessage?.chunks) ? sourceMessage.chunks : [];
  const sourcesOpen = Boolean(sourceMessage);

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

  useEffect(() => () => {
    if (copyFeedbackTimerRef.current) {
      window.clearTimeout(copyFeedbackTimerRef.current);
    }
  }, []);

  useEffect(() => {
    let ignore = false;

    const loadKnowledgeBases = async () => {
      setKbLoading(true);
      setKbLoadFailed(false);
      try {
        const data = await getKnowledgeBases();
        const list = normalizeKnowledgeBases(data);
        if (!ignore) {
          setKnowledgeBases(list);
          setSelectedKbId((current) => current);
        }
      } catch (err) {
        if (!ignore) {
          setKbLoadFailed(true);
          setError(err.message || "加载知识库失败");
        }
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

  useEffect(() => {
    if (!sourcesOpen) return undefined;
    const closeOnEscape = (event) => {
      if (event.key === "Escape") setSourceMessageId(null);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [sourcesOpen]);

  useEffect(() => {
    if (sourceMessageId && !sourceMessage) {
      setSourceMessageId(null);
    }
  }, [sourceMessage, sourceMessageId]);

  useEffect(() => {
    window.dispatchEvent(new CustomEvent("docpilot:active-chat-session", {
      detail: { session_id: sessionId },
    }));
  }, [sessionId]);

  useEffect(() => {
    window.dispatchEvent(new CustomEvent("docpilot:chat-title-changed", {
      detail: { title: chatTitle },
    }));
  }, [chatTitle]);

  const startNewChat = () => {
    setSessionId(null);
    setSessionTitleHint("");
    setInput("");
    setError("");
    setSourceMessageId(null);
    setMessages([
      {
        id: "welcome",
        role: "assistant",
        content: "新的对话已开始。把问题、文档目标或报告需求发给我就行。",
        status: "completed",
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
    setSessionTitleHint(session.title?.trim() || "");
    setInput("");
    setError("");
    setSourceMessageId(null);

    try {
      const data = await getChatMessages(session.session_id);
      const historyMessages = Array.isArray(data?.messages) ? data.messages : [];
      const historyUiMessages = toUiMessages(session.session_id, historyMessages);
      setMessages(
        historyMessages.length
          ? historyUiMessages
          : [
              {
                id: "empty-history",
                role: "assistant",
                content: "这个历史对话还没有消息记录。",
                status: "completed",
              },
            ]
      );
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

  const handleCopyMessage = async (message) => {
    if (copyFeedbackTimerRef.current) {
      window.clearTimeout(copyFeedbackTimerRef.current);
    }

    let status = "copied";
    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error("Clipboard API unavailable");
      }
      await navigator.clipboard.writeText(message.content);
    } catch (_err) {
      status = "failed";
    }

    setCopyFeedback({ messageId: message.id, status });
    copyFeedbackTimerRef.current = window.setTimeout(() => {
      setCopyFeedback((current) => current?.messageId === message.id ? null : current);
      copyFeedbackTimerRef.current = null;
    }, 1600);
  };

  const sendMessage = async (nextInput = input) => {
    const text = nextInput.trim();
    if (!text || sending) return;

    const messageTimestamp = Date.now();
    const assistantId = `assistant-${messageTimestamp}`;
    const userMessage = {
      id: `user-${messageTimestamp}`,
      role: "user",
      content: text,
    };
    const assistantMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
      status: "pending",
      chunks: [],
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setInput("");
    setError("");
    setSending(true);

    let streamedAnswer = "";

    try {
      await streamChatCompletion({
        sessionId,
        message: text,
        kbId: selectedKbId,
        onMeta: (meta) => {
          if (meta?.session_id) {
            setSessionId(meta.session_id);
          }
          const normalizedChunks = normalizeUsedChunks(meta?.used_chunks || meta?.chunks || []);
          setMessages((prev) =>
            prev.map((message) =>
              message.id === assistantId
                ? { ...message, chunks: normalizedChunks }
                : message
            )
          );
        },
        onChunk: (chunk, chunks) => {
          const normalizedChunks = normalizeUsedChunks(chunks);
          streamedAnswer += chunk;
          setMessages((prev) =>
            prev.map((message) =>
              message.id === assistantId
                ? {
                    ...message,
                    content: streamedAnswer,
                    status: streamedAnswer ? "streaming" : message.status,
                    chunks: normalizedChunks.length > 0 ? normalizedChunks : message.chunks,
                  }
                : message
            )
          );
        },
      });

      setMessages((prev) =>
        prev.map((message) =>
          message.id === assistantId
            ? streamedAnswer.trim()
              ? { ...message, status: "completed" }
              : {
                  ...message,
                  content: "我没有收到有效回答，请稍后再试。",
                  status: "error",
                  error: true,
                }
            : message
        )
      );
      refreshChatSessions();
      window.dispatchEvent(new CustomEvent("docpilot:chat-sessions-changed"));
    } catch (err) {
      setError(err.message || "发送失败");
      setMessages((prev) =>
        prev.map((message) =>
          message.id === assistantId
            ? {
                ...message,
                content: "这次请求没有成功。请检查后端服务和模型配置后再试一次。",
                status: "error",
                error: true,
              }
            : message
        )
      );
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
    <div className={`chat-page${hasConversation ? " chat-page--reading" : " chat-page--welcome"}`}>
      <section className="chat-panel" aria-label={chatTitle}>
        {!hasConversation ? (
          <div className="chat-welcome">
            <span className="chat-welcome__mark"><SvgIcon name="sparkles" size={22} /></span>
            <h1>今天想处理什么？</h1>
            <p>询问文档、连接知识库，或把资料整理成一份清晰的报告。</p>
          </div>
        ) : (
          <div className="chat-messages">
            {messages.filter((message) => message.id !== "welcome").map((message) => (
              <article key={message.id} className={`chat-message chat-message--${message.role}${message.error ? " chat-message--error" : ""}`}>
                {message.role === "assistant" && message.status === "pending" && !message.content
                  ? <div className="chat-typing" aria-label="DocPilot 正在生成"><span /><span /><span /></div>
                  : message.role === "assistant"
                    ? <MarkdownMessage content={message.content} />
                    : <div className="chat-message__content">{message.content}</div>}
                {message.role === "assistant"
                  && message.status === "completed"
                  && !message.error
                  && message.id !== "empty-history"
                  && message.content && (
                    <div className="chat-message__actions" aria-label="回答操作">
                      <button
                        type="button"
                        className={"chat-message__action" + (
                          copyFeedback?.messageId === message.id
                            ? " is-" + copyFeedback.status
                            : ""
                        )}
                        onClick={() => handleCopyMessage(message)}
                      >
                        <span aria-live="polite">
                          {copyFeedback?.messageId === message.id
                            ? copyFeedback.status === "copied" ? "已复制" : "复制失败"
                            : "复制"}
                        </span>
                      </button>
                      {Array.isArray(message.chunks) && message.chunks.length > 0 && (
                        <button
                          type="button"
                          className="chat-message__action"
                          aria-haspopup="dialog"
                          aria-controls="chat-sources-drawer"
                          aria-expanded={sourceMessageId === message.id}
                          onClick={() => setSourceMessageId(message.id)}
                        >
                          引用来源 <span>· {message.chunks.length}</span>
                        </button>
                      )}
                    </div>
                  )}
              </article>
            ))}
            <div ref={endRef} />
          </div>
        )}

        <div className="chat-composer-zone">
          {error && <div className="chat-composer__error">{error}</div>}
          <div className="chat-composer__shell">
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="询问文档、知识库或生成报告…"
              rows={2}
            />
            <div className="chat-composer__footer">
              <div className="chat-composer__tools">
                {kbLoading ? (
                  <span className="chat-kb-status">知识库加载中</span>
                ) : kbLoadFailed ? (
                  <span className="chat-kb-status chat-kb-status--error">知识库加载失败</span>
                ) : knowledgeBases.length === 0 ? (
                  <div className="chat-kb-empty-state">
                    <span>未使用知识库</span>
                    <button type="button" onClick={() => onNavigate("/knowledge-base")}>创建知识库</button>
                  </div>
                ) : (
                  <select className="chat-kb-select" value={selectedKbId} onChange={(event) => setSelectedKbId(event.target.value)} title="选择知识库">
                    <option value="">不使用知识库</option>
                    {knowledgeBases.map((kb) => <option key={kb.id} value={String(kb.id)}>{kb.name || kb.title || `知识库 ${kb.id}`}</option>)}
                  </select>
                )}
              </div>
              <button className="chat-send-btn" type="button" aria-label="发送消息" disabled={!canSend} onClick={() => sendMessage()}><SvgIcon name="send" size={17} /></button>
            </div>
          </div>
          {!hasConversation && (
            <div className="chat-suggestions">
              {SUGGESTIONS.slice(0, 3).map((suggestion) => <button key={suggestion} type="button" onClick={() => sendMessage(suggestion)}>{suggestion}</button>)}
            </div>
          )}
          <p className="chat-composer__hint">DocPilot 可能会出错，请核对重要信息。</p>
        </div>
      </section>

      {sourcesOpen && (
        <div className="chat-sources-layer" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setSourceMessageId(null); }}>
          <aside id="chat-sources-drawer" className="chat-sources-drawer" role="dialog" aria-modal="true" aria-labelledby="chat-sources-title">
            <div className="chat-sources-drawer__header">
              <div>
                <h2 id="chat-sources-title">引用来源</h2>
                <p>本回答使用了 {sourceChunks.length} 条知识库内容</p>
              </div>
              <button type="button" aria-label="关闭引用来源" onClick={() => setSourceMessageId(null)}>×</button>
            </div>
            <div className="chat-chunks-list">
              {sourceChunks.length === 0 ? (
                <div className="chat-chunks-empty">
                  <p>暂无引用</p>
                  <span>本回答暂未关联可查看的知识库内容。</span>
                </div>
              ) : sourceChunks.map((chunk, index) => {
                const formattedScore = formatChunkScore(chunk.score);
                return (
                  <article className="chat-chunk-card" key={chunk.id + "-" + index}>
                    <div className="chat-chunk-card__top">
                      <span>引用 {index + 1}</span>
                      {formattedScore && <em>相关度：{formattedScore}</em>}
                    </div>
                    {chunk.documentId && <div className="chat-chunk-card__meta">文档 ID：{chunk.documentId}</div>}
                    <div className="chat-chunk-card__content">
                      <span>引用原文</span>
                      <p>{chunk.content}</p>
                    </div>
                  </article>
                );
              })}
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}
