import { useCallback, useEffect, useMemo, useState } from "react";
import {
  getKnowledgeBase,
  deleteKnowledgeBase,
  updateKnowledgeBase,
  rebuildKnowledgeBaseIndex,
  uploadKnowledgeBaseFile,
  getDocuments,
  deleteDocument,
  retryDocument,
} from "../api/knowledgeBase";

/* ===============================================================
   Adapter: backend KB detail DTO → frontend type
   =============================================================== */
function mapKBDetailDTO(dto) {
  return {
    id: String(dto.id),
    name: dto.name || "未命名知识库",
    description: dto.description || "",
    status: (dto.status || "").toLowerCase() === "active" ? "normal" : "unknown",
    updatedAt: dto.updated_at || "",
    createdAt: dto.created_at || "",
    // TODO: replace with real fields when backend returns them
    fileCount: null,
    chunkCount: null,
    embeddingModel: dto.embedding_model || null,
  };
}

/* ===============================================================
   Adapter: backend document DTO → frontend type
   TODO: implement when backend document API is available
   =============================================================== */
const STATUS_LABEL = {
  vectorized: "已向量化",
  indexed: "已向量化",
  completed: "已向量化",
  processing: "处理中",
  parsing: "处理中",
  chunking: "处理中",
  embedding: "处理中",
  failed: "失败",
  pending: "等待中",
  not_indexed: "等待中",
};
const STATUS_COLOR = {
  vectorized: "#16a34a",
  indexed: "#16a34a",
  completed: "#16a34a",
  processing: "#2563eb",
  parsing: "#2563eb",
  chunking: "#2563eb",
  embedding: "#2563eb",
  failed: "#ef4444",
  pending: "#94a3b8",
  not_indexed: "#94a3b8",
};

const FILE_TYPE_COLORS = {
  pdf: { bg: "#fef2f2", fg: "#dc2626", label: "PDF" },
  md: { bg: "#f1f5f9", fg: "#334155", label: "MD" },
  markdown: { bg: "#f1f5f9", fg: "#334155", label: "MD" },
  doc: { bg: "#eff6ff", fg: "#2563eb", label: "DOC" },
  docx: { bg: "#eff6ff", fg: "#2563eb", label: "DOCX" },
  txt: { bg: "#f8fafc", fg: "#64748b", label: "TXT" },
};

function getFileTypeMeta(ext) {
  const key = (ext || "").toLowerCase().replace(/^\./, "");
  return FILE_TYPE_COLORS[key] || { bg: "#f8fafc", fg: "#64748b", label: key.toUpperCase() || "FILE" };
}

function mapParseStatus(s) {
  const lower = (s || "").toLowerCase();
  if (lower === "success" || lower === "indexed" || lower === "completed" || lower === "vectorized") return "completed";
  if (lower === "processing" || lower === "parsing" || lower === "chunking" || lower === "embedding" || lower === "indexing") return "processing";
  if (lower === "failed" || lower === "error") return "failed";
  return "pending";
}

/* ===== SVG Icon ===== */
function SvgIcon({ name, size = 20 }) {
  const s = size;
  const paths = {
    layers: <><path d="m12 3 9 5-9 5-9-5 9-5Z" /><path d="m4 12 8 4.5 8-4.5" /><path d="m4 16 8 4.5 8-4.5" /></>,
    "chevron-right": <><path d="m9 18 6-6-6-6" /></>,
    edit: <><path d="M17 3a2.85 2.85 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" /></>,
    upload: <><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></>,
    "refresh-cw": <><polyline points="23 4 23 10 17 10" /><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" /></>,
    trash: <><polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /></>,
    search: <><circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" /></>,
    file: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Z" /><path d="M14 2v6h6" /></>,
    eye: <><path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z" /><circle cx="12" cy="12" r="2.5" /></>,
    "more-h": <><circle cx="12" cy="12" r="1" /><circle cx="19" cy="12" r="1" /><circle cx="5" cy="12" r="1" /></>,
    database: <><ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" /><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" /></>,
    document: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Z" /><path d="M14 2v6h6M10 12h4M10 16h6" /></>,
    box: <><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" /></>,
    clock: <><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></>,
    check: <><polyline points="20 6 9 17 4 12" /></>,
    loader: <><line x1="12" y1="2" x2="12" y2="6" /><line x1="12" y1="18" x2="12" y2="22" /><line x1="4.93" y1="4.93" x2="7.76" y2="7.76" /><line x1="16.24" y1="16.24" x2="19.07" y2="19.07" /><line x1="2" y1="12" x2="6" y2="12" /><line x1="18" y1="12" x2="22" y2="12" /><line x1="4.93" y1="19.07" x2="7.76" y2="16.24" /><line x1="16.24" y1="7.76" x2="19.07" y2="4.93" /></>,
    "chevron-down": <><path d="m6 9 6 6 6-6" /></>,
    plus: <><circle cx="12" cy="12" r="10" /><path d="M8 12h8M12 8v8" /></>,
    "arrow-up": <><line x1="12" y1="19" x2="12" y2="5" /><polyline points="5 12 12 5 19 12" /></>,
    "chat-dot": <><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10Z" /><circle cx="12" cy="10" r="1" /></>,
    settings: <><circle cx="12" cy="12" r="3" /><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" /></>,
  };
  return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[name] || <rect x="3" y="3" width="18" height="18" rx="2" />}
    </svg>
  );
}

