import { useEffect, useMemo, useState } from "react";
import { getStoredAuth } from "../api/auth";
import { getKnowledgeBases } from "../api/knowledgeBase";
import { createReportTask } from "../api/report";

const REPORT_TYPES = [
  { value: "technical_review", label: "技术综述" },
  { value: "summary", label: "综合报告" },
  { value: "project_analysis", label: "项目分析" },
  { value: "custom", label: "自定义" },
];

const LENGTHS = [
  { value: "short", label: "短" },
  { value: "medium", label: "中" },
  { value: "long", label: "长" },
];

const DEFAULT_MARKDOWN = `# RAG 系统技术综述

## 1. 背景

随着大语言模型在自然语言处理任务中的广泛应用，如何缓解知识时效性、幻觉问题以及私域知识整合的挑战成为研究热点。

## 2. 核心流程

RAG 系统通常包含问题向量化、知识库检索、上下文组装、模型生成和引用溯源等步骤。

## 3. 技术路线

常见技术路线包括向量检索、混合检索、重排模型、上下文压缩以及提示词工程。

---

引用来源

1. Lewis P., et al. Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.
2. Gao L., et al. Making Large Language Models Better Reasoners with Step-Aware Verifier.`;

function ReportIcon({ name, size = 20 }) {
  const paths = {
    file: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" /><path d="M14 2v6h6" /><path d="M8 13h8M8 17h5" /></>,
    sparkles: <><path d="m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z" /><path d="M5 3v4M3 5h4M19 17v4M17 19h4" /></>,
    copy: <><rect x="9" y="9" width="13" height="13" rx="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></>,
    download: <><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><path d="M7 10l5 5 5-5" /><path d="M12 15V3" /></>,
    save: <><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2Z" /><path d="M17 21v-8H7v8" /><path d="M7 3v5h8" /></>,
    refresh: <><path d="M21 12a9 9 0 1 1-2.64-6.36" /><path d="M21 3v6h-6" /></>,
    chevron: <path d="m6 9 6 6 6-6" />,
  };

  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[name] || paths.file}
    </svg>
  );
}

function normalizeKnowledgeBases(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.knowledge_bases)) return data.knowledge_bases;
  if (Array.isArray(data?.items)) return data.items;
  return [];
}

function formatMarkdown(markdown) {
  return (markdown || "")
    .split(/\n/)
    .map((line, index) => {
      if (line.startsWith("# ")) return <h1 key={index}>{line.slice(2)}</h1>;
      if (line.startsWith("## ")) return <h2 key={index}>{line.slice(3)}</h2>;
      if (line.startsWith("### ")) return <h3 key={index}>{line.slice(4)}</h3>;
      if (line.trim() === "---") return <hr key={index} />;
      if (/^\d+\.\s/.test(line.trim())) return <li key={index}>{line.trim().replace(/^\d+\.\s/, "")}</li>;
      if (!line.trim()) return <br key={index} />;
      return <p key={index}>{line}</p>;
    });
}

