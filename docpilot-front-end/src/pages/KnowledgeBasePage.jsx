import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createKnowledgeBase,
  deleteKnowledgeBase,
  getDocuments,
  getKnowledgeBases,
  rebuildKnowledgeBaseIndex,
  uploadKnowledgeBaseFile,
} from "../api/knowledgeBase";

function SvgIcon({ name, size = 20 }) {
  const paths = {
    layers: <><path d="m12 3 9 5-9 5-9-5 9-5Z" /><path d="m4 12 8 4.5 8-4.5M4 16l8 4.5 8-4.5" /></>,
    plus: <><path d="M12 5v14M5 12h14" /></>,
    search: <><circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" /></>,
    upload: <><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12" /></>,
    refresh: <><path d="M20 7V3h-4M4 17v4h4M5.5 9a7 7 0 0 1 11.8-3.3L20 8M4 16l2.7 2.3A7 7 0 0 0 18.5 15" /></>,
    trash: <><path d="M3 6h18M8 6V4h8v2M19 6l-1 15H6L5 6" /></>,
    more: <><circle cx="5" cy="12" r="1" /><circle cx="12" cy="12" r="1" /><circle cx="19" cy="12" r="1" /></>,
    arrow: <><path d="M5 12h14M13 6l6 6-6 6" /></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

function toList(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.items)) return data.items;
  if (Array.isArray(data?.list)) return data.list;
  if (Array.isArray(data?.records)) return data.records;
  return [];
}

function getChunkCount(document) {
  const value = Number(document.chunk_count ?? document.chunks ?? document.vector_count ?? document.embedding_count ?? 0);
  return Number.isFinite(value) ? value : 0;
}

function mapKnowledgeBase(dto) {
  const rawStatus = String(dto.status || "").toLowerCase();
  return {
    id: String(dto.id),
    name: dto.name || "未命名知识库",
    description: dto.description || "",
    updatedAt: dto.updated_at || dto.created_at || "",
    status: rawStatus === "deleted" ? "deleted" : rawStatus === "active" ? "normal" : "unknown",
    fileCount: 0,
    chunkCount: 0,
  };
}

async function withDocumentStats(knowledgeBase) {
  try {
    const documents = toList(await getDocuments(knowledgeBase.id));
    return {
      ...knowledgeBase,
      fileCount: documents.length,
      chunkCount: documents.reduce((total, document) => total + getChunkCount(document), 0),
    };
  } catch {
    return knowledgeBase;
  }
}

function formatUpdatedAt(value) {
  if (!value) return "暂无更新记录";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value).replace("T", " ").slice(0, 16);
  const diff = Date.now() - date.getTime();
  const minutes = Math.max(0, Math.floor(diff / 60000));
  if (minutes < 1) return "刚刚";
  if (minutes < 60) return `${minutes} 分钟前`;
  if (minutes < 1440) return `${Math.floor(minutes / 60)} 小时前`;
  return date.toLocaleDateString("zh-CN", { year: "numeric", month: "short", day: "numeric" });
}

