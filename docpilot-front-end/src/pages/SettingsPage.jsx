import { useCallback, useEffect, useMemo, useState } from "react";
import { getStoredAuth } from "../api/auth";
import {
  getLocalUser,
  updateProfile,
  saveModelSettings,
  saveRetrievalSettings,
  saveReportSettings,
  changePassword,
} from "../api/settings";

/* ===============================================================
   Default settings (used when no backend data yet)
   TODO: replace with backend data when APIs are available
   =============================================================== */
const DEFAULT_MODEL_SETTINGS = {
  defaultModel: "DeepSeek / GPT",
  temperature: 0.7,
  maxTokens: 4096,
  responseLanguage: "简体中文",
};

const DEFAULT_RETRIEVAL_SETTINGS = {
  topK: 10,
  similarityThreshold: 0.65,
  enableRerank: true,
  showSources: true,
};

const DEFAULT_REPORT_SETTINGS = {
  defaultReportType: "综合报告",
  defaultLength: "中等（约1500字）",
  citationStyle: "APA",
  exportFormat: "PDF",
};

/* ===== SvgIcon ===== */
function SvgIcon({ name, size = 20 }) {
  const s = size;
  const paths = {
    edit: <><path d="M17 3a2.85 2.85 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" /></>,
    eye: <><path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z" /><circle cx="12" cy="12" r="2.5" /></>,
    "eye-off": <><path d="m3 3 18 18" /><path d="M10.6 10.7a2.5 2.5 0 0 0 2.8 2.8" /><path d="M9.4 5.4A9.1 9.1 0 0 1 12 5c6 0 9.5 7 9.5 7a15.9 15.9 0 0 1-2.2 3.1" /><path d="M6.2 6.8C3.9 8.4 2.5 12 2.5 12s3.5 7 9.5 7c1.6 0 3-.5 4.2-1.2" /></>,
    "chevron-down": <><path d="m6 9 6 6 6-6" /></>,
    search: <><circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" /></>,
    layers: <><path d="m12 3 9 5-9 5-9-5 9-5Z" /><path d="m4 12 8 4.5 8-4.5" /><path d="m4 16 8 4.5 8-4.5" /></>,
    file: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Z" /><path d="M14 2v6h6" /></>,
    settings: <><circle cx="12" cy="12" r="3" /><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" /></>,
    "chat-dot": <><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10Z" /><circle cx="12" cy="10" r="1" /></>,
    plus: <><circle cx="12" cy="12" r="10" /><path d="M8 12h8M12 8v8" /></>,
    "log-out": <><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" /></>,
    check: <><polyline points="20 6 9 17 4 12" /></>,
  };
  return <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

/* ===============================================================
   SettingsPage
   =============================================================== */
export default function SettingsPage({ onNavigate, onLogout }) {
  // ---- User ----
  const user = useMemo(() => getLocalUser(), []);
  const displayName = user?.display_name || user?.username || "用户";
  const email = user?.email || "";
  const role = user?.role || "普通用户";
  const joinedAt = user?.created_at ? user.created_at.replace("T", " ").slice(0, 10) : "";

  // ---- Model settings ----
  const [model, setModel] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("docpilot_model_settings") || "null") || DEFAULT_MODEL_SETTINGS;
    } catch { return DEFAULT_MODEL_SETTINGS; }
  });
  const [modelSaving, setModelSaving] = useState(false);
  const [modelSaved, setModelSaved] = useState(false);

  // ---- Retrieval settings ----
  const [retrieval, setRetrieval] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("docpilot_retrieval_settings") || "null") || DEFAULT_RETRIEVAL_SETTINGS;
    } catch { return DEFAULT_RETRIEVAL_SETTINGS; }
  });
  const [retrievalSaving, setRetrievalSaving] = useState(false);
  const [retrievalSaved, setRetrievalSaved] = useState(false);

  // ---- Report settings ----
  const [report, setReport] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("docpilot_report_settings") || "null") || DEFAULT_REPORT_SETTINGS;
    } catch { return DEFAULT_REPORT_SETTINGS; }
  });
  const [reportSaving, setReportSaving] = useState(false);
  const [reportSaved, setReportSaved] = useState(false);

  // ---- Password ----
  const [pwForm, setPwForm] = useState({ current: "", newPw: "", confirm: "" });
  const [pwVisible, setPwVisible] = useState({ current: false, newPw: false, confirm: false });
  const [pwErrors, setPwErrors] = useState({});
  const [pwSaving, setPwSaving] = useState(false);
  const [pwSuccess, setPwSuccess] = useState(false);

  // ---- Toast ----
  const [toast, setToast] = useState(null); // { message, type }

  const showToast = useCallback((message, type = "success") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  }, []);

  // ---- Save model ----
  const handleSaveModel = async () => {
    setModelSaving(true);
    setModelSaved(false);
    try {
      await saveModelSettings(model);
      localStorage.setItem("docpilot_model_settings", JSON.stringify(model));
      showToast("模型设置已保存（本地）");

    } catch (err) { showToast(err.message, "error"); }
    finally { setModelSaving(false); setModelSaved(true); }
  };

  // ---- Save retrieval ----
  const handleSaveRetrieval = async () => {
    setRetrievalSaving(true);
    setRetrievalSaved(false);
    try {
      await saveRetrievalSettings(retrieval);
      localStorage.setItem("docpilot_retrieval_settings", JSON.stringify(retrieval));
      showToast("检索设置已保存（本地）");
    } catch (err) { showToast(err.message, "error"); }
    finally { setRetrievalSaving(false); setRetrievalSaved(true); }
  };

  // ---- Save report ----
  const handleSaveReport = async () => {
    setReportSaving(true);
    setReportSaved(false);
    try {
      await saveReportSettings(report);
      localStorage.setItem("docpilot_report_settings", JSON.stringify(report));
      showToast("报告设置已保存（本地）");
    } catch (err) { showToast(err.message, "error"); }
    finally { setReportSaving(false); setReportSaved(true); }
  };

  // ---- Change password ----
  const handleChangePassword = async (e) => {
    e.preventDefault();
    const errs = {};
    if (!pwForm.current) errs.current = "请输入当前密码";
    if (!pwForm.newPw) errs.newPw = "请输入新密码";
    else if (pwForm.newPw.length < 8) errs.newPw = "密码至少 8 位";
    if (!pwForm.confirm) errs.confirm = "请再次输入新密码";
    else if (pwForm.newPw !== pwForm.confirm) errs.confirm = "两次输入的密码不一致";
    setPwErrors(errs);
    if (Object.keys(errs).length) return;

    setPwSaving(true);
    setPwSuccess(false);
    try {
      await changePassword({ currentPassword: pwForm.current, newPassword: pwForm.newPw, confirmPassword: pwForm.confirm });
      setPwForm({ current: "", newPw: "", confirm: "" });
      showToast("密码修改成功");
      setPwSuccess(true);
    } catch (err) { showToast(err.message, "error"); }
    finally { setPwSaving(false); }
  };

  // ---- Logout ----
  const handleLogout = () => {
    if (!window.confirm("确定要退出登录吗？")) return;
    onLogout();
  };

  // ---- Edit profile ----
  const handleEditProfile = () => {
    // TODO: implement profile edit modal when backend API is available
    showToast("个人资料编辑接口待接入", "error");
  };

  // ---- Toast ----
  const Toast = toast ? (
    <div className={`st-toast st-toast--${toast.type}`}>
      {toast.type === "success" && <SvgIcon name="check" size={16} />}
      <span>{toast.message}</span>
    </div>
  ) : null;

  /* ============================================================
     Render
     ============================================================ */
  return (
    <div className="kb-page st-page">
      {/* Sidebar */}
      <aside className="kb-sidebar">
        <div className="kb-sidebar__brand">
          <span className="kb-sidebar__logo" aria-hidden="true"><span /></span>
          <span className="kb-sidebar__name">DocPilot</span>
        </div>
        <button className="kb-sidebar__new-btn" onClick={() => onNavigate("/chat")}><SvgIcon name="plus" size={18} /><span>新建对话</span></button>
        <nav className="kb-sidebar__nav">
          <a className="kb-nav-item" href="#" onClick={(e) => { e.preventDefault(); onNavigate("/knowledge-base"); }}>
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
          <a className="kb-nav-item" href="#" onClick={(e) => { e.preventDefault(); onNavigate("/files"); }}>
            <SvgIcon name="file" size={18} /><span>文件管理</span>
          </a>
          <a className="kb-nav-item kb-nav-item--active" href="#" onClick={(e) => e.preventDefault()}>
            <SvgIcon name="settings" size={18} /><span>设置</span>
          </a>
        </div>
      </aside>

      {/* Main */}
      <div className="kb-main">
        <div className="st-content">
          <div className="st-header">
            <h1 className="st-header__title">设置</h1>
            <p className="st-header__subtitle">管理账号、模型、检索和报告生成偏好</p>
          </div>

          {Toast}

          {/* ===== 1. Profile ===== */}
          <div className="st-card">
            <h2 className="st-card__title">个人信息</h2>
            <div className="st-profile">
              <div className="st-avatar">{displayName[0]?.toUpperCase() || "U"}</div>
              <div className="st-profile__fields">
                <div className="st-field">
                  <span className="st-field__label">用户名</span>
                  <span className="st-field__value">{displayName}</span>
                </div>
                <div className="st-field">
                  <span className="st-field__label">邮箱</span>
                  <span className="st-field__value">{email}</span>
                </div>
                <div className="st-field">
                  <span className="st-field__label">角色</span>
                  <span className="st-field__value">{role}</span>
                </div>
                <div className="st-field">
                  <span className="st-field__label">加入时间</span>
                  <span className="st-field__value">{joinedAt}</span>
                </div>
              </div>
              <button className="st-btn st-btn--outline" onClick={handleEditProfile}>
                <SvgIcon name="edit" size={15} />
                <span>编辑资料</span>
              </button>
            </div>
          </div>

          {/* ===== 2. Model settings ===== */}
          <div className="st-card">
            <h2 className="st-card__title">模型设置</h2>
            <div className="st-form-grid">
              <div className="st-form-group">
                <label>默认模型</label>
                <select value={model.defaultModel} onChange={(e) => setModel({ ...model, defaultModel: e.target.value })}>
                  <option>DeepSeek / GPT</option>
                  <option>GPT-4o</option>
                  <option>DeepSeek-V3</option>
                  <option>Claude 4</option>
                </select>
              </div>
              <div className="st-form-group">
                <label>Temperature <span className="st-val">{model.temperature}</span></label>
                <input type="range" min="0" max="2" step="0.1" value={model.temperature}
                  onChange={(e) => setModel({ ...model, temperature: parseFloat(e.target.value) })} />
                <div className="st-slider-labels"><span>0</span><span>0.5</span><span>1</span><span>1.5</span><span>2</span></div>
              </div>
              <div className="st-form-group">
                <label>Max Tokens</label>
                <select value={model.maxTokens} onChange={(e) => setModel({ ...model, maxTokens: parseInt(e.target.value) })}>
                  <option value={1024}>1024</option>
                  <option value={2048}>2048</option>
                  <option value={4096}>4096</option>
                  <option value={8192}>8192</option>
                </select>
              </div>
              <div className="st-form-group">
                <label>回复语言</label>
                <select value={model.responseLanguage} onChange={(e) => setModel({ ...model, responseLanguage: e.target.value })}>
                  <option>简体中文</option>
                  <option>English</option>
                  <option>跟随用户输入</option>
                </select>
              </div>
            </div>
            <div className="st-card-actions">
              <button className="st-btn st-btn--primary" disabled={modelSaving} onClick={handleSaveModel}>
                {modelSaving ? "保存中..." : "保存设置"}
              </button>
              {modelSaved && <span className="st-hint">已保存（本地存储，TODO: 对接后端接口）</span>}
            </div>
          </div>

          {/* ===== 3. Retrieval settings ===== */}
          <div className="st-card">
            <h2 className="st-card__title">检索设置</h2>
            <div className="st-form-grid">
              <div className="st-form-group">
                <label>Top K <span className="st-val">{retrieval.topK}</span></label>
                <input type="range" min="1" max="50" value={retrieval.topK}
                  onChange={(e) => setRetrieval({ ...retrieval, topK: parseInt(e.target.value) })} />
                <div className="st-slider-labels"><span>1</span><span>10</span><span>20</span><span>30</span><span>50</span></div>
              </div>
              <div className="st-form-group">
                <label>相似度阈值 <span className="st-val">{retrieval.similarityThreshold}</span></label>
                <input type="range" min="0" max="1" step="0.01" value={retrieval.similarityThreshold}
                  onChange={(e) => setRetrieval({ ...retrieval, similarityThreshold: parseFloat(e.target.value) })} />
                <div className="st-slider-labels"><span>0</span><span>0.25</span><span>0.5</span><span>0.75</span><span>1</span></div>
              </div>
              <div className="st-form-group">
                <label>启用 Rerank</label>
                <div className="st-toggle-group">
                  <button className={`st-toggle${retrieval.enableRerank ? " st-toggle--on" : ""}`}
                    onClick={() => setRetrieval({ ...retrieval, enableRerank: !retrieval.enableRerank })}>
                    <span className="st-toggle__knob" />
                  </button>
                  <span className="st-toggle__label">{retrieval.enableRerank ? "已开启" : "已关闭"}</span>
                </div>
              </div>
              <div className="st-form-group">
                <label>引用来源展示</label>
                <div className="st-toggle-group">
                  <button className={`st-toggle${retrieval.showSources ? " st-toggle--on" : ""}`}
                    onClick={() => setRetrieval({ ...retrieval, showSources: !retrieval.showSources })}>
                    <span className="st-toggle__knob" />
                  </button>
                  <span className="st-toggle__label">{retrieval.showSources ? "已开启" : "已关闭"}</span>
                </div>
              </div>
            </div>
            <div className="st-card-actions">
              <button className="st-btn st-btn--primary" disabled={retrievalSaving} onClick={handleSaveRetrieval}>
                {retrievalSaving ? "保存中..." : "保存设置"}
              </button>
              {retrievalSaved && <span className="st-hint">已保存（本地存储，TODO: 对接后端接口）</span>}
            </div>
          </div>

          {/* ===== 4. Report settings ===== */}
          <div className="st-card">
            <h2 className="st-card__title">报告设置</h2>
            <div className="st-form-grid">
              <div className="st-form-group">
                <label>默认报告类型</label>
                <select value={report.defaultReportType} onChange={(e) => setReport({ ...report, defaultReportType: e.target.value })}>
                  <option>综合报告</option><option>学术综述</option><option>项目分析</option><option>合同分析</option><option>自定义</option>
                </select>
              </div>
              <div className="st-form-group">
                <label>默认长度</label>
                <select value={report.defaultLength} onChange={(e) => setReport({ ...report, defaultLength: e.target.value })}>
                  <option>简短（约800字）</option><option>中等（约1500字）</option><option>详细（约3000字）</option>
                </select>
              </div>
              <div className="st-form-group">
                <label>引用格式</label>
                <select value={report.citationStyle} onChange={(e) => setReport({ ...report, citationStyle: e.target.value })}>
                  <option>APA</option><option>MLA</option><option>Chicago</option><option>GB/T 7714</option>
                </select>
              </div>
              <div className="st-form-group">
                <label>导出格式</label>
                <select value={report.exportFormat} onChange={(e) => setReport({ ...report, exportFormat: e.target.value })}>
                  <option>PDF</option><option>DOCX</option><option>Markdown</option><option>HTML</option>
                </select>
              </div>
            </div>
            <div className="st-card-actions">
              <button className="st-btn st-btn--primary" disabled={reportSaving} onClick={handleSaveReport}>
                {reportSaving ? "保存中..." : "保存设置"}
              </button>
              {reportSaved && <span className="st-hint">已保存（本地存储，TODO: 对接后端接口）</span>}
            </div>
          </div>

          {/* ===== 5. Security ===== */}
          <div className="st-card">
            <h2 className="st-card__title">安全设置</h2>
            <form onSubmit={handleChangePassword} className="st-form-grid">
              <PwField label="当前密码" name="current" value={pwForm.current}
                visible={pwVisible.current}
                onToggle={() => setPwVisible({ ...pwVisible, current: !pwVisible.current })}
                error={pwErrors.current}
                onChange={(v) => { setPwForm({ ...pwForm, current: v }); setPwErrors({ ...pwErrors, current: "" }); }} />
              <PwField label="新密码" name="newPw" value={pwForm.newPw}
                visible={pwVisible.newPw}
                onToggle={() => setPwVisible({ ...pwVisible, newPw: !pwVisible.newPw })}
                error={pwErrors.newPw}
                onChange={(v) => { setPwForm({ ...pwForm, newPw: v }); setPwErrors({ ...pwErrors, newPw: "" }); }} />
              <PwField label="确认新密码" name="confirm" value={pwForm.confirm}
                visible={pwVisible.confirm}
                onToggle={() => setPwVisible({ ...pwVisible, confirm: !pwVisible.confirm })}
                error={pwErrors.confirm}
                onChange={(v) => { setPwForm({ ...pwForm, confirm: v }); setPwErrors({ ...pwErrors, confirm: "" }); }} />
              <div className="st-pw-hint">密码长度至少 8 位，建议包含大小写字母、数字和特殊字符</div>
              <div className="st-card-actions" style={{ marginTop: 8 }}>
                <button type="submit" className="st-btn st-btn--outline" disabled={pwSaving}>
                  {pwSaving ? "修改中..." : "修改密码"}
                </button>
                <button type="button" className="st-btn st-btn--danger" onClick={handleLogout}>
                  <SvgIcon name="log-out" size={15} />
                  <span>退出登录</span>
                </button>
              </div>
            </form>
          </div>

          {/* Footer hint */}
          <div style={{ textAlign: "center", padding: "20px 0 40px", fontSize: 12, color: "#94a3b8" }}>
            DocPilot v0.1.0 · 设置数据暂存于本地，待后端设置接口上线后自动迁移
          </div>
        </div>
      </div>
    </div>
  );
}

/* ===== Password field sub-component ===== */
function PwField({ label, value, visible, onToggle, error, onChange }) {
  const inputId = `pw-${label}`;
  return (
    <div className="st-form-group">
      <label htmlFor={inputId}>{label}</label>
      <div className={`st-pw-shell${error ? " st-pw-shell--error" : ""}`}>
        <input id={inputId} type={visible ? "text" : "password"} placeholder={label} value={value}
          onChange={(e) => onChange(e.target.value)} />
        <button type="button" className="st-pw-eye" onClick={onToggle} tabIndex={-1}>
          <SvgIcon name={visible ? "eye-off" : "eye"} size={18} />
        </button>
      </div>
      {error && <p className="st-field-error">{error}</p>}
    </div>
  );
}
