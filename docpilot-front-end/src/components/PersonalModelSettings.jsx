import { useEffect, useState } from "react";
import { getModelCatalog, getPersonalModel, savePersonalModel, testPersonalModel, deletePersonalModel } from "../api/settings";

export default function PersonalModelSettings() {
  const [catalog, setCatalog] = useState(null);
  const [status, setStatus] = useState(null);
  const [source, setSource] = useState("platform");
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const applyStatus = (next, directory) => {
    setStatus(next);
    setSource(next.enabled ? "personal" : "platform");
    const choice = directory.providers.find((p) => p.id === next.provider_id) || directory.providers[0];
    setProvider(choice?.id || "");
    setModel(choice?.models.includes(next.model_name) ? next.model_name : choice?.models[0] || "");
    setKey("");
  };

  useEffect(() => {
    let active = true;
    Promise.all([getModelCatalog(), getPersonalModel()]).then(([directory, next]) => {
      if (active) { setCatalog(directory); applyStatus(next, directory); }
    }).catch((err) => { if (active) setError(err.message); });
    return () => { active = false; };
  }, []);

  const models = catalog?.providers.find((p) => p.id === provider)?.models || [];
  const payload = () => ({ provider_id: provider, model_name: model, enabled: source === "personal", ...(key ? { api_key: key } : {}) });
  const act = async (action) => {
    setBusy(true); setError(""); setMessage("");
    try {
      if (action === "test") {
        const result = await testPersonalModel(payload());
        setMessage(result.message);
      } else if (action === "delete") {
        applyStatus(await deletePersonalModel(), catalog);
        setMessage("个人凭据已删除，已使用平台默认配置");
      } else if (source === "platform" && !status.configured) {
        setMessage("当前使用平台默认配置");
      } else {
        const data = source === "platform" ? { provider_id: status.provider_id, model_name: status.model_name, enabled: false } : payload();
        applyStatus(await savePersonalModel(data), catalog);
        setMessage("模型来源和个人配置已保存");
      }
    } catch (err) { setError(err.message); }
    finally { setKey(""); setBusy(false); }
  };

  return (
    <div className="st-card">
      <h2 className="st-card__title">个人模型配置</h2>
      <p className="st-control-hint">用于普通聊天、流式聊天和报告。文档 Embedding 使用平台配置。平台模式使用工作空间模型设置。</p>
      {error && <p role="alert" className="st-field-error">{error}</p>}
      {message && <p role="status" className="st-hint">{message}</p>}
      {!status && !error && <p>正在加载配置...</p>}
      {status && catalog && <>
        {!status.available && <p role="alert">{status.unavailable_reason}；平台功能仍可使用，已有凭据可删除。</p>}
        <fieldset disabled={busy} style={{ border: 0, padding: 0, margin: 0 }}>
          <div className="st-form-grid">
            <div className="st-form-group">
              <label htmlFor="personal-source">模型来源</label>
              <select id="personal-source" value={source} onChange={(e) => setSource(e.target.value)}>
                <option value="platform">平台默认</option>
                <option value="personal" disabled={!status.available}>个人配置</option>
              </select>
            </div>
            <div className="st-form-group">
              <label htmlFor="personal-provider">服务商</label>
              <select id="personal-provider" value={provider} disabled={source !== "personal" || !status.available} onChange={(e) => {
                setProvider(e.target.value);
                setModel(catalog.providers.find((p) => p.id === e.target.value)?.models[0] || "");
                setKey("");
              }}>
                {catalog.providers.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
              </select>
            </div>
            <div className="st-form-group">
              <label htmlFor="personal-model">个人模型</label>
              <select id="personal-model" value={model} disabled={source !== "personal" || !status.available} onChange={(e) => setModel(e.target.value)}>
                {models.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
            <div className="st-form-group">
              <label htmlFor="personal-api-key">API Key {status.key_mask ? `（已配置 ${status.key_mask}）` : "（未配置）"}</label>
              <input id="personal-api-key" className="st-text-input" type="password" autoComplete="new-password" spellCheck={false} maxLength={4096}
                disabled={source !== "personal" || !status.available} value={key} onChange={(e) => setKey(e.target.value)}
                placeholder={status.configured ? "留空保留原凭据；切换服务商需填写新 Key" : "填写自己的 API Key"} />
            </div>
          </div>
          <p className="st-control-hint">测试连接会发送极短请求，可能产生少量费用。测试不会保存配置。Key 仅在本次输入期间保留于页面内存。</p>
          <div className="st-card-actions">
            <button className="st-btn st-btn--outline" disabled={!status.available || source !== "personal"} onClick={() => act("test")}>测试连接</button>
            <button className="st-btn st-btn--primary" disabled={!status.available} onClick={() => act("save")}>{busy ? "处理中..." : "保存"}</button>
            <button className="st-btn st-btn--danger" disabled={!status.configured} onClick={() => act("delete")}>删除个人凭据</button>
          </div>
        </fieldset>
      </>}
    </div>
  );
}
