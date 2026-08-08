import { useCallback, useEffect, useMemo, useState } from "react";
import {
  getKnowledgeBases,
  getDocuments,
  createKnowledgeBase,
  deleteKnowledgeBase,
  rebuildKnowledgeBaseIndex,
  uploadKnowledgeBaseFile,
} from "../api/knowledgeBase";

/* ===============================================================
   Mock / fallback — for fields not yet in backend response
   TODO: remove when backend returns file_count, vector_count, embedding_model
   =============================================================== */
const MOCK_KB_META = {
  "论文知识库": { fileCount: 32, vectorCount: 8426, embeddingModel: "text-embedding-3-large", iconTone: "blue" },
  "项目文档库": { fileCount: 24, vectorCount: 5384, embeddingModel: "text-embedding-3-large", iconTone: "green" },
  "课程资料库": { fileCount: 18, vectorCount: 2713, embeddingModel: "text-embedding-3-large", iconTone: "purple" },
  "合同资料库": { fileCount: 12, vectorCount: 2019, embeddingModel: "text-embedding-3-large", iconTone: "orange" },
};

function getDefaultMeta(name) {
  const colors = ["blue", "green", "purple", "orange"];
  const hash = name.split("").reduce((a, c) => a + c.charCodeAt(0), 0);
  return {
    fileCount: Math.floor(Math.random() * 30) + 5,
    vectorCount: Math.floor(Math.random() * 6000) + 1000,
    embeddingModel: "text-embedding-3-large",
    iconTone: colors[hash % colors.length],
  };
}

/* ===============================================================
   Adapter: backend DTO → frontend KnowledgeBase type
   =============================================================== */