export default function KnowledgeBasePage({ onNavigate }) {
  const [knowledgeBases, setKnowledgeBases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [searchText, setSearchText] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sortBy, setSortBy] = useState("updated");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createForm, setCreateForm] = useState({ name: "", description: "" });
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [uploadingId, setUploadingId] = useState(null);
  const [actionLoading, setActionLoading] = useState({});
  const [openMenuId, setOpenMenuId] = useState(null);

  const fetchList = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const items = toList(await getKnowledgeBases()).map(mapKnowledgeBase);
      setKnowledgeBases(await Promise.all(items.map(withDocumentStats)));
    } catch (requestError) {
      setError(requestError.message || "知识库加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchList(); }, [fetchList]);

  useEffect(() => {
    if (!openMenuId) return undefined;
    const close = (event) => { if (!event.target.closest(".kb-card__menu-wrap")) setOpenMenuId(null); };
    window.addEventListener("click", close);
    return () => window.removeEventListener("click", close);
  }, [openMenuId]);

  useEffect(() => {
    const focusSearch = () => document.querySelector(".kb-search-box input")?.focus();
    window.addEventListener("docpilot:focus-search", focusSearch);
    return () => window.removeEventListener("docpilot:focus-search", focusSearch);
  }, []);

  const filteredKnowledgeBases = useMemo(() => {
    const query = searchText.trim().toLowerCase();
    return [...knowledgeBases]
      .filter((item) => !query || item.name.toLowerCase().includes(query) || item.description.toLowerCase().includes(query))
      .filter((item) => statusFilter === "all" || item.status === statusFilter)
      .sort((a, b) => sortBy === "name" ? a.name.localeCompare(b.name, "zh") : (b.updatedAt || "").localeCompare(a.updatedAt || ""));
  }, [knowledgeBases, searchText, sortBy, statusFilter]);

  const notifyChanged = () => window.dispatchEvent(new CustomEvent("docpilot:knowledge-bases-changed"));

  const openCreateModal = () => {
    setCreateError("");
    setShowCreateModal(true);
  };

  const closeCreateModal = () => {
    if (creating) return;
    setCreateError("");
    setShowCreateModal(false);
  };

  const handleCreate = async (event) => {
    event.preventDefault();
    if (!createForm.name.trim()) return;
    setCreateError("");
    setCreating(true);
    try {
      await createKnowledgeBase({ name: createForm.name.trim(), description: createForm.description.trim() });
      setShowCreateModal(false);
      setCreateForm({ name: "", description: "" });
      await fetchList();
      notifyChanged();
    } catch (requestError) {
      setCreateError(requestError.message || "创建失败，请稍后重试");
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteConfirm) return;
    setDeleting(true);
    try {
      await deleteKnowledgeBase(deleteConfirm.id);
      setDeleteConfirm(null);
      await fetchList();
      notifyChanged();
    } catch (requestError) {
      alert(requestError.message || "删除失败");
    } finally {
      setDeleting(false);
    }
  };

  const handleUpload = (knowledgeBase) => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".pdf,.doc,.docx,.txt,.md,.markdown";
    input.onchange = async (event) => {
      const file = event.target.files?.[0];
      if (!file) return;
      setUploadingId(knowledgeBase.id);
      try {
        await uploadKnowledgeBaseFile(knowledgeBase.id, file);
        await fetchList();
      } catch (requestError) {
        alert(requestError.message || "上传失败");
      } finally {
        setUploadingId(null);
      }
    };
    input.click();
  };

  const handleRebuild = async (knowledgeBase) => {
    if (!window.confirm(`确定重建「${knowledgeBase.name}」的索引吗？`)) return;
    setActionLoading((state) => ({ ...state, [knowledgeBase.id]: true }));
    setOpenMenuId(null);
    try {
      await rebuildKnowledgeBaseIndex(knowledgeBase.id);
      alert("重建索引任务已提交");
    } catch (requestError) {
      alert(requestError.message || "重建失败");
    } finally {
      setActionLoading((state) => ({ ...state, [knowledgeBase.id]: false }));
    }
  };

  return (
    <div className="kb-workspace-page">
      <div className="kb-list-header">
        <div><h1 className="kb-list-title">知识库</h1><p className="kb-list-subtitle">管理用于问答、搜索和报告生成的知识。</p></div>
        <button className="kb-primary-btn" type="button" onClick={openCreateModal}><SvgIcon name="plus" size={17} /><span>新建知识库</span></button>
      </div>

      <div className="kb-toolbar">
        <label className="kb-search-box"><SvgIcon name="search" size={16} /><input type="search" placeholder="搜索知识库" value={searchText} onChange={(event) => setSearchText(event.target.value)} /></label>
        <select className="kb-select" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} aria-label="状态筛选"><option value="all">全部状态</option><option value="normal">正常</option><option value="unknown">未知</option></select>
        <select className="kb-select" value={sortBy} onChange={(event) => setSortBy(event.target.value)} aria-label="排序方式"><option value="updated">最近更新</option><option value="name">按名称</option></select>
      </div>

      {loading ? <div className="kb-loading">{[1, 2, 3].map((item) => <div className="kb-skeleton kb-card" key={item} />)}</div>
        : error ? <div className="kb-empty"><p>{error}</p><button className="kb-btn kb-btn--outline" type="button" onClick={fetchList}>重试</button></div>
          : filteredKnowledgeBases.length === 0 ? <div className="kb-empty"><span className="kb-empty__icon"><SvgIcon name="layers" size={24} /></span><h2>{searchText ? "没有匹配的知识库" : "还没有知识库"}</h2><p>{searchText ? "尝试更换搜索关键词。" : "创建一个知识库，开始连接你的文档。"}</p>{!searchText && <button className="kb-primary-btn" type="button" onClick={openCreateModal}>新建知识库</button>}</div>
            : <div className="kb-card-list">{filteredKnowledgeBases.map((knowledgeBase) => (
              <article className="kb-card" key={knowledgeBase.id} onDoubleClick={() => onNavigate(`/knowledge-base/${knowledgeBase.id}`)}>
                <div className="kb-card__top">
                  <span className="kb-card__icon"><SvgIcon name="layers" size={20} /></span>
                  <div className="kb-card__info"><h2 className="kb-card__name">{knowledgeBase.name}</h2><p className="kb-card__desc">{knowledgeBase.description || "暂无描述"}</p></div>
                  <div className="kb-card__actions">
                    <button className="kb-action-btn" type="button" disabled={uploadingId === knowledgeBase.id} onClick={() => handleUpload(knowledgeBase)}><SvgIcon name="upload" size={14} />{uploadingId === knowledgeBase.id ? "上传中" : "上传"}</button>
                    <button className="kb-action-btn kb-action-btn--enter" type="button" onClick={() => onNavigate(`/knowledge-base/${knowledgeBase.id}`)}>进入<SvgIcon name="arrow" size={14} /></button>
                    <div className="kb-card__menu-wrap">
                      <button className="kb-action-btn kb-action-btn--icon" type="button" aria-label={`更多 ${knowledgeBase.name}`} aria-expanded={openMenuId === knowledgeBase.id} onClick={(event) => { event.stopPropagation(); setOpenMenuId((id) => id === knowledgeBase.id ? null : knowledgeBase.id); }}><SvgIcon name="more" size={17} /></button>
                      {openMenuId === knowledgeBase.id && <div className="kb-card__menu"><button type="button" disabled={actionLoading[knowledgeBase.id]} onClick={() => handleRebuild(knowledgeBase)}><SvgIcon name="refresh" size={14} />{actionLoading[knowledgeBase.id] ? "重建中" : "重建索引"}</button><button className="is-danger" type="button" onClick={() => { setDeleteConfirm(knowledgeBase); setOpenMenuId(null); }}><SvgIcon name="trash" size={14} />删除</button></div>}
                    </div>
                  </div>
                </div>
                <div className="kb-card__meta"><span>{knowledgeBase.fileCount} 个文件</span><span>{knowledgeBase.chunkCount} 个切片</span><span>{formatUpdatedAt(knowledgeBase.updatedAt)}</span></div>
              </article>
            ))}</div>}

      <div className="kb-list-footer">共 {filteredKnowledgeBases.length} 个知识库</div>

      {showCreateModal && (
        <div className="kb-overlay" onMouseDown={(event) => { if (event.target === event.currentTarget) closeCreateModal(); }}>
          <div className="kb-modal" role="dialog" aria-modal="true" aria-labelledby="create-kb-title">
            <h3 className="kb-modal__title" id="create-kb-title">新建知识库</h3>
            <form onSubmit={handleCreate}>
              <div className="kb-modal__field">
                <label htmlFor="kb-name">名称</label>
                <input id="kb-name" value={createForm.name} onChange={(event) => { setCreateError(""); setCreateForm((form) => ({ ...form, name: event.target.value })); }} placeholder="例如：项目资料" autoFocus />
              </div>
              <div className="kb-modal__field">
                <label htmlFor="kb-description">描述（可选）</label>
                <textarea id="kb-description" rows={3} value={createForm.description} onChange={(event) => { setCreateError(""); setCreateForm((form) => ({ ...form, description: event.target.value })); }} placeholder="这个知识库用于什么？" />
              </div>
              {createError && <p className="kb-modal__error" role="alert">{createError}</p>}
              <div className="kb-modal__actions">
                <button className="kb-btn kb-btn--outline" type="button" disabled={creating} onClick={closeCreateModal}>取消</button>
                <button className="kb-btn kb-btn--primary" type="submit" disabled={creating || !createForm.name.trim()}>{creating ? "创建中..." : "创建"}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {deleteConfirm && <div className="kb-overlay" onMouseDown={(event) => { if (event.target === event.currentTarget) setDeleteConfirm(null); }}><div className="kb-modal" role="dialog" aria-modal="true" aria-labelledby="delete-kb-title"><h3 className="kb-modal__title" id="delete-kb-title">删除知识库</h3><p className="kb-modal__description">确定删除「{deleteConfirm.name}」吗？此操作不可撤销。</p><div className="kb-modal__actions"><button className="kb-btn kb-btn--outline" type="button" onClick={() => setDeleteConfirm(null)}>取消</button><button className="kb-btn kb-btn--danger" type="button" disabled={deleting} onClick={handleDelete}>{deleting ? "删除中..." : "确认删除"}</button></div></div></div>}
    </div>
  );
}
