import { useCallback, useEffect, useMemo, useState } from "react";
import {
  getKnowledgeBases,
  getDocuments,
  uploadKnowledgeBaseFile,
  deleteDocument,
  downloadDocument,
  retryDocument,
} from "../api/knowledgeBase";
import DocumentViewer from "../components/DocumentViewer";

const FILE_TYPE_META = {
  pdf: { label: "PDF", bg: "#fef2f2", fg: "#dc2626" },
  docx: { label: "DOCX", bg: "#eff6ff", fg: "#2563eb" },
  doc: { label: "DOC", bg: "#eff6ff", fg: "#2563eb" },
  md: { label: "MD", bg: "#f1f5f9", fg: "#334155" },
  markdown: { label: "MD", bg: "#f1f5f9", fg: "#334155" },
  txt: { label: "TXT", bg: "#f8fafc", fg: "#64748b" },
};

const STATUS_META = {
  completed: { label: "已完成", color: "#16a34a", bg: "#dcfce7" },
  processing: { label: "处理中", color: "#f97316", bg: "#ffedd5" },
  failed: { label: "失败", color: "#ef4444", bg: "#fef2f2" },
  pending: { label: "等待中", color: "#64748b", bg: "#f1f5f9" },
};

function getTypeMeta(ext) {
  const key = (ext || "").toLowerCase().replace(/^\./, "");
  return FILE_TYPE_META[key] || { label: key.toUpperCase() || "FILE", bg: "#f1f5f9", fg: "#64748b" };
}

function mapStatus(value) {
  const status = (value || "").toLowerCase();
  if (["success", "indexed", "completed", "vectorized"].includes(status)) return "completed";
  if (["processing", "parsing", "chunking", "embedding", "indexing"].includes(status)) return "processing";
  if (["failed", "error"].includes(status)) return "failed";
  return "pending";
}

function formatSize(bytes) {
  if (bytes === undefined || bytes === null || bytes === "") return "--";
  const value = Number(bytes);
  if (Number.isNaN(value)) return "--";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function formatTime(value) {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value).replace("T", " ").slice(0, 16);
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function normalizeList(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.items)) return payload.items;
  if (Array.isArray(payload?.list)) return payload.list;
  if (Array.isArray(payload?.records)) return payload.records;
  return [];
}

function normalizeKnowledgeBases(payload) {
  return normalizeList(payload)
    .filter((kb) => kb?.id !== undefined && kb?.id !== null)
    .map((kb) => ({ id: String(kb.id), name: kb.name || "未命名知识库" }));
}

function normalizeDocument(doc, kb) {
  const ext = doc.file_ext || doc.type || doc.ext || doc.extension || "";
  const status = mapStatus(doc.parse_status || doc.index_status || doc.status);
  return {
    id: String(doc.id ?? `${kb.id}-${doc.original_file_name || doc.name || doc.title}`),
    kbId: kb.id,
    kbName: kb.name,
    name: doc.title || doc.original_file_name || doc.name || "未命名文件",
    ext,
    status,
    size: doc.size_bytes ?? doc.size ?? doc.file_size,
    uploadedAt: doc.created_at || doc.updated_at || doc.uploaded_at || "",
    chunkCount: doc.chunk_count ?? doc.chunks ?? "--",
  };
}

function SvgIcon({ name, size = 20 }) {
  const paths = {
    folder: <><path d="M4 20V4a2 2 0 0 1 2-2h5l4 4h5a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2Z" /></>,
    search: <><circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" /></>,
    upload: <><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></>,
    trash: <><polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /></>,
    "refresh-cw": <><polyline points="23 4 23 10 17 10" /><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" /></>,
    layers: <><path d="m12 3 9 5-9 5-9-5 9-5Z" /><path d="m4 12 8 4.5 8-4.5" /><path d="m4 16 8 4.5 8-4.5" /></>,
    plus: <><circle cx="12" cy="12" r="10" /><path d="M8 12h8M12 8v8" /></>,
    file: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Z" /><path d="M14 2v6h6" /></>,
    "cloud-up": <><path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z" /><line x1="12" y1="13" x2="12" y2="19" /><polyline points="9 16 12 19 15 16" /></>,
    "chevron-down": <><path d="m6 9 6 6 6-6" /></>,
    "chat-dot": <><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10Z" /><circle cx="12" cy="10" r="1" /></>,
    settings: <><circle cx="12" cy="12" r="3" /><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" /></>,
  };

  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[name] || paths.file}
    </svg>
  );
}