export default function ReportPage() {
  const [knowledgeBases, setKnowledgeBases] = useState([]);
  const [kbLoading, setKbLoading] = useState(false);
  const [kbId, setKbId] = useState("");
  const [title, setTitle] = useState("RAG 系统技术综述");
  const [reportType, setReportType] = useState("technical_review");
  const [length, setLength] = useState("medium");
  const [citationFormat, setCitationFormat] = useState("markdown");
  const [instruction, setInstruction] = useState("突出 RAG 核心流程、关键技术与落地价值");
  const [modelName, setModelName] = useState("DeepSeek / GPT");
  const [markdown, setMarkdown] = useState(DEFAULT_MARKDOWN);
  const [task, setTask] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const selectedKb = useMemo(
    () => knowledgeBases.find((kb) => String(kb.id) === String(kbId)),
    [knowledgeBases, kbId]
  );

  useEffect(() => {
    let ignore = false;
    const loadKnowledgeBases = async () => {
      setKbLoading(true);
      setError("");
      try {
        const data = await getKnowledgeBases();
        const list = normalizeKnowledgeBases(data);
        if (!ignore) {
          setKnowledgeBases(list);
          setKbId((current) => current || (list[0]?.id ? String(list[0].id) : ""));
        }
      } catch (err) {
        if (!ignore) setError(err.message || "知识库加载失败");
      } finally {
        if (!ignore) setKbLoading(false);
      }
    };

    loadKnowledgeBases();
    return () => {
      ignore = true;
    };
  }, []);

  const handleGenerate = async () => {
    if (!kbId) {
      setError("请先选择知识库");
      return;
    }
    if (!title.trim()) {
      setError("请输入报告主题");
      return;
    }

    const auth = getStoredAuth();
    const userId = auth?.user?.id || auth?.user?.user_id || 1;
    const workspaceId = selectedKb?.workspace_id || selectedKb?.workspaceId || 1;

    setLoading(true);
    setError("");
    setNotice("");
    try {
      const result = await createReportTask({
        workspace_id: Number(workspaceId),
        user_id: Number(userId),
        kb_id: Number(kbId),
        title: title.trim(),
        report_type: reportType,
        length,
        citation_format: citationFormat,
        instruction: instruction.trim() || null,
        model_name: modelName.trim() || null,
      });
      setTask(result);
      setMarkdown(result?.result_content || "");
      setNotice("报告已生成");
    } catch (err) {
      setError(err.message || "报告生成失败");
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = async () => {
    await navigator.clipboard.writeText(markdown || "");
    setNotice("已复制 Markdown");
  };

  const handleDownload = () => {
    const blob = new Blob([markdown || ""], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${title.trim() || "report"}.md`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    setNotice("已导出 Markdown 文件");
  };

  const handleSave = () => {
    const history = JSON.parse(localStorage.getItem("docpilot_report_history") || "[]");
    localStorage.setItem("docpilot_report_history", JSON.stringify([
      {
        id: task?.task_id || Date.now(),
        title,
        kbName: selectedKb?.name || "",
        createdAt: new Date().toISOString(),
        markdown,
      },
      ...history,
    ].slice(0, 20)));
    setNotice("已保存到本地记录");
  };

  return (
    <main className="report-page">
      <section className="report-generator">
        <div className="report-panel-heading">
          <span className="report-panel-icon"><ReportIcon name="file" size={22} /></span>
          <div>
            <h2>报告生成</h2>
            <p>基于知识库内容快速生成结构化报告</p>
          </div>
        </div>

        <label className="report-field">
          <span>选择知识库</span>
          <div className="report-select-wrap">
            <select value={kbId} onChange={(event) => setKbId(event.target.value)} disabled={kbLoading || loading}>
              <option value="">{kbLoading ? "加载中..." : "请选择知识库"}</option>
              {knowledgeBases.map((kb) => (
                <option key={kb.id} value={String(kb.id)}>{kb.name || `知识库 ${kb.id}`}</option>
              ))}
            </select>
            <ReportIcon name="chevron" size={16} />
          </div>
        </label>

        <label className="report-field">
          <span>报告主题</span>
          <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="请输入报告主题" />
        </label>

        <label className="report-field">
          <span>报告类型</span>
          <div className="report-select-wrap">
            <select value={reportType} onChange={(event) => setReportType(event.target.value)}>
              {REPORT_TYPES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
            <ReportIcon name="chevron" size={16} />
          </div>
        </label>

        <div className="report-field">
          <span>报告长度</span>
          <div className="report-segmented">
            {LENGTHS.map((item) => (
              <button key={item.value} type="button" className={length === item.value ? "is-active" : ""} onClick={() => setLength(item.value)}>
                {item.label}
              </button>
            ))}
          </div>
        </div>

        <label className="report-field">
          <span>引用格式</span>
          <div className="report-select-wrap">
            <select value={citationFormat} onChange={(event) => setCitationFormat(event.target.value)}>
              <option value="markdown">Markdown</option>
              <option value="plain">Plain Text</option>
            </select>
            <ReportIcon name="chevron" size={16} />
          </div>
        </label>

        <label className="report-field">
          <span>使用模型</span>
          <input value={modelName} onChange={(event) => setModelName(event.target.value)} placeholder="DeepSeek / GPT" />
        </label>

        <label className="report-field">
          <span>补充要求</span>
          <textarea value={instruction} onChange={(event) => setInstruction(event.target.value)} rows={4} placeholder="补充报告重点、结构或写作要求" />
        </label>

        {error && <div className="report-alert report-alert--error">{error}</div>}
        {notice && <div className="report-alert report-alert--success">{notice}</div>}

        <button className="report-generate-btn" type="button" onClick={handleGenerate} disabled={loading}>
          <ReportIcon name="sparkles" size={18} />
          <span>{loading ? "生成中..." : "生成报告"}</span>
        </button>
        <p className="report-estimate">预计耗时 20-40 秒</p>
      </section>

      <section className="report-preview">
        <div className="report-preview-top">
          <div>
            <h2>报告预览</h2>
            <div className="report-preview-meta">
              <span>最近生成</span>
              <strong>{task?.title || title}</strong>
              {task?.task_id && <em>任务 #{task.task_id}</em>}
            </div>
          </div>
          <div className="report-actions">
            <button type="button" onClick={handleCopy}><ReportIcon name="copy" size={16} />复制 Markdown</button>
            <button type="button" onClick={handleDownload}><ReportIcon name="download" size={16} />导出 Markdown</button>
            <button type="button" onClick={handleSave}><ReportIcon name="save" size={16} />保存记录</button>
            <button type="button" onClick={handleGenerate} disabled={loading}><ReportIcon name="refresh" size={16} />重新生成</button>
          </div>
        </div>

        <article className="report-markdown">
          {markdown ? formatMarkdown(markdown) : <p className="report-empty">生成完成后会在这里显示报告内容。</p>}
        </article>
      </section>
    </main>
  );
}
