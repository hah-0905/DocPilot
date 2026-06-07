import { useCallback, useEffect, useMemo, useState } from "react";
import { getKnowledgeBases, uploadKnowledgeBaseFile } from "../api/knowledgeBase";
import {
  getFiles,
  deleteFile,
  downloadFile,
  retryFile,
  getRecentUploads,
} from "../api/fileManagement";

/* ===============================================================
   Mock fallback data — TODO: remove when backend file APIs are available
   =============================================================== */
const MOCK_FILES = [
  { id: "1", name: "RAG论文.pdf", kbName: "论文知识库", ext: "pdf", status: "completed", size: 13254000, uploadedAt: "2026-06-04T10:12:00" },
  { id: "2", name: "项目说明.docx", kbName: "项目文档库", ext: "docx", status: "completed", size: 2202000, uploadedAt: "2026-06-03T17:30:00" },
  { id: "3", name: "课程笔记.md", kbName: "课程资料库", ext: "md", status: "processing", size: 426000, uploadedAt: "2026-06-04T09:45:00" },
  { id: "4", name: "合同模板.pdf", kbName: "合同资料库", ext: "pdf", status: "failed", size: 5400000, uploadedAt: "2026-05-31T14:20:00" },
  { id: "5", name: "会议纪要.txt", kbName: "项目文档库", ext: "txt", status: "completed", size: 98000, uploadedAt: "2026-05-30T11:00:00" },
  { id: "6", name: "产品需求文档.pdf", kbName: "项目文档库", ext: "pdf", status: "completed", size: 8700000, uploadedAt: "2026-05-29T16:45:00" },
  { id: "7", name: "API接口文档.md", kbName: "项目文档库", ext: "md", status: "completed", size: 312000, uploadedAt: "2026-05-28T09:30:00" },
  { id: "8", name: "数据库设计文档.pdf", kbName: "论文知识库", ext: "pdf", status: "completed", size: 4100000, uploadedAt: "2026-05-27T14:00:00" },
  { id: "9", name: "研究报告.docx", kbName: "论文知识库", ext: "docx", status: "pending", size: 6800000, uploadedAt: "2026-05-26T10:15:00" },
  { id: "10", name: "实验数据.txt", kbName: "论文知识库", ext: "txt", status: "completed", size: 150000, uploadedAt: "2026-05-25T08:30:00" },
];

const MOCK_RECENT_UPLOADS = [
  { id: "r3", fileName: "课程笔记.md", sizeText: "426 KB", status: "processing", progress: 65 },
  { id: "r6", fileName: "产品需求文档.pdf", sizeText: "8.7 MB", status: "completed", progress: 100 },
  { id: "r7", fileName: "API接口文档.md", sizeText: "312 KB", status: "completed", progress: 100 },
  { id: "r5", fileName: "会议记录.txt", sizeText: "98 KB", status: "completed", progress: 100 },
  { id: "r4", fileName: "合同模板.pdf", sizeText: "5.2 MB", status: "failed", progress: 100 },
];

/* ===============================================================
   Adapters & helpers
   =============================================================== */
const FILE_TYPE_META = {
  pdf: { label: "PDF", bg: "#fef2f2", fg: "#dc2626" },
  docx: { label: "DOCX", bg: "#eff6ff", fg: "#2563eb" },
  doc: { label: "DOC", bg: "#eff6ff", fg: "#2563eb" },
  md: { label: "MD", bg: "#f1f5f9", fg: "#334155" },
  txt: { label: "TXT", bg: "#f8fafc", fg: "#64748b" },
};
function getTypeMeta(ext) { return FILE_TYPE_META[(ext || "").toLowerCase().replace(/^\./, "")] || { label: "FILE", bg: "#f1f5f9", fg: "#64748b" }; }

