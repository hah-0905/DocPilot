import { useEffect, useMemo, useState } from "react";
import { getDocumentChunks } from "../api/knowledgeBase";

function normalizeChunks(payload) {
  const source = Array.isArray(payload?.chunks) ? payload.chunks : [];
  return source
    .map((chunk, index) => ({
      id: chunk.id ?? index,
      index: Number(chunk.chunk_index ?? chunk.chunk_no ?? chunk.index ?? index + 1),
      content: chunk.content || "",
      tokenCount: chunk.token_count ?? chunk.tokens ?? null,
    }))
    .sort((a, b) => a.index - b.index);
}

export default function DocumentViewer({ kbId, document, open, onClose }) {
  const [chunks, setChunks] = useState([]);
  const [documentMeta, setDocumentMeta] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open || !kbId || !document?.id) return;

    let cancelled = false;
    async function loadChunks() {
      setLoading(true);
      setError("");
      setChunks([]);
      try {
        const data = await getDocumentChunks(kbId, document.id);
        if (cancelled) return;
        setDocumentMeta(data?.document || null);
        setChunks(normalizeChunks(data));
      } catch (err) {
        if (!cancelled) setError(err.message || "文档切片加载失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadChunks();
    return () => {
      cancelled = true;
    };
  }, [document?.id, kbId, open]);

  const title = useMemo(() => {
    return documentMeta?.name || document?.name || "未命名文件";
  }, [document?.name, documentMeta?.name]);

  if (!open) return null;

  return (
    <div className="doc-viewer-overlay" role="presentation" onMouseDown={onClose}>
      <aside
        className="doc-viewer"
        role="dialog"
        aria-modal="true"
        aria-label="文件查看"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="doc-viewer__header">
          <div className="doc-viewer__heading">
            <span className="doc-viewer__eyebrow">文件原文切片</span>
            <h2 className="doc-viewer__title">{title}</h2>
            <div className="doc-viewer__meta">
              <span>{documentMeta?.type || document?.ext || document?.type || "FILE"}</span>
              <span>{chunks.length} 个切片</span>
            </div>
          </div>
          <button className="doc-viewer__close" type="button" onClick={onClose} aria-label="关闭">
            x
          </button>
        </header>

        <div className="doc-viewer__body">
          {loading ? (
            <div className="doc-viewer__state">
              <div className="kb-skeleton" style={{ height: 72, marginBottom: 12 }} />
              <div className="kb-skeleton" style={{ height: 120, marginBottom: 12 }} />
              <div className="kb-skeleton" style={{ height: 96 }} />
            </div>
          ) : error ? (
            <div className="doc-viewer__empty">
              <p>{error}</p>
              <button className="kb-btn kb-btn--outline" type="button" onClick={onClose}>关闭</button>
            </div>
          ) : chunks.length === 0 ? (
            <div className="doc-viewer__empty">
              <p>暂无可查看的切片内容</p>
            </div>
          ) : (
            <div className="doc-viewer__chunks">
              {chunks.map((chunk) => (
                <article className="doc-viewer__chunk" key={chunk.id}>
                  <div className="doc-viewer__chunk-head">
                    <span className="doc-viewer__chunk-no">#{chunk.index}</span>
                    {chunk.tokenCount !== null && <span>{chunk.tokenCount} tokens</span>}
                  </div>
                  <pre className="doc-viewer__chunk-content">{chunk.content}</pre>
                </article>
              ))}
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}
