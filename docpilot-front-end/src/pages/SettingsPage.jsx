import { useCallback, useEffect, useState } from "react";
import { getStoredAuth } from "../api/auth";
import {
  getLocalUser,
  getModelSettingWorkspaces,
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
  modelKey: "deepseek-chat",
  temperature: 0.7,
  maxTokens: 4096,
  responseLanguage: "zh-CN",
};

const MODEL_STORAGE_KEY = "docpilot_model_settings";
const MODEL_OPTIONS = [
  { value: "deepseek-chat", label: "DeepSeek Chat" },
  { value: "deepseek-reasoner", label: "DeepSeek Reasoner" },
];

const LANGUAGE_OPTIONS = [
  { value: "zh-CN", label: "简体中文" },
  { value: "en-US", label: "English" },
  { value: "auto", label: "跟随用户输入" },
];

function readModelSettings() {
  try {
    const stored = JSON.parse(localStorage.getItem(MODEL_STORAGE_KEY) || "null");
    if (!stored) return DEFAULT_MODEL_SETTINGS;

    const legacyModelMap = {
      "DeepSeek / GPT": "deepseek-chat",
      "DeepSeek-V3": "deepseek-chat",
    };
    const legacyLanguageMap = {
      "简体中文": "zh-CN",
      English: "en-US",
      "跟随用户输入": "auto",
    };

    return {
      modelKey: stored.modelKey || legacyModelMap[stored.defaultModel] || DEFAULT_MODEL_SETTINGS.modelKey,
      temperature: Number(stored.temperature ?? DEFAULT_MODEL_SETTINGS.temperature),
      maxTokens: Number(stored.maxTokens ?? DEFAULT_MODEL_SETTINGS.maxTokens),
      responseLanguage:
        legacyLanguageMap[stored.responseLanguage] ||
        stored.responseLanguage ||
        DEFAULT_MODEL_SETTINGS.responseLanguage,
    };
  } catch {
    return DEFAULT_MODEL_SETTINGS;
  }
}

const DEFAULT_RETRIEVAL_SETTINGS = {
  topK: 10,
  similarityThreshold: 0.65,
  enableRerank: true,
  showSources: true,
};

const DEFAULT_REPORT_SETTINGS = {
  defaultReportType: "general",
  defaultLength: "medium",
  citationStyle: "apa",
  exportFormat: "markdown",
};