function toNumber(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function getDocumentChunkCount(doc) {
  return toNumber(doc.chunk_count ?? doc.chunks ?? doc.vector_count ?? doc.embedding_count, 0);
}

async function hydrateKnowledgeBaseStats(kb) {
  try {
    const documents = await getDocuments(kb.id);
    const list = Array.isArray(documents) ? documents : [];
    return {
      ...kb,
      fileCount: list.length,
      vectorCount: list.reduce((sum, doc) => sum + getDocumentChunkCount(doc), 0),
    };
  } catch (_err) {
    return kb;
  }
}

function mapKnowledgeBaseDTO(dto) {
  const name = dto.name || "未命名知识库";
  const meta = MOCK_KB_META[name] || getDefaultMeta(name);
  const rawStatus = (dto.status || "").toLowerCase();
  return {
    id: String(dto.id),
    name,
    description: dto.description || "",
    fileCount: meta.fileCount,
    vectorCount: meta.vectorCount,
    embeddingModel: meta.embeddingModel,
    iconTone: meta.iconTone,
    updatedAt: dto.updated_at || "",
    status: rawStatus === "active" ? "normal" : rawStatus === "deleted" ? "deleted" : "unknown",
  };
}

/* ===============================================================
   Icon color mapping
   =============================================================== */
const KB_COLORS = ["#2563eb", "#16a34a", "#7c3aed", "#f97316", "#0891b2", "#dc2626", "#ca8a04", "#9333ea"];

/* ===== SVG 图标组件 ===== */
function SvgIcon({ name, size = 20 }) {
  const s = size;
  const paths = {
    layers: <><path d="m12 3 9 5-9 5-9-5 9-5Z" /><path d="m4 12 8 4.5 8-4.5" /><path d="m4 16 8 4.5 8-4.5" /></>,
    book: <><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H19a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H6.5A2.5 2.5 0 0 1 4 19.5Z" /><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /></>,
    folder: <><path d="M4 20V4a2 2 0 0 1 2-2h5l4 4h5a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2Z" /></>,
    bookmark: <><path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16Z" /></>,
    file: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Z" /><path d="M14 2v6h6" /></>,
    chat: <><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10Z" /></>,
    "chat-dot": <><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10Z" /><circle cx="12" cy="10" r="1" /></>,
    plus: <><circle cx="12" cy="12" r="10" /><path d="M8 12h8M12 8v8" /></>,
    search: <><circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" /></>,
    user: <><circle cx="12" cy="8" r="4" /><path d="M20 21a8 8 0 0 0-16 0" /></>,
    "chevron-down": <><path d="m6 9 6 6 6-6" /></>,
    "chevron-right": <><path d="m9 18 6-6-6-6" /></>,
    database: <><ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" /><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" /></>,
    document: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Z" /><path d="M14 2v6h6M10 12h4M10 16h6" /></>,
    box: <><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" /></>,
    settings: <><circle cx="12" cy="12" r="3" /><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" /></>,
    upload: <><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></>,
    "refresh-cw": <><polyline points="23 4 23 10 17 10" /><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" /></>,
    trash: <><polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /></>,
    "arrow-right": <><line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" /></>,
    "more-h": <><circle cx="12" cy="12" r="1" /><circle cx="19" cy="12" r="1" /><circle cx="5" cy="12" r="1" /></>,
  };
  return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}

/* ===============================================================
   KnowledgeBasePage
   =============================================================== */
export default function KnowledgeBasePage({ onNavigate }) {
  // ---- data state ----
  const [kbs, setKbs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // ---- filter state ----
  const [searchText, setSearchText] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sortBy, setSortBy] = useState("updated");

  // ---- sidebar collapse ----
  const [kbCollapsed, setKbCollapsed] = useState(false);

  // ---- modal / action state ----
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createForm, setCreateForm] = useState({ name: "", description: "" });
  const [creating, setCreating] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null); // { id, name } | null
  const [deleting, setDeleting] = useState(false);
  const [actionLoading, setActionLoading] = useState({}); // { [id]: "rebuild" | "upload" }

  // ---- selected KB in top bar ----
  const [selectedKb, setSelectedKb] = useState(null);
  const [kbDropdownOpen, setKbDropdownOpen] = useState(false);

  // ---- fetch list ----
  const fetchList = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getKnowledgeBases();
      const mapped = Array.isArray(data) ? data.map(mapKnowledgeBaseDTO) : [];
      const withRealStats = await Promise.all(mapped.map(hydrateKnowledgeBaseStats));
      setKbs(withRealStats);
    } catch (err) {
      if (err.code === 401 || err.code === 403) {
        // Will be handled by App's auth check
        setError(err.message);
      } else {
        setError(err.message || "加载失败");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchList(); }, [fetchList]);

  // Set default selected KB when list loads
  useEffect(() => {
    if (kbs.length > 0 && !selectedKb) {
      setSelectedKb(kbs[0]);
    }
  }, [kbs, selectedKb]);

  // Close KB dropdown on outside click
  useEffect(() => {
    if (!kbDropdownOpen) return;
    const handler = (e) => {
      if (!e.target.closest(".kb-topbar__dropdown-trigger, .kb-topbar-dropdown")) {
        setKbDropdownOpen(false);
      }
    };
    document.addEventListener("click", handler);
    return () => document.removeEventListener("click", handler);
  }, [kbDropdownOpen]);

  // ---- filtered + sorted list ----
  const filteredKbs = useMemo(() => {
    let list = [...kbs];

    // search filter
    if (searchText.trim()) {
      const q = searchText.trim().toLowerCase();
      list = list.filter(
        (kb) => kb.name.toLowerCase().includes(q) || kb.description.toLowerCase().includes(q)
      );
    }

    // status filter
    if (statusFilter !== "all") {
      list = list.filter((kb) => kb.status === statusFilter);
    }

    // sort
    if (sortBy === "updated") {
      list.sort((a, b) => (b.updatedAt || "").localeCompare(a.updatedAt || ""));
    } else if (sortBy === "name") {
      list.sort((a, b) => a.name.localeCompare(b.name, "zh"));
    }

    return list;
  }, [kbs, searchText, statusFilter, sortBy]);

  // ---- overview stats ----
  const stats = useMemo(() => {
    const totalKB = kbs.length;
    const totalFiles = kbs.reduce((s, kb) => s + kb.fileCount, 0);
    const totalVectors = kbs.reduce((s, kb) => s + kb.vectorCount, 0);
    const latestUpdate = kbs.length
      ? kbs.reduce((a, b) => ((a.updatedAt || "") > (b.updatedAt || "") ? a : b))
      : null;
    const embeddingModel =
      kbs.length > 0
        ? [...new Set(kbs.map((kb) => kb.embeddingModel).filter(Boolean))].join(", ") || "text-embedding-3-large"
        : "-";
    const storageGB = (totalVectors * 0.00068).toFixed(1);
    return { totalKB, totalFiles, totalVectors, latestUpdate, embeddingModel, storageGB };
  }, [kbs]);

  // ---- create knowledge base ----
  const handleCreate = async (e) => {
    e.preventDefault();
    if (!createForm.name.trim()) return;
    setCreating(true);
    try {
      // TODO: workspace_id should be dynamic when multi-workspace is supported
      await createKnowledgeBase({ name: createForm.name.trim(), description: createForm.description.trim() });
      setShowCreateModal(false);
      setCreateForm({ name: "", description: "" });
      await fetchList();
    } catch (err) {
      alert(err.message || "创建失败");
    } finally {
      setCreating(false);
    }
  };

  // ---- delete knowledge base ----
  const handleDeleteConfirm = async () => {
    if (!deleteConfirm) return;
    setDeleting(true);
    try {
      await deleteKnowledgeBase(deleteConfirm.id);
      setDeleteConfirm(null);
      await fetchList();
    } catch (err) {
      alert(err.message || "删除失败");
    } finally {
      setDeleting(false);
    }
  };

  // ---- rebuild index ----
  const handleRebuild = async (kbId) => {
    if (!window.confirm("确定要重建该知识库的向量索引吗？")) return;
    setActionLoading((prev) => ({ ...prev, [kbId]: "rebuild" }));
    try {
      await rebuildKnowledgeBaseIndex(kbId);
      alert("重建索引任务已提交");
    } catch (err) {
      alert(err.message || "重建失败");
    } finally {
      setActionLoading((prev) => ({ ...prev, [kbId]: null }));
    }
  };

  // ---- upload file ----
  const [uploadingId, setUploadingId] = useState(null);

  const handleUpload = (kbId) => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".pdf,.doc,.docx,.txt,.md,.markdown";
    input.onchange = async (e) => {
      const file = e.target.files?.[0];
      if (!file) return;
      setUploadingId(kbId);
      try {
        await uploadKnowledgeBaseFile(kbId, file);
        alert("上传成功");
        await fetchList();
      } catch (err) {
        alert(err.message || "上传失败");
      } finally {
        setUploadingId(null);
      }
    };
    input.click();
  };

  // ---- navigate to detail ----
  const handleEnter = (kb) => {
    onNavigate(`/knowledge-base/${kb.id}`);
  };

  // ---- status label ----
  const statusLabel = { normal: "正常", deleted: "已删除", unknown: "未知" };

  // ---- icon tone colors ----
  const toneBg = { blue: "#dbeafe", green: "#dcfce7", purple: "#ede9fe", orange: "#ffedd5" };
  const toneFg = { blue: "#2563eb", green: "#16a34a", purple: "#7c3aed", orange: "#f97316" };

  /* ============================================================
     Render
     ============================================================ */
  return (
    <div className="kb-page">

      {/* ===== Sidebar ===== */}
      <aside className="kb-sidebar">
        {/* Logo */}
        <div className="kb-sidebar__brand">
          <span className="kb-sidebar__logo" aria-hidden="true">
            <span />
          </span>
          <span className="kb-sidebar__name">DocPilot</span>
        </div>

        {/* New chat button */}
        <button className="kb-sidebar__new-btn" onClick={() => onNavigate("/chat")}>
          <SvgIcon name="plus" size={18} />
          <span>新建对话</span>
        </button>

        {/* Nav list — 知识库可折叠 */}
        <nav className="kb-sidebar__nav">
          <a
            className="kb-nav-item kb-nav-item--active"
            href="#"
            onClick={(e) => { e.preventDefault(); onNavigate("/knowledge-base"); setKbCollapsed((v) => !v); }}
            style={{ cursor: "pointer" }}
          >
            <SvgIcon name="layers" size={18} />
            <span style={{ flex: 1 }}>知识库</span>
            <span className={`kb-chevron${kbCollapsed ? " kb-chevron--collapsed" : ""}`}>
              <SvgIcon name="chevron-down" size={14} />
            </span>
          </a>
          {!kbCollapsed && kbs.map((kb, i) => (
            <a
              key={kb.id}
              className="kb-nav-item kb-nav-item--sub"
              href="#"
              onClick={(e) => { e.preventDefault(); handleEnter(kb); }}
            >
              <span
                className="kb-dot-icon"
                style={{ background: KB_COLORS[i % KB_COLORS.length] }}
              />
              <span>{kb.name}</span>
            </a>
          ))}
        </nav>

        {/* Recent conversations */}
        <div className="kb-sidebar__section">
          <div className="kb-sidebar__divider" />
          <div className="kb-sidebar__section-title">最近对话</div>
          <a className="kb-nav-item kb-nav-item--sub" href="#" onClick={(e) => e.preventDefault()}>
            <SvgIcon name="chat-dot" size={16} />
            <span>RAG 架构设计</span>
          </a>
          <a className="kb-nav-item kb-nav-item--sub" href="#" onClick={(e) => e.preventDefault()}>
            <SvgIcon name="chat-dot" size={16} />
            <span>合同风险分析</span>
          </a>
          <a className="kb-nav-item kb-nav-item--sub" href="#" onClick={(e) => e.preventDefault()}>
            <SvgIcon name="chat-dot" size={16} />
            <span>文档总结</span>
          </a>
        </div>

        {/* Footer */}
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

      {/* ===== Main area ===== */}
      <div className="kb-main">

        {/* Top bar */}
        <header className="kb-topbar">
          <div className="kb-topbar__left" style={{ position: "relative" }}>
            <span className="kb-topbar__label">当前知识库：</span>
            <span className="kb-topbar__value kb-topbar__dropdown-trigger"
              onClick={() => setKbDropdownOpen(!kbDropdownOpen)}
              style={{ cursor: "pointer", userSelect: "none", display: "inline-flex", alignItems: "center", gap: 6 }}>
              {selectedKb?.name || "选择知识库"}
              <SvgIcon name="chevron-down" size={16} />
            </span>
            {kbDropdownOpen && (
              <div className="kb-topbar-dropdown">
                {kbs.map((kb, i) => (
                  <div
                    key={kb.id}
                    className={`kb-topbar-dropdown__item${selectedKb?.id === kb.id ? " kb-topbar-dropdown__item--active" : ""}`}
                    onClick={() => { setSelectedKb(kb); setKbDropdownOpen(false); onNavigate(`/knowledge-base/${kb.id}`); }}
                  >
                    <span className="kb-dot-icon" style={{ background: KB_COLORS[i % KB_COLORS.length] }} />
                    <span>{kb.name}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="kb-topbar__center">
            <span className="kb-topbar__label">模型：</span>
            <span className="kb-topbar__value">DeepSeek / GPT</span>
            <SvgIcon name="chevron-down" size={16} />
          </div>

          <div className="kb-topbar__right">
            <button className="kb-topbar__icon-btn" title="搜索">
              <SvgIcon name="search" size={20} />
            </button>
            <span className="kb-avatar" />
            <SvgIcon name="chevron-down" size={16} />
          </div>
        </header>

        {/* Content area */}
        <div className="kb-content">
          {/* ===== Left: Knowledge base list ===== */}
          <div className="kb-list-area">
            {/* Title row */}
            <div className="kb-list-header">
              <div>
                <h1 className="kb-list-title">知识库管理</h1>
                <p className="kb-list-subtitle">统一管理知识库、文档与向量索引</p>
              </div>
              <button className="kb-primary-btn" onClick={() => setShowCreateModal(true)}>
                <SvgIcon name="plus" size={16} />
                <span>新建知识库</span>
              </button>
            </div>

            {/* Toolbar */}
            <div className="kb-toolbar">
              <div className="kb-search-box">
                <SvgIcon name="search" size={16} />
                <input
                  type="text"
                  placeholder="搜索知识库名称..."
                  value={searchText}
                  onChange={(e) => setSearchText(e.target.value)}
                />
              </div>
              <div className="kb-select" onClick={() => setStatusFilter(statusFilter === "all" ? "normal" : "all")}>
                <span>状态：{statusFilter === "all" ? "全部" : "正常"}</span>
                <SvgIcon name="chevron-down" size={14} />
              </div>
              <div className="kb-select" onClick={() => setSortBy(sortBy === "updated" ? "name" : "updated")}>
                <span>排序：{sortBy === "updated" ? "最近更新" : "名称"}</span>
                <SvgIcon name="chevron-down" size={14} />
              </div>
            </div>

            {/* Loading */}
            {loading ? (
              <div className="kb-loading">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="kb-skeleton kb-card" />
                ))}
              </div>
            ) : error ? (
              /* Error */
              <div className="kb-empty">
                <p style={{ color: "#ef4444", marginBottom: 12 }}>{error}</p>
                <button className="kb-primary-btn" onClick={fetchList}>重试</button>
              </div>
            ) : filteredKbs.length === 0 ? (
              /* Empty */
              <div className="kb-empty">
                <p>{searchText ? "没有匹配的知识库" : "暂无知识库"}</p>
                {!searchText && (
                  <button className="kb-primary-btn" onClick={() => setShowCreateModal(true)}>
                    新建知识库
                  </button>
                )}
              </div>
            ) : (
              /* List */
              <div className="kb-card-list">
                {filteredKbs.map((kb) => (
                  <div key={kb.id} className="kb-card">
                    <div className="kb-card__top">
                      <div className="kb-card__icon" style={{ background: toneBg[kb.iconTone], color: toneFg[kb.iconTone] }}>
                        <SvgIcon name="layers" size={24} />
                      </div>
                      <div className="kb-card__info">
                        <div className="kb-card__name">{kb.name}</div>
                        <div className="kb-card__desc">{kb.description}</div>
                      </div>
                      <div className="kb-card__actions">
                        <span className="kb-status-tag" style={{ background: "#dcfce7", color: "#16a34a" }}>
                          {statusLabel[kb.status] || kb.status}
                        </span>
                        <button className="kb-action-btn kb-action-btn--enter" onClick={() => handleEnter(kb)}>
                          <SvgIcon name="arrow-right" size={14} />
                          <span>进入</span>
                        </button>
                        <button className="kb-action-btn" title="更多" onClick={() => console.log("more", kb.id)}>
                          <SvgIcon name="more-h" size={16} />
                        </button>
                      </div>
                    </div>
                    <div className="kb-card__meta">
                      <span className="kb-meta-item">
                        <span className="kb-meta-label">文件数</span>
                        <span className="kb-meta-value">{kb.fileCount}</span>
                      </span>
                      <span className="kb-meta-divider" />
                      <span className="kb-meta-item">
                        <span className="kb-meta-label">向量数</span>
                        <span className="kb-meta-value">{kb.vectorCount.toLocaleString()}</span>
                      </span>
                      <span className="kb-meta-divider" />
                      <span className="kb-meta-item">
                        <span className="kb-meta-label">Embedding 模型</span>
                        <span className="kb-meta-value">{kb.embeddingModel}</span>
                      </span>
                      <span className="kb-meta-divider" />
                      <span className="kb-meta-item">
                        <span className="kb-meta-label">最近更新</span>
                        <span className="kb-meta-value">{kb.updatedAt ? kb.updatedAt.replace("T", " ").slice(0, 16) : "-"}</span>
                      </span>
                    </div>
                    <div className="kb-card__bottom-actions">
                      <button className="kb-action-btn" disabled={uploadingId === kb.id} onClick={() => handleUpload(kb.id)}>
                        <SvgIcon name="upload" size={14} />
                        <span>{uploadingId === kb.id ? "上传中..." : "上传文件"}</span>
                      </button>
                      <button
                        className="kb-action-btn"
                        disabled={actionLoading[kb.id] === "rebuild"}
                        onClick={() => handleRebuild(kb.id)}
                      >
                        <SvgIcon name="refresh-cw" size={14} />
                        <span>{actionLoading[kb.id] === "rebuild" ? "重建中..." : "重建索引"}</span>
                      </button>
                      <button
                        className="kb-action-btn kb-action-btn--danger"
                        onClick={() => setDeleteConfirm({ id: kb.id, name: kb.name })}
                      >
                        <SvgIcon name="trash" size={14} />
                        <span>删除</span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Pagination */}
            <div className="kb-pagination">
              <span className="kb-pagination__info">共 {filteredKbs.length} 个知识库</span>
              <div className="kb-pagination__controls">
                <button className="kb-page-btn" disabled>上一页</button>
                <button className="kb-page-btn kb-page-btn--active">1</button>
                <button className="kb-page-btn" disabled>下一页</button>
              </div>
            </div>
          </div>

          {/* ===== Right: Overview panel ===== */}
          <aside className="kb-overview">
            <div className="kb-overview-card">
              <h3 className="kb-overview__title">知识库概览</h3>

              {/* Stats */}
              <div className="kb-stat-grid">
                <div className="kb-stat-item">
                  <span className="kb-stat-icon" style={{ background: "#dbeafe", color: "#2563eb" }}>
                    <SvgIcon name="database" size={20} />
                  </span>
                  <div>
                    <div className="kb-stat-label">知识库总数</div>
                    <div className="kb-stat-value">{stats.totalKB}</div>
                  </div>
                </div>
                <div className="kb-stat-item">
                  <span className="kb-stat-icon" style={{ background: "#dcfce7", color: "#16a34a" }}>
                    <SvgIcon name="document" size={20} />
                  </span>
                  <div>
                    <div className="kb-stat-label">文档总数</div>
                    <div className="kb-stat-value">{stats.totalFiles}</div>
                  </div>
                </div>
                <div className="kb-stat-item">
                  <span className="kb-stat-icon" style={{ background: "#ede9fe", color: "#7c3aed" }}>
                    <SvgIcon name="box" size={20} />
                  </span>
                  <div>
                    <div className="kb-stat-label">向量片段</div>
                    <div className="kb-stat-value">{stats.totalVectors.toLocaleString()}</div>
                  </div>
                </div>
              </div>

              {/* Storage */}
              <div className="kb-overview-section">
                <div className="kb-overview-section__header">存储使用</div>
                <div className="kb-storage-bar">
                  <div className="kb-storage-bar__track">
                    <div className="kb-storage-bar__fill" style={{ width: "12.6%" }} />
                  </div>
                  <span className="kb-storage-bar__label">{stats.storageGB} GB / 100 GB</span>
                </div>
              </div>

              {/* Embedding model */}
              <div className="kb-overview-section">
                <div className="kb-overview-section__header">Embedding 模型</div>
                <div className="kb-overview-row">
                  <span className="kb-overview-value">{stats.embeddingModel}</span>
                  <span className="kb-dot" style={{ background: "#16a34a" }} />
                  <span style={{ color: "#16a34a", fontSize: 13 }}>正常</span>
                </div>
              </div>

              {/* Recent update */}
              <div className="kb-overview-section">
                <div className="kb-overview-row" style={{ justifyContent: "space-between" }}>
                  <div className="kb-overview-section__header">最近更新</div>
                  <button className="kb-action-btn" title="刷新" onClick={fetchList}>
                    <SvgIcon name="refresh-cw" size={14} />
                  </button>
                </div>
                <div className="kb-overview-value">
                  {stats.latestUpdate
                    ? (() => {
                        const diff = Date.now() - new Date(stats.latestUpdate.updatedAt).getTime();
                        const mins = Math.floor(diff / 60000);
                        if (mins < 1) return "刚刚";
                        if (mins < 60) return `${mins} 分钟前`;
                        const hrs = Math.floor(mins / 60);
                        if (hrs < 24) return `${hrs} 小时前`;
                        return stats.latestUpdate.updatedAt.replace("T", " ").slice(0, 10);
                      })()
                    : "-"}
                </div>
              </div>
            </div>
          </aside>
        </div>
      </div>

      {/* ===== Create modal ===== */}
      {showCreateModal && (
        <div className="kb-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="kb-modal" onClick={(e) => e.stopPropagation()}>
            <h3 className="kb-modal__title">新建知识库</h3>
            <form onSubmit={handleCreate}>
              <div className="kb-modal__field">
                <label>知识库名称</label>
                <input
                  type="text"
                  placeholder="请输入知识库名称"
                  value={createForm.name}
                  onChange={(e) => setCreateForm((f) => ({ ...f, name: e.target.value }))}
                  autoFocus
                />
              </div>
              <div className="kb-modal__field">
                <label>描述（可选）</label>
                <textarea
                  placeholder="请输入知识库描述"
                  rows={3}
                  value={createForm.description}
                  onChange={(e) => setCreateForm((f) => ({ ...f, description: e.target.value }))}
                />
              </div>
              <div className="kb-modal__actions">
                <button type="button" className="kb-btn kb-btn--outline" onClick={() => setShowCreateModal(false)}>
                  取消
                </button>
                <button type="submit" className="kb-btn kb-btn--primary" disabled={creating || !createForm.name.trim()}>
                  {creating ? "创建中..." : "创建"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ===== Delete confirm ===== */}
      {deleteConfirm && (
        <div className="kb-overlay" onClick={() => setDeleteConfirm(null)}>
          <div className="kb-modal" onClick={(e) => e.stopPropagation()}>
            <h3 className="kb-modal__title">删除知识库</h3>
            <p style={{ color: "#64748b", fontSize: 15, lineHeight: 1.6, margin: "8px 0 20px" }}>
              确定要删除「{deleteConfirm.name}」吗？此操作不可撤销。
            </p>
            <div className="kb-modal__actions">
              <button type="button" className="kb-btn kb-btn--outline" onClick={() => setDeleteConfirm(null)}>
                取消
              </button>
              <button
                type="button"
                className="kb-btn kb-btn--danger"
                disabled={deleting}
                onClick={handleDeleteConfirm}
              >
                {deleting ? "删除中..." : "确认删除"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