/* ===============================================================
   KnowledgeBaseDetailPage
   =============================================================== */
export default function KnowledgeBaseDetailPage({ onNavigate }) {
  // Extract KB id from URL path: /knowledge-base/:id
  const kbId = useMemo(() => {
    const parts = window.location.pathname.split("/").filter(Boolean);
    return parts[parts.length - 1] || null;
  }, []);

  // ---- State ----
  const [kb, setKb] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [notFound, setNotFound] = useState(false);

  // docs from backend
  const [docs, setDocs] = useState([]);
  const [docLoading, setDocLoading] = useState(false);
  const [docError, setDocError] = useState(null);

  // modals
  const [showEditModal, setShowEditModal] = useState(false);
  const [editForm, setEditForm] = useState({ name: "", description: "" });
  const [saving, setSaving] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [uploading, setUploading] = useState(false);

  // ---- Fetch KB detail ----
  const fetchDetail = useCallback(async () => {
    if (!kbId) return;
    setLoading(true);
    setError(null);
    setNotFound(false);
    try {
      const data = await getKnowledgeBase(kbId);
      setKb(mapKBDetailDTO(data));
    } catch (err) {
      if (err.code === 401 || err.code === 403) {
        setError(err.message);
      } else if (err.message?.includes("404") || err.message?.includes("不存在")) {
        setNotFound(true);
      } else {
        setError(err.message || "加载失败");
      }
    } finally {
      setLoading(false);
    }
  }, [kbId]);

  useEffect(() => { fetchDetail(); }, [fetchDetail]);

  // ---- Fetch documents ----
  const fetchDocuments = useCallback(async () => {
    if (!kbId) return;
    setDocLoading(true);
    setDocError(null);
    try {
      const data = await getDocuments(kbId);
      const mapped = Array.isArray(data) ? data.map((d) => ({
        id: String(d.id ?? ""),
        name: d.name || "未命名文件",
        ext: d.type || "",
        status: mapParseStatus(d.status || ""),
        uploadedAt: d.updated_at || "",
        chunkCount: typeof d.chunks === "number" ? d.chunks : "--",
      })) : [];
      setDocs(mapped);
    } catch (err) {
      setDocError(err.message || "文件列表加载失败");
      setDocs([]);
    } finally {
      setDocLoading(false);
    }
  }, [kbId]);

  useEffect(() => { fetchDocuments(); }, [fetchDocuments]);

  // ---- Edit KB ----
  const handleOpenEdit = () => {
    if (!kb) return;
    setEditForm({ name: kb.name, description: kb.description });
    setShowEditModal(true);
  };

  const handleSaveEdit = async (e) => {
    e.preventDefault();
    if (!editForm.name.trim()) return;
    setSaving(true);
    try {
      await updateKnowledgeBase(kbId, editForm);
      setShowEditModal(false);
      await fetchDetail();
    } catch (err) {
      alert(err.message || "保存失败");
    } finally {
      setSaving(false);
    }
  };

  // ---- Delete KB ----
  const handleDeleteKB = async () => {
    setDeleting(true);
    try {
      await deleteKnowledgeBase(kbId);
      onNavigate("/knowledge-base", { replace: true });
    } catch (err) {
      alert(err.message || "删除失败");
    } finally {
      setDeleting(false);
      setDeleteConfirm(false);
    }
  };

  // ---- Rebuild index ----
  const handleRebuild = async () => {
    if (!window.confirm("确定要重建该知识库的向量索引吗？")) return;
    setActionLoading(true);
    try {
      await rebuildKnowledgeBaseIndex(kbId);
      alert("重建索引任务已提交");
    } catch (err) {
      alert(err.message || "重建失败");
    } finally {
      setActionLoading(false);
    }
  };

  // ---- Upload file ----
  const handleUpload = () => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".pdf,.doc,.docx,.txt,.md,.markdown";
    input.onchange = async (e) => {
      const file = e.target.files?.[0];
      if (!file) return;
      setUploading(true);
      try {
        await uploadKnowledgeBaseFile(kbId, file);
        alert("上传成功");
        if (fetchDetail) fetchDetail();
        if (fetchDocuments) fetchDocuments();
      } catch (err) {
        alert(err.message || "上传失败");
      } finally {
        setUploading(false);
      }
    };
    input.click();
  };

  // ---- View document (placeholder) ----
  const handleViewDoc = (doc) => {
    alert(`文件预览功能待接入 — ${doc.id}`);
  };

  // ---- Delete document ----
  const handleDeleteDoc = async (doc) => {
    if (!window.confirm(`确定要删除「${doc.name}」吗？`)) return;
    try {
      await deleteDocument(kbId, doc.id);
      setDocs((prev) => prev.filter((d) => d.id !== doc.id));
      alert("删除成功");
    } catch (err) {
      alert(err.message);
    }
  };

  // ---- Retry document (placeholder) ----
  const handleRetryDoc = async (doc) => {
    try {
      await retryDocument(doc.id);
    } catch (err) {
      alert(err.message);
    }
  };

  // ---- Aggregate stats ----
  const stats = useMemo(() => {
    const fileCount = docs.length || "--";
    const chunkCount = docs.reduce((sum, d) => sum + (typeof d.chunkCount === "number" ? d.chunkCount : 0), 0) || "--";
    const latestUpdated = docs.reduce((latest, d) => (d.uploadedAt > (latest || "") ? d.uploadedAt : latest), null);
    const updatedLabel = latestUpdated
      ? (() => {
          const diff = Date.now() - new Date(latestUpdated).getTime();
          const mins = Math.floor(diff / 60000);
          if (mins < 1) return "刚刚";
          if (mins < 60) return `${mins} 分钟前`;
          const hrs = Math.floor(mins / 60);
          if (hrs < 24) return `${hrs} 小时前`;
          return latestUpdated.replace("T", " ").slice(0, 10);
        })()
      : kb?.updatedAt
        ? (() => {
            const diff = Date.now() - new Date(kb.updatedAt).getTime();
            const mins = Math.floor(diff / 60000);
            if (mins < 1) return "刚刚";
            if (mins < 60) return `${mins} 分钟前`;
            const hrs = Math.floor(mins / 60);
            if (hrs < 24) return `${hrs} 小时前`;
            return kb.updatedAt.replace("T", " ").slice(0, 10);
          })()
        : "--";
    return { fileCount, chunkCount, updatedLabel };
  }, [kb, docs]);

  // ---- Upload task (placeholder) ----
  const task = useMemo(() => {
    // TODO: replace with real task progress when backend endpoint is available
    const processingDoc = docs.find((d) => d.status === "processing" || d.status === "pending");
    if (!processingDoc) return null;
    return {
      fileName: processingDoc.name,
      uploadedAt: processingDoc.uploadedAt,
      parseProgress: processingDoc.status === "processing" ? 100 : 0,
      splitProgress: processingDoc.status === "processing" ? 68 : 0,
      embeddingProgress: processingDoc.status === "processing" ? 0 : 0,
      parseStatus: processingDoc.status === "processing" ? "success" : "pending",
      splitStatus: processingDoc.status === "processing" ? "processing" : "pending",
      embeddingStatus: "pending",
    };
  }, [docs]);

  /* ============================================================
     Render
     ============================================================ */

  // Loading
  if (loading) {
    return (
      <div className="kb-detail-page">
        <aside className="kb-sidebar">{/* sidebar skeleton — sidebar not visible here, but kept for layout */}</aside>
        <div className="kb-main">
          <header className="kb-topbar" />
          <div className="kb-detail-content">
            <div className="kb-loading">
              {[1, 2, 3].map((i) => <div key={i} className="kb-skeleton" style={{ height: 100, marginBottom: 16 }} />)}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Not found
  if (notFound) {
    return (
      <div className="kb-detail-page">
        <div className="kb-detail-content" style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div className="kb-empty">
            <p style={{ fontSize: 18, marginBottom: 8 }}>知识库不存在</p>
            <p style={{ color: "#64748b", marginBottom: 16 }}>该知识库可能已被删除或您没有访问权限</p>
            <button className="kb-primary-btn" onClick={() => onNavigate("/knowledge-base")}>返回知识库列表</button>
          </div>
        </div>
      </div>
    );
  }

  // Error
  if (error) {
    return (
      <div className="kb-detail-page">
        <div className="kb-detail-content" style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div className="kb-empty">
            <p style={{ color: "#ef4444", marginBottom: 12 }}>{error}</p>
            <button className="kb-primary-btn" onClick={fetchDetail}>重试</button>
            <button className="kb-btn kb-btn--outline" style={{ marginLeft: 12 }} onClick={() => onNavigate("/knowledge-base")}>返回</button>
          </div>
        </div>
      </div>
    );
  }

  if (!kb) return null;

  return (
    <div className="kb-detail-page">
      {/* ===== Sidebar ===== */}
      <aside className="kb-sidebar">
        <div className="kb-sidebar__brand">
          <span className="kb-sidebar__logo" aria-hidden="true"><span /></span>
          <span className="kb-sidebar__name">DocPilot</span>
        </div>
        <button className="kb-sidebar__new-btn">
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

      {/* ===== Main ===== */}
      <div className="kb-main">
        <header className="kb-topbar">
          <div className="kb-topbar__left">
            <span className="kb-topbar__label">当前知识库：</span>
            <span className="kb-topbar__value">{kb.name}</span>
            <SvgIcon name="chevron-down" size={16} />
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

        <div className="kb-detail-content">
          {/* ===== Breadcrumb ===== */}
          <div className="kb-detail-breadcrumb">
            <button className="kb-breadcrumb-link" onClick={() => onNavigate("/knowledge-base")}>知识库</button>
            <SvgIcon name="chevron-right" size={14} />
            <span className="kb-breadcrumb-current">{kb.name}</span>
          </div>

          {/* ===== Header ===== */}
          <div className="kb-detail-header">
            <div className="kb-detail-header__icon" style={{ background: "linear-gradient(135deg, #60a5fa, #2563eb)" }}>
              <SvgIcon name="layers" size={28} color="#fff" />
            </div>
            <div className="kb-detail-header__info">
              <div className="kb-detail-header__title-row">
                <h1 className="kb-detail-header__title">{kb.name}</h1>
                <button className="kb-icon-btn" title="编辑" onClick={handleOpenEdit}>
                  <SvgIcon name="edit" size={16} />
                </button>
              </div>
              <p className="kb-detail-header__desc">{kb.description || "暂无描述"}</p>
            </div>
            <div className="kb-detail-header__actions">
              <button className="kb-primary-btn" disabled={uploading} onClick={handleUpload}>
                <SvgIcon name="upload" size={15} />
                <span>{uploading ? "上传中..." : "上传文件"}</span>
              </button>
              <button className="kb-btn kb-btn--outline" disabled={actionLoading} onClick={handleRebuild}>
                <SvgIcon name="refresh-cw" size={15} />
                <span>{actionLoading ? "重建中..." : "重建索引"}</span>
              </button>
              <button className="kb-btn kb-btn--danger" onClick={() => setDeleteConfirm(true)}>
                <SvgIcon name="trash" size={15} />
                <span>删除知识库</span>
              </button>
            </div>
          </div>

          {/* ===== Stats cards ===== */}
          <div className="kb-detail-stats">
            <div className="kb-detail-stat-card">
              <span className="kb-detail-stat-icon" style={{ background: "#dbeafe", color: "#2563eb" }}>
                <SvgIcon name="document" size={22} />
              </span>
              <div>
                <div className="kb-detail-stat-label">文件总数</div>
                <div className="kb-detail-stat-value">{stats.fileCount}</div>
              </div>
            </div>
            <div className="kb-detail-stat-card">
              <span className="kb-detail-stat-icon" style={{ background: "#ede9fe", color: "#7c3aed" }}>
                <SvgIcon name="box" size={22} />
              </span>
              <div>
                <div className="kb-detail-stat-label">切片数量</div>
                <div className="kb-detail-stat-value">{stats.chunkCount}</div>
              </div>
            </div>
            <div className="kb-detail-stat-card">
              <span className="kb-detail-stat-icon" style={{ background: "#dbeafe", color: "#2563eb" }}>
                <SvgIcon name="clock" size={22} />
              </span>
              <div>
                <div className="kb-detail-stat-label">最近更新</div>
                <div className="kb-detail-stat-value">{stats.updatedLabel}</div>
              </div>
            </div>
          </div>

          {/* ===== Table + Task panel ===== */}
          <div className="kb-detail-body">
            {/* File table */}
            <div className="kb-detail-table-wrapper">
              <div className="kb-detail-table-header">
                <h3>知识库文件（{docs.length}）</h3>
              </div>

              {docLoading ? (
                <div className="kb-skeleton" style={{ height: 200 }} />
              ) : docError ? (
                <div className="kb-empty" style={{ padding: "60px 20px" }}>
                  <p style={{ color: "#ef4444" }}>{docError}</p>
                  <button className="kb-primary-btn" onClick={fetchDocuments} style={{ marginTop: 8 }}>重试</button>
                </div>
              ) : docs.length === 0 ? (
                <div className="kb-empty" style={{ padding: "60px 20px" }}>
                  <p>暂无文件</p>
                  <p style={{ color: "#94a3b8", fontSize: 13, marginTop: 4 }}>
                    点击上方「上传文件」按钮添加文档
                  </p>
                </div>
              ) : (
                <div className="kb-detail-table-responsive">
                  <table className="kb-detail-table">
                    <thead>
                      <tr>
                        <th>文件名</th>
                        <th>类型</th>
                        <th>状态</th>
                        <th>上传时间</th>
                        <th>切片数</th>
                        <th>操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {docs.map((doc) => {
                        const extMeta = getFileTypeMeta(doc.ext);
                        const status = doc.status || "unknown";
                        return (
                          <tr key={doc.id}>
                            <td>
                              <span className="kb-file-type-badge" style={{ background: extMeta.bg, color: extMeta.fg }}>
                                {extMeta.label}
                              </span>
                              <span className="kb-file-name">{doc.name}</span>
                            </td>
                            <td>{extMeta.label}</td>
                            <td>
                              <span
                                className="kb-status-tag"
                                style={{
                                  background: STATUS_COLOR[status] ? `${STATUS_COLOR[status]}18` : "#f1f5f9",
                                  color: STATUS_COLOR[status] || "#64748b",
                                }}
                              >
                                {STATUS_LABEL[status] || status}
                              </span>
                            </td>
                            <td className="kb-cell-muted">{doc.uploadedAt ? doc.uploadedAt.replace("T", " ").slice(0, 10) : "--"}</td>
                            <td className="kb-cell-muted">{doc.chunkCount ?? "--"}</td>
                            <td>
                              <div className="kb-table-actions">
                                <button className="kb-table-action-btn" onClick={() => handleViewDoc(doc)}>查看</button>
                                {status === "failed" && (
                                  <button className="kb-table-action-btn" onClick={() => handleRetryDoc(doc)}>重试</button>
                                )}
                                <button className="kb-table-action-btn kb-table-action-btn--danger" onClick={() => handleDeleteDoc(doc)}>删除</button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Pagination */}
              <div className="kb-pagination">
                <span className="kb-pagination__info">共 {docs.length} 条</span>
                <div className="kb-pagination__controls">
                  <button className="kb-page-btn" disabled>上一页</button>
                  <button className="kb-page-btn kb-page-btn--active">1</button>
                  <button className="kb-page-btn" disabled>下一页</button>
                </div>
              </div>
            </div>

            {/* Task panel */}
            <div className="kb-detail-task-panel">
              <h3 className="kb-task-panel__title">最近上传任务</h3>
              {task ? (
                <div className="kb-task-panel__content">
                  <div className="kb-task-file">
                    <SvgIcon name="file" size={20} />
                    <div>
                      <div className="kb-task-file__name">{task.fileName}</div>
                      <div className="kb-task-file__time">{task.uploadedAt?.replace("T", " ").slice(0, 16) || ""}</div>
                    </div>
                  </div>
                  <StageRow label="解析文件" progress={task.parseProgress} status={task.parseStatus} detail="2.4 MB" />
                  <StageRow label="切分文本" progress={task.splitProgress} status={task.splitStatus} detail="42 切片" />
                  <StageRow label="向量化" progress={task.embeddingProgress} status={task.embeddingStatus} detail="预计 12 秒" />
                  <div className="kb-task-note">
                    <SvgIcon name="loader" size={14} />
                    <span>任务进行中，离开此页不影响执行</span>
                  </div>
                </div>
              ) : (
                <div className="kb-empty" style={{ padding: "40px 20px" }}>
                  <p style={{ fontSize: 13 }}>暂无进行中的任务</p>
                  <p style={{ fontSize: 12, color: "#94a3b8", marginTop: 4 }}>
                    TODO: 后端任务进度接口尚未实现
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ===== Edit Modal ===== */}
      {showEditModal && (
        <div className="kb-overlay" onClick={() => setShowEditModal(false)}>
          <div className="kb-modal" onClick={(e) => e.stopPropagation()}>
            <h3 className="kb-modal__title">编辑知识库</h3>
            <form onSubmit={handleSaveEdit}>
              <div className="kb-modal__field">
                <label>知识库名称</label>
                <input
                  type="text"
                  value={editForm.name}
                  onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))}
                  autoFocus
                />
              </div>
              <div className="kb-modal__field">
                <label>描述</label>
                <textarea rows={3} value={editForm.description} onChange={(e) => setEditForm((f) => ({ ...f, description: e.target.value }))} />
              </div>
              <div className="kb-modal__actions">
                <button type="button" className="kb-btn kb-btn--outline" onClick={() => setShowEditModal(false)}>取消</button>
                <button type="submit" className="kb-btn kb-btn--primary" disabled={saving || !editForm.name.trim()}>
                  {saving ? "保存中..." : "保存"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ===== Delete Confirm Modal ===== */}
      {deleteConfirm && (
        <div className="kb-overlay" onClick={() => setDeleteConfirm(false)}>
          <div className="kb-modal" onClick={(e) => e.stopPropagation()}>
            <h3 className="kb-modal__title">删除知识库</h3>
            <p style={{ color: "#64748b", fontSize: 15, lineHeight: 1.6, margin: "8px 0 20px" }}>
              确定要删除「{kb.name}」吗？此操作不可撤销。
            </p>
            <div className="kb-modal__actions">
              <button type="button" className="kb-btn kb-btn--outline" onClick={() => setDeleteConfirm(false)}>取消</button>
              <button type="button" className="kb-btn kb-btn--danger" disabled={deleting} onClick={handleDeleteKB}>
                {deleting ? "删除中..." : "确认删除"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ===== StageRow sub-component ===== */
function StageRow({ label, progress, status, detail }) {
  const isSuccess = status === "success";
  const isProcessing = status === "processing";
  const isFailed = status === "failed";
  const isPending = status === "pending" || !status;

  return (
    <div className="kb-task-stage">
      <div className="kb-task-stage__top">
        <div className="kb-task-stage__label">
          {isSuccess && <span className="kb-task-stage__icon kb-task-stage__icon--success"><SvgIcon name="check" size={14} /></span>}
          {isProcessing && <span className="kb-task-stage__icon kb-task-stage__icon--processing"><SvgIcon name="loader" size={14} /></span>}
          {isFailed && <span className="kb-task-stage__icon kb-task-stage__icon--failed">!</span>}
          {isPending && <span className="kb-task-stage__icon kb-task-stage__icon--pending"><span /></span>}
          <span>{label}</span>
        </div>
        <span className={`kb-task-stage__pct ${isSuccess ? "kb-task-stage__pct--done" : ""}`}>{progress}%</span>
      </div>
      <div className="kb-task-bar">
        <div
          className={`kb-task-bar__fill ${isSuccess ? "kb-task-bar__fill--success" : isProcessing ? "kb-task-bar__fill--processing" : ""}`}
          style={{ width: `${progress}%` }}
        />
      </div>
      {detail && <div className="kb-task-stage__detail">{detail}</div>}
    </div>
  );
}