function readReportSettings() {
  try {
    const stored = JSON.parse(localStorage.getItem("docpilot_report_settings") || "null");
    if (!stored) return DEFAULT_REPORT_SETTINGS;

    const reportTypeMap = {
      "综合报告": "general",
      "学术综述": "academic_review",
      "项目分析": "project_analysis",
      "合同分析": "contract_analysis",
      "自定义": "custom",
    };
    const lengthMap = {
      "简短（约800字）": "short",
      "中等（约1500字）": "medium",
      "详细（约3000字）": "long",
    };
    const citationMap = { APA: "apa", MLA: "mla", Chicago: "chicago", "GB/T 7714": "gb_t_7714" };
    const exportMap = { PDF: "pdf", DOCX: "docx", Markdown: "markdown", HTML: "html" };

    return {
      defaultReportType: reportTypeMap[stored.defaultReportType] || stored.defaultReportType || DEFAULT_REPORT_SETTINGS.defaultReportType,
      defaultLength: lengthMap[stored.defaultLength] || stored.defaultLength || DEFAULT_REPORT_SETTINGS.defaultLength,
      citationStyle: citationMap[stored.citationStyle] || stored.citationStyle || DEFAULT_REPORT_SETTINGS.citationStyle,
      exportFormat: exportMap[stored.exportFormat] || stored.exportFormat || DEFAULT_REPORT_SETTINGS.exportFormat,
    };
  } catch {
    return DEFAULT_REPORT_SETTINGS;
  }
}

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
  const [user, setUser] = useState(() => getLocalUser());
  const displayName = user?.display_name || user?.username || "用户";
  const email = user?.email || "";
  const role = user?.role || "普通用户";
  const joinedAt = user?.created_at ? user.created_at.replace("T", " ").slice(0, 10) : "";
  const [isEditingProfile, setIsEditingProfile] = useState(false);
  const [profileForm, setProfileForm] = useState({ username: user?.username || "", email: user?.email || "" });
  const [profileErrors, setProfileErrors] = useState({});
  const [profileSaving, setProfileSaving] = useState(false);

  // ---- Model settings ----
  const [model, setModel] = useState(readModelSettings);
  const [workspaceId, setWorkspaceId] = useState("");
  const [workspaces, setWorkspaces] = useState([]);
  const [workspaceLoading, setWorkspaceLoading] = useState(true);
  const [workspaceLoadError, setWorkspaceLoadError] = useState("");
  const [modelSaving, setModelSaving] = useState(false);
  const [modelSaved, setModelSaved] = useState(false);

  useEffect(() => {
    let active = true;

    getModelSettingWorkspaces()
      .then((items) => {
        if (!active) return;
        setWorkspaces(items);
        const cachedWorkspaceId = Number(localStorage.getItem("docpilot_model_workspace_id"));
        const cachedWorkspace = items.find((item) => item.id === cachedWorkspaceId);
        if (cachedWorkspace) {
          setWorkspaceId(String(cachedWorkspace.id));
        } else if (items[0]) {
          setWorkspaceId(String(items[0].id));
        }
      })
      .catch((error) => {
        if (active) setWorkspaceLoadError(error.message || "工作空间加载失败");
      })
      .finally(() => {
        if (active) setWorkspaceLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    setModelSaved(false);
    setRetrievalSaved(false);
    setReportSaved(false);
  }, [workspaceId]);

  // ---- Retrieval settings ----
  const [retrieval, setRetrieval] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("docpilot_retrieval_settings") || "null") || DEFAULT_RETRIEVAL_SETTINGS;
    } catch { return DEFAULT_RETRIEVAL_SETTINGS; }
  });
  const [retrievalSaving, setRetrievalSaving] = useState(false);
  const [retrievalSaved, setRetrievalSaved] = useState(false);

  // ---- Report settings ----
  const [report, setReport] = useState(readReportSettings);
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
    const normalizedWorkspaceId = Number(workspaceId);
    if (!Number.isInteger(normalizedWorkspaceId) || normalizedWorkspaceId <= 0) {
      showToast("请选择或填写有效的工作空间 ID", "error");
      return;
    }

    setModelSaving(true);
    setModelSaved(false);
    try {
      await saveModelSettings(normalizedWorkspaceId, model);
      localStorage.setItem(MODEL_STORAGE_KEY, JSON.stringify(model));
      localStorage.setItem("docpilot_model_workspace_id", String(normalizedWorkspaceId));
      showToast("模型设置已保存");
      setModelSaved(true);
    } catch (err) { showToast(err.message, "error"); }
    finally { setModelSaving(false); }
  };

  // ---- Save retrieval ----
  const handleSaveRetrieval = async () => {
    setRetrievalSaving(true);
    setRetrievalSaved(false);
    try {
      await saveRetrievalSettings(workspaceId, retrieval);
      localStorage.setItem("docpilot_retrieval_settings", JSON.stringify(retrieval));
      showToast("检索设置已同步到当前工作空间");
      setRetrievalSaved(true);
    } catch (err) { showToast(err.message, "error"); }
    finally { setRetrievalSaving(false); }
  };

  // ---- Save report ----
  const handleSaveReport = async () => {
    setReportSaving(true);
    setReportSaved(false);
    try {
      await saveReportSettings(workspaceId, report);
      localStorage.setItem("docpilot_report_settings", JSON.stringify(report));
      showToast("报告设置已同步到当前工作空间");
      setReportSaved(true);
    } catch (err) { showToast(err.message, "error"); }
    finally { setReportSaving(false); }
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
    setProfileForm({ username: user?.username || "", email: user?.email || "" });
    setProfileErrors({});
    setIsEditingProfile(true);
  };

  const handleCancelProfileEdit = () => {
    setIsEditingProfile(false);
    setProfileErrors({});
  };

  const handleSaveProfile = async (event) => {
    event.preventDefault();
    const username = profileForm.username.trim();
    const nextEmail = profileForm.email.trim();
    const errors = {};

    if (username.length < 3 || username.length > 64) {
      errors.username = "用户名长度需为 3–64 个字符";
    }
    if (!/^\S+@\S+\.\S+$/.test(nextEmail)) {
      errors.email = "请输入有效的邮箱地址";
    }
    setProfileErrors(errors);
    if (Object.keys(errors).length) return;

    setProfileSaving(true);
    try {
      const updatedUser = await updateProfile(user?.id, { username, email: nextEmail });
      setUser(updatedUser);
      setIsEditingProfile(false);
      showToast("个人资料已更新");
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      setProfileSaving(false);
    }
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
    <div className="st-page">
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
                <div className="st-field"><span className="st-field__label">用户名</span><span className="st-field__value">{displayName}</span></div>
                <div className="st-field"><span className="st-field__label">邮箱</span><span className="st-field__value">{email}</span></div>
                <div className="st-field"><span className="st-field__label">角色</span><span className="st-field__value">{role}</span></div>
                <div className="st-field"><span className="st-field__label">加入时间</span><span className="st-field__value">{joinedAt}</span></div>
              </div>
              <button className="st-btn st-btn--outline" onClick={handleEditProfile}>
                <SvgIcon name="edit" size={15} />
                <span>编辑资料</span>
              </button>
            </div>

            {isEditingProfile && (
              <div
                className="st-profile-modal"
                role="presentation"
                onMouseDown={(event) => {
                  if (event.target === event.currentTarget && !profileSaving) handleCancelProfileEdit();
                }}
              >
                <div className="st-profile-modal__card" role="dialog" aria-modal="true" aria-labelledby="profile-modal-title">
                  <div className="st-profile-modal__header">
                    <div>
                      <h3 id="profile-modal-title">编辑个人资料</h3>
                      <p>更新后会同步到当前登录账号。</p>
                    </div>
                    <button className="st-profile-modal__close" type="button" aria-label="关闭" onClick={handleCancelProfileEdit} disabled={profileSaving}>×</button>
                  </div>
                  <form className="st-profile-edit" onSubmit={handleSaveProfile}>
                    <div className="st-form-group">
                      <label htmlFor="profile-username">用户名</label>
                      <input
                        id="profile-username"
                        className={`st-text-input${profileErrors.username ? " st-text-input--error" : ""}`}
                        value={profileForm.username}
                        onChange={(e) => setProfileForm({ ...profileForm, username: e.target.value })}
                        minLength={3}
                        maxLength={64}
                        autoComplete="username"
                        disabled={profileSaving}
                      />
                      {profileErrors.username && <p className="st-field-error">{profileErrors.username}</p>}
                    </div>
                    <div className="st-form-group">
                      <label htmlFor="profile-email">邮箱</label>
                      <input
                        id="profile-email"
                        className={`st-text-input${profileErrors.email ? " st-text-input--error" : ""}`}
                        type="email"
                        value={profileForm.email}
                        onChange={(e) => setProfileForm({ ...profileForm, email: e.target.value })}
                        autoComplete="email"
                        disabled={profileSaving}
                      />
                      {profileErrors.email && <p className="st-field-error">{profileErrors.email}</p>}
                    </div>
                    <div className="st-card-actions">
                      <button className="st-btn st-btn--outline" type="button" onClick={handleCancelProfileEdit} disabled={profileSaving}>取消</button>
                      <button className="st-btn st-btn--primary" type="submit" disabled={profileSaving}>
                        {profileSaving ? "保存中..." : "保存资料"}
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            )}          </div>

          {/* ===== 2. Model settings ===== */}
          <div className="st-card">
            <h2 className="st-card__title">模型设置</h2>
            <div className="st-form-grid">
              <div className="st-form-group">
                <label htmlFor="model-workspace">工作空间</label>
                {workspaces.length > 0 ? (
                  <select
                    id="model-workspace"
                    value={workspaceId}
                    onChange={(e) => {
                      setWorkspaceId(e.target.value);
                      setModelSaved(false);
                    }}
                    disabled={workspaceLoading || modelSaving}
                  >
                    {workspaces.map((workspace) => (
                      <option key={workspace.id} value={workspace.id}>{workspace.label}</option>
                    ))}
                  </select>
                ) : (
                  <input
                    id="model-workspace"
                    className="st-text-input"
                    type="number"
                    min="1"
                    step="1"
                    inputMode="numeric"
                    placeholder={workspaceLoading ? "正在识别工作空间..." : "请输入工作空间 ID"}
                    value={workspaceId}
                    onChange={(e) => {
                      setWorkspaceId(e.target.value);
                      setModelSaved(false);
                    }}
                    disabled={workspaceLoading || modelSaving}
                  />
                )}
                {!workspaceLoading && workspaces.length === 0 && (
                  <p className={`st-control-hint${workspaceLoadError ? " st-control-hint--error" : ""}`}>
                    {workspaceLoadError || "当前没有可自动识别的工作空间，请填写工作空间 ID。"}
                  </p>
                )}
              </div>
              <div className="st-form-group">
                <label htmlFor="model-key">默认模型</label>
                <select
                  id="model-key"
                  value={model.modelKey}
                  onChange={(e) => {
                    setModel({ ...model, modelKey: e.target.value });
                    setModelSaved(false);
                  }}
                  disabled={modelSaving}
                >
                  {MODEL_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </div>
              <div className="st-form-group">
                <label>Temperature <span className="st-val">{model.temperature}</span></label>
                <input type="range" min="0" max="2" step="0.1" value={model.temperature}
                  onChange={(e) => {
                    setModel({ ...model, temperature: parseFloat(e.target.value) });
                    setModelSaved(false);
                  }}
                  disabled={modelSaving} />
                <div className="st-slider-labels"><span>0</span><span>0.5</span><span>1</span><span>1.5</span><span>2</span></div>
              </div>
              <div className="st-form-group">
                <label htmlFor="model-max-tokens">Max Tokens</label>
                <select id="model-max-tokens" value={model.maxTokens} onChange={(e) => {
                  setModel({ ...model, maxTokens: parseInt(e.target.value, 10) });
                  setModelSaved(false);
                }} disabled={modelSaving}>
                  <option value={1024}>1024</option>
                  <option value={2048}>2048</option>
                  <option value={4096}>4096</option>
                  <option value={8192}>8192</option>
                  <option value={16384}>16384</option>
                </select>
              </div>
              <div className="st-form-group">
                <label htmlFor="model-language">回复语言</label>
                <select id="model-language" value={model.responseLanguage} onChange={(e) => {
                  setModel({ ...model, responseLanguage: e.target.value });
                  setModelSaved(false);
                }} disabled={modelSaving}>
                  {LANGUAGE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="st-card-actions">
              <button className="st-btn st-btn--primary" disabled={modelSaving || workspaceLoading || !workspaceId} onClick={handleSaveModel}>
                {modelSaving ? "保存中..." : "保存设置"}
              </button>
              {modelSaved && <span className="st-hint">已同步到当前工作空间</span>}
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
              <button className="st-btn st-btn--primary" disabled={retrievalSaving || workspaceLoading || !workspaceId} onClick={handleSaveRetrieval}>
                {retrievalSaving ? "保存中..." : "保存设置"}
              </button>
              {retrievalSaved && <span className="st-hint">已同步到当前工作空间</span>}
            </div>
          </div>

          {/* ===== 4. Report settings ===== */}
          <div className="st-card">
            <h2 className="st-card__title">报告设置</h2>
            <div className="st-form-grid">
              <div className="st-form-group">
                <label>默认报告类型</label>
                <select value={report.defaultReportType} onChange={(e) => setReport({ ...report, defaultReportType: e.target.value })}>
                  <option value="general">综合报告</option><option value="academic_review">学术综述</option><option value="project_analysis">项目分析</option><option value="contract_analysis">合同分析</option><option value="custom">自定义</option>
                </select>
              </div>
              <div className="st-form-group">
                <label>默认长度</label>
                <select value={report.defaultLength} onChange={(e) => setReport({ ...report, defaultLength: e.target.value })}>
                  <option value="short">简短（约800字）</option><option value="medium">中等（约1500字）</option><option value="long">详细（约3000字）</option>
                </select>
              </div>
              <div className="st-form-group">
                <label>引用格式</label>
                <select value={report.citationStyle} onChange={(e) => setReport({ ...report, citationStyle: e.target.value })}>
                  <option value="apa">APA</option><option value="mla">MLA</option><option value="chicago">Chicago</option><option value="gb_t_7714">GB/T 7714</option>
                </select>
              </div>
              <div className="st-form-group">
                <label>导出格式</label>
                <select value={report.exportFormat} onChange={(e) => setReport({ ...report, exportFormat: e.target.value })}>
                  <option value="pdf">PDF</option><option value="docx">DOCX</option><option value="markdown">Markdown</option><option value="html">HTML</option>
                </select>
              </div>
            </div>
            <div className="st-card-actions">
              <button className="st-btn st-btn--primary" disabled={reportSaving || workspaceLoading || !workspaceId} onClick={handleSaveReport}>
                {reportSaving ? "保存中..." : "保存设置"}
              </button>
              {reportSaved && <span className="st-hint">已同步到当前工作空间</span>}
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