const STATUS_MAP = {
  completed: { label: "已完成", color: "#16a34a", bg: "#dcfce7" },
  success: { label: "已完成", color: "#16a34a", bg: "#dcfce7" },
  indexed: { label: "已完成", color: "#16a34a", bg: "#dcfce7" },
  vectorized: { label: "已完成", color: "#16a34a", bg: "#dcfce7" },
  processing: { label: "处理中", color: "#f97316", bg: "#ffedd5" },
  parsing: { label: "处理中", color: "#f97316", bg: "#ffedd5" },
  chunking: { label: "处理中", color: "#f97316", bg: "#ffedd5" },
  embedding: { label: "处理中", color: "#f97316", bg: "#ffedd5" },
  failed: { label: "失败", color: "#ef4444", bg: "#fef2f2" },
  error: { label: "失败", color: "#ef4444", bg: "#fef2f2" },
  pending: { label: "等待中", color: "#94a3b8", bg: "#f1f5f9" },
};
function mapStatus(s) { return STATUS_MAP[(s || "").toLowerCase()] || { label: s || "未知", color: "#64748b", bg: "#f1f5f9" }; }

function formatSize(bytes) {
  if (!bytes && bytes !== 0) return "--";
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

function formatTime(t) {
  if (!t) return "--";
  const d = new Date(t);
  const now = new Date();
  const diff = now - d;
  const sameDay = d.toDateString() === now.toDateString();
  const yesterday = new Date(now); yesterday.setDate(yesterday.getDate() - 1);
  const isYesterday = d.toDateString() === yesterday.toDateString();
  const timeStr = d.toTimeString().slice(0, 5);
  if (sameDay) return `今天 ${timeStr}`;
  if (isYesterday) return `昨天 ${timeStr}`;
  return t.replace("T", " ").slice(0, 16);
}

function normalizeKnowledgeBases(payload) {
  const list = Array.isArray(payload)
    ? payload
    : Array.isArray(payload?.items)
      ? payload.items
      : Array.isArray(payload?.list)
        ? payload.list
        : Array.isArray(payload?.records)
          ? payload.records
          : [];

  return list
    .filter((kb) => kb && kb.id !== undefined && kb.id !== null && kb.name)
    .map((kb) => ({ id: String(kb.id), name: kb.name }));
}

/* ===== SvgIcon ===== */
function SvgIcon({ name, size = 20 }) {
  const s = size;
  const paths = {
    folder: <><path d="M4 20V4a2 2 0 0 1 2-2h5l4 4h5a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2Z" /></>,
    search: <><circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" /></>,
    upload: <><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></>,
    trash: <><polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /></>,
    download: <><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></>,
    "refresh-cw": <><polyline points="23 4 23 10 17 10" /><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" /></>,
    eye: <><path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z" /><circle cx="12" cy="12" r="2.5" /></>,
    layers: <><path d="m12 3 9 5-9 5-9-5 9-5Z" /><path d="m4 12 8 4.5 8-4.5" /><path d="m4 16 8 4.5 8-4.5" /></>,
    chevron: <><path d="m6 9 6 6 6-6" /></>,
    plus: <><circle cx="12" cy="12" r="10" /><path d="M8 12h8M12 8v8" /></>,
    file: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Z" /><path d="M14 2v6h6" /></>,
    "cloud-up": <><path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z" /><line x1="12" y1="13" x2="12" y2="19" /><polyline points="9 16 12 19 15 16" /></>,
    "chevron-down": <><path d="m6 9 6 6 6-6" /></>,
    "chat-dot": <><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10Z" /><circle cx="12" cy="10" r="1" /></>,
    settings: <><circle cx="12" cy="12" r="3" /><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" /></>,
  };
  return <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

/* ===============================================================
   FileManagementPage
   =============================================================== */
export default function FileManagementPage({ onNavigate }) {
  // ---- Data state ----
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [kbs, setKbs] = useState([]);

  // ---- Filter state ----
  const [searchText, setSearchText] = useState("");
  const [kbFilter, setKbFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");

  // ---- Upload state ----
  const [uploadKbId, setUploadKbId] = useState("");
  const [dragging, setDragging] = useState(false);

  // ---- Page state ----
  const [page, setPage] = useState(1);
  const pageSize = 10;

  // ---- Fetch data ----
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    let realKbList = [];
    try {
      // Try real API first
      const [realFiles, realKbs] = await Promise.all([getFiles(), getKnowledgeBases()]).catch(() => [null, null]);
      // eslint-disable-next-line no-unused-expressions
      realFiles;
      realKbList = normalizeKnowledgeBases(realKbs);
    } catch (_e) { /* ignore */ }

    // TODO: remove mock fallback when backend APIs are available
    setFiles(MOCK_FILES);
    setKbs(realKbList);
    setLoading(false);
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  useEffect(() => {
    if (kbFilter !== "all" && !kbs.some((kb) => kb.name === kbFilter)) {
      setKbFilter("all");
      setPage(1);
    }
    if (uploadKbId && !kbs.some((kb) => kb.id === uploadKbId)) {
      setUploadKbId("");
    }
  }, [kbFilter, kbs, uploadKbId]);

  // ---- Search debounce ----
  const [searchInput, setSearchInput] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => setSearchText(searchInput), 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  // ---- Filter & sort ----
  const filteredFiles = useMemo(() => {
    let list = [...files];
    if (searchText.trim()) {
      const q = searchText.trim().toLowerCase();
      list = list.filter((f) => f.name.toLowerCase().includes(q));
    }
    if (kbFilter !== "all") list = list.filter((f) => f.kbName === kbFilter);
    if (typeFilter !== "all") list = list.filter((f) => getTypeMeta(f.ext).label === typeFilter || (typeFilter === "其他" && !FILE_TYPE_META[f.ext]));
    list.sort((a, b) => (b.uploadedAt || "").localeCompare(a.uploadedAt || ""));
    return list;
  }, [files, searchText, kbFilter, typeFilter]);

  const paginatedFiles = useMemo(() => filteredFiles.slice((page - 1) * pageSize, page * pageSize), [filteredFiles, page]);
  const totalPages = Math.max(1, Math.ceil(filteredFiles.length / pageSize));

  // ---- Upload handler ----
  const handleUploadFile = async (file) => {
    if (!uploadKbId) { alert("请先选择所属知识库"); return; }
    try {
      const result = await uploadKnowledgeBaseFile(uploadKbId, file);
      const uploaded = Array.isArray(result) ? result : [result];
      // Add uploaded files to the mock list (TODO: remove when real file list API exists)
      for (const doc of uploaded) {
        setFiles((prev) => [{ id: String(doc.id), name: doc.title || doc.original_file_name, kbName: kbs.find(k => k.id === uploadKbId)?.name || "", ext: doc.file_ext || "file", status: doc.parse_status === "success" ? "completed" : doc.parse_status, size: doc.size_bytes || 0, uploadedAt: new Date().toISOString() }, ...prev]);
      }
      alert(`上传成功，共 ${uploaded.length} 个文件`);
    } catch (err) {
      alert(err.message || "上传失败");
    }
  };

  const handleFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (file) handleUploadFile(file);
    e.target.value = "";
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleUploadFile(file);
  };

  // ---- Delete ----
  const handleDelete = async (fileId, fileName) => {
    if (!window.confirm(`确定要删除「${fileName}」吗？`)) return;
    try {
      await deleteFile(fileId);
      setFiles((prev) => prev.filter((f) => f.id !== fileId));
    } catch (err) {
      alert(err.message || "删除失败");
    }
  };

  // ---- Download ----
  const handleDownload = async (fileId) => {
    try {
      await downloadFile(fileId);
    } catch (err) {
      alert(err.message || "下载失败");
    }
  };

  // ---- Retry ----
  const handleRetry = async (fileId) => {
    try {
      await retryFile(fileId);
      alert("重试请求已提交（TODO: 对接真实接口后将自动刷新状态）");
    } catch (err) {
      alert(err.message || "重试失败");
    }
  };

  // ---- Preview ----
  const handlePreview = (file) => {
    alert(`文件预览功能待接入 — ${file.name}`);
  };

  // ---- Type filter options ----
  const typeOptions = ["全部", "PDF", "Word", "Markdown", "TXT", "其他"];

  // ---- Sidebar nav ----
  const sidebarNav = (active, onClick) => (
    <aside className="kb-sidebar">
      <div className="kb-sidebar__brand">
        <span className="kb-sidebar__logo" aria-hidden="true"><span /></span>
        <span className="kb-sidebar__name">DocPilot</span>
      </div>
      <button className="kb-sidebar__new-btn"><SvgIcon name="plus" size={18} /><span>新建对话</span></button>
      <nav className="kb-sidebar__nav">
        <a className={`kb-nav-item${active === "kb" ? " kb-nav-item--active" : ""}`}
          href="#" onClick={(e) => { e.preventDefault(); onClick("/knowledge-base"); }}>
          <SvgIcon name="layers" size={18} /><span>知识库</span>
        </a>
      </nav>
      <div className="kb-sidebar__section">
        <div className="kb-sidebar__divider" />
        <div className="kb-sidebar__section-title">最近对话</div>
        {["RAG 架构设计", "合同风险分析", "文档总结"].map((s) => (
          <a key={s} className="kb-nav-item kb-nav-item--sub" href="#" onClick={(e) => e.preventDefault()}>
            <SvgIcon name="chat-dot" size={16} /><span>{s}</span>
          </a>
        ))}
      </div>
      <div className="kb-sidebar__footer">
        <div className="kb-sidebar__divider" />
        <a className={`kb-nav-item${active === "files" ? " kb-nav-item--active" : ""}`}
          href="#" onClick={(e) => { e.preventDefault(); onClick("/files"); }}>
          <SvgIcon name="file" size={18} /><span>文件管理</span>
        </a>
        <a className="kb-nav-item" href="#" onClick={(e) => { e.preventDefault(); onClick("/settings"); }}>
          <SvgIcon name="settings" size={18} /><span>设置</span>
        </a>
      </div>
    </aside>
  );

  /* ============================================================
     Render
     ============================================================ */
  return (
    <div className="kb-page">
      {sidebarNav("files", onNavigate)}

      <div className="kb-main">
        <header className="kb-topbar">
          <div className="kb-topbar__left">
            <span className="kb-topbar__label">当前知识库：</span>
            <span className="kb-topbar__value">论文知识库</span>
            <SvgIcon name="chevron-down" size={16} />
          </div>
          <div className="kb-topbar__center">
            <span className="kb-topbar__label">模型：</span>
            <span className="kb-topbar__value">DeepSeek / GPT</span>
            <SvgIcon name="chevron-down" size={16} />
          </div>
          <div className="kb-topbar__right">
            <button className="kb-topbar__icon-btn" title="搜索"><SvgIcon name="search" size={20} /></button>
            <span className="kb-avatar" />
            <SvgIcon name="chevron-down" size={16} />
          </div>
        </header>

        <div className="fm-content">
          {/* ===== Left: main area ===== */}
          <div className="fm-main">
            {/* Header */}
            <div className="fm-header">
              <span className="fm-header-icon"><SvgIcon name="folder" size={32} /></span>
              <div>
                <h1 className="fm-header__title">文件管理</h1>
                <p className="fm-header__subtitle">统一查看、筛选与管理上传文件</p>
              </div>
            </div>

            {/* Toolbar */}
            <div className="fm-toolbar">
              <div className="fm-search">
                <SvgIcon name="search" size={16} />
                <input type="text" placeholder="搜索文件名..." value={searchInput} onChange={(e) => { setSearchInput(e.target.value); setPage(1); }} />
              </div>
              <div className="fm-select" onClick={() => {
                const opts = ["all", ...kbs.map((k) => k.name)];
                const idx = opts.indexOf(kbFilter);
                setKbFilter(opts[(idx + 1) % opts.length]);
                setPage(1);
              }}>
                <span>所属知识库：{kbFilter === "all" ? "全部" : kbFilter}</span>
                <SvgIcon name="chevron-down" size={14} />
              </div>
              <div className="fm-select" onClick={() => {
                const idx = typeOptions.indexOf(typeFilter === "all" ? "全部" : typeFilter);
                const next = typeOptions[(idx + 1) % typeOptions.length];
                setTypeFilter(next === "全部" ? "all" : next);
                setPage(1);
              }}>
                <span>文件类型：{typeFilter === "all" ? "全部" : typeFilter}</span>
                <SvgIcon name="chevron-down" size={14} />
              </div>
              <label className="fm-upload-btn">
                <SvgIcon name="upload" size={15} />
                <span>上传文件</span>
                <input type="file" style={{ display: "none" }} onChange={handleFileSelect} />
              </label>
            </div>

            {/* File table */}
            {loading ? (
              <div className="kb-loading" style={{ marginTop: 16 }}>
                {[1, 2, 3, 4].map((i) => <div key={i} className="kb-skeleton" style={{ height: 60, marginBottom: 8, borderRadius: 8 }} />)}
              </div>
            ) : error ? (
              <div className="kb-empty" style={{ marginTop: 40 }}>
                <p style={{ color: "#ef4444" }}>{error}</p>
                <button className="kb-primary-btn" onClick={fetchData}>重试</button>
              </div>
            ) : filteredFiles.length === 0 ? (
              <div className="kb-empty" style={{ marginTop: 40 }}>
                <p>{searchText ? "没有匹配的文件" : "暂无文件"}</p>
                <p style={{ color: "#94a3b8", fontSize: 13, marginTop: 4 }}>请点击「上传文件」添加文档</p>
              </div>
            ) : (
              <div className="fm-table-card">
                <div className="fm-table-wrap">
                  <table className="fm-table">
                    <thead>
                      <tr>
                        <th>文件名</th>
                        <th>所属知识库</th>
                        <th>类型</th>
                        <th>状态</th>
                        <th>大小</th>
                        <th>上传时间</th>
                        <th>操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {paginatedFiles.map((f) => {
                        const typeM = getTypeMeta(f.ext);
                        const st = mapStatus(f.status);
                        return (
                          <tr key={f.id}>
                            <td>
                              <span className="fm-type-badge" style={{ background: typeM.bg, color: typeM.fg }}>{typeM.label}</span>
                              <span className="fm-file-name">{f.name}</span>
                            </td>
                            <td className="fm-cell-muted">{f.kbName}</td>
                            <td><span className="fm-type-label">{typeM.label}</span></td>
                            <td>
                              <span className="kb-status-tag" style={{ background: st.bg, color: st.color }}>{st.label}</span>
                            </td>
                            <td className="fm-cell-muted">{formatSize(f.size)}</td>
                            <td className="fm-cell-muted">{formatTime(f.uploadedAt)}</td>
                            <td>
                              <div className="fm-table-actions">
                                {f.status === "completed" && (
                                  <>
                                    <button className="fm-tbl-btn" onClick={() => handlePreview(f)}>预览</button>
                                    <button className="fm-tbl-btn" onClick={() => handleDownload(f.id)}>下载</button>
                                  </>
                                )}
                                {f.status === "processing" && (
                                  <button className="fm-tbl-btn" onClick={() => handlePreview(f)}>查看</button>
                                )}
                                {f.status === "failed" && (
                                  <button className="fm-tbl-btn" onClick={() => handleRetry(f.id)}>重试</button>
                                )}
                                {f.status === "pending" && (
                                  <span className="fm-cell-muted" style={{ fontSize: 12 }}>等待中</span>
                                )}
                                <button className="fm-tbl-btn fm-tbl-btn--danger" onClick={() => handleDelete(f.id, f.name)}>删除</button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Pagination */}
                <div className="fm-pagination">
                  <span className="fm-pagination__info">共 {filteredFiles.length} 项</span>
                  <div className="kb-pagination__controls">
                    <button className="kb-page-btn" disabled={page <= 1} onClick={() => setPage(page - 1)}>上一页</button>
                    {Array.from({ length: totalPages }, (_, i) => (
                      <button key={i + 1} className={`kb-page-btn${page === i + 1 ? " kb-page-btn--active" : ""}`} onClick={() => setPage(i + 1)}>{i + 1}</button>
                    ))}
                    <button className="kb-page-btn" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>下一页</button>
                  </div>
                </div>
              </div>
            )}

            {/* TODO note */}
            <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 12, textAlign: "center" }}>
              TODO: 当前使用 mock 数据展示，待后端提供文件接口后切换为真实数据
            </div>
          </div>

          {/* ===== Right panel ===== */}
          <div className="fm-sidebar">
            {/* Upload card */}
            <div className="fm-card">
              <h3 className="fm-card__title">上传文件</h3>
              <div
                className={`fm-dropzone${dragging ? " fm-dropzone--active" : ""}`}
                onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={handleDrop}
                onClick={() => document.getElementById("fm-file-input")?.click()}
              >
                <SvgIcon name="cloud-up" size={40} />
                <p className="fm-dropzone__text">拖拽文件到这里，或点击上传</p>
                <p className="fm-dropzone__hint">支持格式：PDF / DOCX / TXT / Markdown</p>
                <p className="fm-dropzone__hint">单个文件最大 100MB</p>
                <input id="fm-file-input" type="file" style={{ display: "none" }} onChange={handleFileSelect} />
              </div>

              <div className="fm-upload-kb-select">
                <label>所属知识库</label>
                <select value={uploadKbId} onChange={(e) => setUploadKbId(e.target.value)}>
                  <option value="">请选择知识库</option>
                  {kbs.map((kb) => <option key={kb.id} value={kb.id}>{kb.name}</option>)}
                </select>
              </div>
            </div>

            {/* Recent uploads */}
            <div className="fm-card" style={{ marginTop: 16 }}>
              <div className="fm-card__title-row">
                <h3 className="fm-card__title">最近上传</h3>
                <button className="fm-tbl-btn" title="清空" onClick={() => setFiles((prev) => prev.slice(0, 0))}>
                  <SvgIcon name="trash" size={14} />
                </button>
              </div>
              <div className="fm-recent-list">
                {MOCK_RECENT_UPLOADS.map((u) => {
                  const st = mapStatus(u.status);
                  const isFailed = u.status === "failed";
                  return (
                    <div key={u.id} className="fm-recent-item">
                      <div className="fm-recent-item__top">
                        <div className="fm-recent-item__info">
                          <div className="fm-recent-item__name">{u.fileName}</div>
                          <div className="fm-recent-item__size">{u.sizeText}</div>
                        </div>
                        <span className="kb-status-tag" style={{ background: st.bg, color: st.color, fontSize: 11 }}>{st.label}</span>
                      </div>
                      <div className="fm-progress">
                        <div
                          className={`fm-progress__fill${isFailed ? " fm-progress__fill--failed" : u.progress >= 100 ? " fm-progress__fill--done" : ""}`}
                          style={{ width: `${u.progress}%` }}
                        />
                      </div>
                      <span className="fm-progress__label">{u.progress}%</span>
                    </div>
                  );
                })}
              </div>
              <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 12, textAlign: "center" }}>
                TODO: 待后端提供上传任务接口
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