export default function FileManagementPage({ onNavigate }) {
  const [files, setFiles] = useState([]);
  const [kbs, setKbs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [kbFilter, setKbFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [uploadKbId, setUploadKbId] = useState("");
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [page, setPage] = useState(1);
  const [viewerFile, setViewerFile] = useState(null);
  const pageSize = 10;

  const fetchFiles = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const kbList = normalizeKnowledgeBases(await getKnowledgeBases());
      setKbs(kbList);
      if (!uploadKbId && kbList[0]) setUploadKbId(kbList[0].id);

      const settled = await Promise.allSettled(
        kbList.map(async (kb) => normalizeList(await getDocuments(kb.id)).map((doc) => normalizeDocument(doc, kb)))
      );
      const allFiles = settled.flatMap((item) => (item.status === "fulfilled" ? item.value : []));
      setFiles(allFiles);

      const failedCount = settled.filter((item) => item.status === "rejected").length;
      if (failedCount > 0) {
        setError(`有 ${failedCount} 个知识库的文件暂时无法加载。`);
      }
    } catch (err) {
      setFiles([]);
      setError(err.message || "文件列表加载失败");
    } finally {
      setLoading(false);
    }
  }, [uploadKbId]);

  useEffect(() => {
    fetchFiles();
  }, [fetchFiles]);

  useEffect(() => {
    if (uploadKbId && !kbs.some((kb) => kb.id === uploadKbId)) setUploadKbId(kbs[0]?.id || "");
    if (kbFilter !== "all" && !kbs.some((kb) => kb.id === kbFilter)) setKbFilter("all");
  }, [kbFilter, kbs, uploadKbId]);

  const filteredFiles = useMemo(() => {
    const query = searchInput.trim().toLowerCase();
    return files
      .filter((file) => !query || file.name.toLowerCase().includes(query))
      .filter((file) => kbFilter === "all" || file.kbId === kbFilter)
      .filter((file) => typeFilter === "all" || getTypeMeta(file.ext).label === typeFilter)
      .sort((a, b) => (b.uploadedAt || "").localeCompare(a.uploadedAt || ""));
  }, [files, kbFilter, searchInput, typeFilter]);

  const totalPages = Math.max(1, Math.ceil(filteredFiles.length / pageSize));
  const paginatedFiles = filteredFiles.slice((page - 1) * pageSize, page * pageSize);
  const recentUploads = files
    .slice()
    .sort((a, b) => (b.uploadedAt || "").localeCompare(a.uploadedAt || ""))
    .slice(0, 5);

  const stats = useMemo(() => {
    return {
      total: files.length,
      completed: files.filter((file) => file.status === "completed").length,
      processing: files.filter((file) => file.status === "processing" || file.status === "pending").length,
      failed: files.filter((file) => file.status === "failed").length,
    };
  }, [files]);

  const uploadFiles = async (fileList) => {
    const selected = Array.from(fileList || []);
    if (selected.length === 0) return;
    if (!uploadKbId) {
      alert("请先选择所属知识库");
      return;
    }

    setUploading(true);
    try {
      await uploadKnowledgeBaseFile(uploadKbId, selected);
      await fetchFiles();
    } catch (err) {
      alert(err.message || "上传失败");
    } finally {
      setUploading(false);
    }
  };

  const handleFileSelect = (event) => {
    uploadFiles(event.target.files);
    event.target.value = "";
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setDragging(false);
    uploadFiles(event.dataTransfer.files);
  };

  const handleDelete = async (file) => {
    if (!window.confirm(`确定删除「${file.name}」吗？`)) return;
    try {
      await deleteDocument(file.kbId, file.id);
      setFiles((prev) => prev.filter((item) => !(item.kbId === file.kbId && item.id === file.id)));
    } catch (err) {
      alert(err.message || "删除失败");
    }
  };

  const handleRetry = async (file) => {
    try {
      await retryDocument(file.id);
      await fetchFiles();
    } catch (err) {
      alert(err.message || "重试失败");
    }
  };

  const handleDownload = async (file) => {
    try {
      await downloadDocument(file.kbId, file.id, file.name);
    } catch (err) {
      alert(err.message || "下载失败");
    }
  };

  const typeOptions = ["all", "PDF", "DOCX", "DOC", "MD", "TXT", "FILE"];

  return (
    <div className="kb-page">
      <aside className="kb-sidebar">
        <div className="kb-sidebar__brand">
          <span className="kb-sidebar__logo" aria-hidden="true"><span /></span>
          <span className="kb-sidebar__name">DocPilot</span>
        </div>
        <button className="kb-sidebar__new-btn" onClick={() => onNavigate("/chat")}><SvgIcon name="plus" size={18} /><span>新建对话</span></button>
        <nav className="kb-sidebar__nav">
          <a className="kb-nav-item" href="#" onClick={(event) => { event.preventDefault(); onNavigate("/knowledge-base"); }}>
            <SvgIcon name="layers" size={18} /><span>知识库</span>
          </a>
        </nav>
        <div className="kb-sidebar__section">
          <div className="kb-sidebar__divider" />
          <div className="kb-sidebar__section-title">最近对话</div>
          {["RAG 架构设计", "合同风险分析", "文档总结"].map((item) => (
            <a key={item} className="kb-nav-item kb-nav-item--sub" href="#" onClick={(event) => event.preventDefault()}>
              <SvgIcon name="chat-dot" size={16} /><span>{item}</span>
            </a>
          ))}
        </div>
        <div className="kb-sidebar__footer">
          <div className="kb-sidebar__divider" />
          <a className="kb-nav-item kb-nav-item--active" href="#" onClick={(event) => { event.preventDefault(); onNavigate("/files"); }}>
            <SvgIcon name="file" size={18} /><span>文件管理</span>
          </a>
          <a className="kb-nav-item" href="#" onClick={(event) => { event.preventDefault(); onNavigate("/settings"); }}>
            <SvgIcon name="settings" size={18} /><span>设置</span>
          </a>
        </div>
      </aside>

      <div className="kb-main">
        <header className="kb-topbar">
          <div className="kb-topbar__left">
            <span className="kb-topbar__label">当前页面：</span>
            <span className="kb-topbar__value">我上传的文件</span>
          </div>
          <div className="kb-topbar__center">
            <span className="kb-topbar__label">模型：</span>
            <span className="kb-topbar__value">DeepSeek / GPT</span>
            <SvgIcon name="chevron-down" size={16} />
          </div>
          <div className="kb-topbar__right">
            <button className="kb-topbar__icon-btn" title="刷新" onClick={fetchFiles}><SvgIcon name="refresh-cw" size={18} /></button>
            <span className="kb-avatar" />
            <SvgIcon name="chevron-down" size={16} />
          </div>
        </header>

        <div className="fm-content">
          <div className="fm-main">
            <div className="fm-header">
              <span className="fm-header-icon"><SvgIcon name="folder" size={32} /></span>
              <div>
                <h1 className="fm-header__title">我上传的文件</h1>
                <p className="fm-header__subtitle">集中查看、筛选和管理你上传到各知识库的文件</p>
              </div>
            </div>

            <div className="kb-detail-stats fm-stats">
              <div className="kb-detail-stat-card"><div><div className="kb-detail-stat-label">全部文件</div><div className="kb-detail-stat-value">{stats.total}</div></div></div>
              <div className="kb-detail-stat-card"><div><div className="kb-detail-stat-label">已完成</div><div className="kb-detail-stat-value">{stats.completed}</div></div></div>
              <div className="kb-detail-stat-card"><div><div className="kb-detail-stat-label">处理中</div><div className="kb-detail-stat-value">{stats.processing}</div></div></div>
              <div className="kb-detail-stat-card"><div><div className="kb-detail-stat-label">失败</div><div className="kb-detail-stat-value">{stats.failed}</div></div></div>
            </div>

            <div className="fm-toolbar">
              <div className="fm-search">
                <SvgIcon name="search" size={16} />
                <input type="text" placeholder="搜索文件名..." value={searchInput} onChange={(event) => { setSearchInput(event.target.value); setPage(1); }} />
              </div>
              <select className="fm-select" value={kbFilter} onChange={(event) => { setKbFilter(event.target.value); setPage(1); }}>
                <option value="all">全部知识库</option>
                {kbs.map((kb) => <option key={kb.id} value={kb.id}>{kb.name}</option>)}
              </select>
              <select className="fm-select" value={typeFilter} onChange={(event) => { setTypeFilter(event.target.value); setPage(1); }}>
                {typeOptions.map((type) => <option key={type} value={type}>{type === "all" ? "全部类型" : type}</option>)}
              </select>
              <label className="fm-upload-btn">
                <SvgIcon name="upload" size={15} />
                <span>{uploading ? "上传中..." : "上传文件"}</span>
                <input type="file" multiple style={{ display: "none" }} onChange={handleFileSelect} disabled={uploading} />
              </label>
            </div>

            {error && (
              <div className="kb-empty" style={{ marginTop: 12, padding: "12px 16px", alignItems: "flex-start" }}>
                <p style={{ color: "#ef4444" }}>{error}</p>
              </div>
            )}

            {loading ? (
              <div className="kb-loading" style={{ marginTop: 16 }}>
                {[1, 2, 3, 4].map((item) => <div key={item} className="kb-skeleton" style={{ height: 60, marginBottom: 8, borderRadius: 8 }} />)}
              </div>
            ) : filteredFiles.length === 0 ? (
              <div className="kb-empty" style={{ marginTop: 40 }}>
                <p>{searchInput ? "没有匹配的文件" : "还没有上传文件"}</p>
                <p style={{ color: "#94a3b8", fontSize: 13, marginTop: 4 }}>选择知识库后点击上传，文件会出现在这里。</p>
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
                        <th>切片数</th>
                        <th>上传时间</th>
                        <th>操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {paginatedFiles.map((file) => {
                        const typeMeta = getTypeMeta(file.ext);
                        const statusMeta = STATUS_META[file.status] || STATUS_META.pending;
                        return (
                          <tr key={`${file.kbId}-${file.id}`}>
                            <td>
                              <span className="fm-type-badge" style={{ background: typeMeta.bg, color: typeMeta.fg }}>{typeMeta.label}</span>
                              <span className="fm-file-name">{file.name}</span>
                            </td>
                            <td className="fm-cell-muted">{file.kbName}</td>
                            <td><span className="fm-type-label">{typeMeta.label}</span></td>
                            <td><span className="kb-status-tag" style={{ background: statusMeta.bg, color: statusMeta.color }}>{statusMeta.label}</span></td>
                            <td className="fm-cell-muted">{formatSize(file.size)}</td>
                            <td className="fm-cell-muted">{file.chunkCount ?? "--"}</td>
                            <td className="fm-cell-muted">{formatTime(file.uploadedAt)}</td>
                            <td>
                              <div className="fm-table-actions">
                                <button className="fm-tbl-btn" onClick={() => handleDownload(file)}>下载</button>
                                <button className="fm-tbl-btn" onClick={() => setViewerFile(file)}>查看</button>
                                {file.status === "failed" && <button className="fm-tbl-btn" onClick={() => handleRetry(file)}>重试</button>}
                                <button className="fm-tbl-btn fm-tbl-btn--danger" onClick={() => handleDelete(file)}>删除</button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                <div className="fm-pagination">
                  <span className="fm-pagination__info">共 {filteredFiles.length} 项</span>
                  <div className="kb-pagination__controls">
                    <button className="kb-page-btn" disabled={page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>上一页</button>
                    <button className="kb-page-btn kb-page-btn--active">{page}</button>
                    <button className="kb-page-btn" disabled={page >= totalPages} onClick={() => setPage((current) => Math.min(totalPages, current + 1))}>下一页</button>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="fm-sidebar">
            <div className="fm-card">
              <h3 className="fm-card__title">上传到知识库</h3>
              <div
                className={`fm-dropzone${dragging ? " fm-dropzone--active" : ""}`}
                onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={handleDrop}
                onClick={() => document.getElementById("fm-file-input")?.click()}
              >
                <SvgIcon name="cloud-up" size={40} />
                <p className="fm-dropzone__text">{uploading ? "正在上传..." : "拖拽文件到这里，或点击上传"}</p>
                <p className="fm-dropzone__hint">支持 PDF / DOCX / TXT / Markdown</p>
                <input id="fm-file-input" type="file" multiple style={{ display: "none" }} onChange={handleFileSelect} disabled={uploading} />
              </div>
              <div className="fm-upload-kb-select">
                <label>所属知识库</label>
                <select value={uploadKbId} onChange={(event) => setUploadKbId(event.target.value)}>
                  <option value="">请选择知识库</option>
                  {kbs.map((kb) => <option key={kb.id} value={kb.id}>{kb.name}</option>)}
                </select>
              </div>
            </div>

            <div className="fm-card" style={{ marginTop: 16 }}>
              <div className="fm-card__title-row">
                <h3 className="fm-card__title">最近上传</h3>
                <button className="fm-tbl-btn" title="刷新" onClick={fetchFiles}><SvgIcon name="refresh-cw" size={14} /></button>
              </div>
              <div className="fm-recent-list">
                {recentUploads.length === 0 ? (
                  <div className="kb-empty" style={{ padding: "28px 10px" }}>
                    <p style={{ fontSize: 13 }}>暂无上传记录</p>
                  </div>
                ) : recentUploads.map((file) => {
                  const statusMeta = STATUS_META[file.status] || STATUS_META.pending;
                  return (
                    <div key={`recent-${file.kbId}-${file.id}`} className="fm-recent-item">
                      <div className="fm-recent-item__top">
                        <div className="fm-recent-item__info">
                          <div className="fm-recent-item__name">{file.name}</div>
                          <div className="fm-recent-item__size">{file.kbName} · {formatSize(file.size)}</div>
                        </div>
                        <span className="kb-status-tag" style={{ background: statusMeta.bg, color: statusMeta.color, fontSize: 11 }}>{statusMeta.label}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </div>
      <DocumentViewer
        kbId={viewerFile?.kbId}
        document={viewerFile}
        open={Boolean(viewerFile)}
        onClose={() => setViewerFile(null)}
      />
    </div>
  );
}
