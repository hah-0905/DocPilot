import { useState } from "react";
import { registerUser } from "../api/auth";
import FormField from "../components/FormField";
import SocialButton from "../components/SocialButton";

const registerFeatures = [
  {
    title: "多知识库管理",
    description: "支持创建和管理多个知识库，轻松切换，让知识组织更高效",
    icon: "layers",
    tone: "blue"
  },
  {
    title: "智能问答",
    description: "基于检索增强生成（RAG）技术，提供准确、可靠的问答服务",
    icon: "chat",
    tone: "green"
  },
  {
    title: "可溯源引用",
    description: "所有回答提供来源引用，确保信息可追溯、可信赖",
    icon: "document",
    tone: "purple"
  },
  {
    title: "报告自动生成",
    description: "基于问答内容，自动生成结构化报告，支持多种格式导出",
    icon: "document",
    tone: "orange"
  }
];

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const usernamePattern = /^[一-龥A-Za-z0-9_]{3,20}$/;
const passwordPattern = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,20}$/;

export default function RegisterPage({ onNavigate, onAuthSuccess }) {
  const [form, setForm] = useState({
    username: "",
    email: "",
    password: "",
    confirmPassword: "",
    agree: false
  });
  const [errors, setErrors] = useState({});
  const [apiError, setApiError] = useState("");
  const [loading, setLoading] = useState(false);

  function updateField(event) {
    const { name, value, checked, type } = event.target;
    setForm((current) => ({
      ...current,
      [name]: type === "checkbox" ? checked : value
    }));
    setErrors((current) => ({ ...current, [name]: "" }));
    setApiError("");
  }

  function validate() {
    const nextErrors = {};

    if (!usernamePattern.test(form.username.trim())) {
      nextErrors.username = "用户名需为 3-20 位中文、字母、数字或下划线";
    }

    if (!emailPattern.test(form.email.trim())) {
      nextErrors.email = "请输入有效的邮箱地址";
    }

    if (!passwordPattern.test(form.password)) {
      nextErrors.password = "密码需 8-20 位，包含大小写字母、数字和特殊字符";
    }

    if (!form.confirmPassword) {
      nextErrors.confirmPassword = "请再次输入密码";
    } else if (form.confirmPassword !== form.password) {
      nextErrors.confirmPassword = "两次输入的密码不一致";
    }

    if (!form.agree) {
      nextErrors.agree = "请先阅读并同意用户协议和隐私政策";
    }

    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }

  async function handleSubmit(event) {
    event.preventDefault();

    if (!validate()) {
      return;
    }

    try {
      setLoading(true);
      setApiError("");
      const data = await registerUser({
        username: form.username.trim(),
        email: form.email.trim(),
        password: form.password
      });
      onAuthSuccess(data, { remember: true });
    } catch (error) {
      setApiError(error.message || "注册失败，请稍后重试");
    } finally {
      setLoading(false);
    }
  }

  function handleUnsupportedAuth() {
    setApiError("当前后端暂未配置第三方注册接口");
  }

  return (
    <main className="register-page">
      {/* ===== 左侧品牌区 ===== */}
      <section className="register-sidebar" aria-label="DocPilot 产品介绍">
        <div className="register-brand">
          <span className="register-brand__mark" aria-hidden="true">
            <span />
          </span>
          <span className="register-brand__text">DocPilot</span>
        </div>

        <div className="register-sidebar__copy">
          <h1 className="register-sidebar__title">
            欢迎加入 <span>DocPilot</span>
          </h1>
          <p className="register-sidebar__subtitle">多知识库智能问答与报告生成平台</p>
        </div>

        <div className="register-features">
          {registerFeatures.map((feature) => (
            <article className="register-feature-item" key={feature.title}>
              <span className={`register-feature-icon register-feature-icon--${feature.tone}`}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  {feature.icon === "layers" ? (
                    <>
                      <path d="m12 3 9 5-9 5-9-5 9-5Z" />
                      <path d="m4 12 8 4.5 8-4.5" />
                      <path d="m4 16 8 4.5 8-4.5" />
                    </>
                  ) : feature.icon === "chat" ? (
                    <>
                      <path d="M4 6.5A4.5 4.5 0 0 1 8.5 2h7A4.5 4.5 0 0 1 20 6.5v4A4.5 4.5 0 0 1 15.5 15H12l-4.5 4v-4A4.5 4.5 0 0 1 4 10.5v-4Z" />
                      <path d="M8 8.5h.01M12 8.5h.01M16 8.5h.01" />
                    </>
                  ) : (
                    <>
                      <path d="M7 3h7l4 4v14H7V3Z" />
                      <path d="M14 3v5h5" />
                      <path d="M10 12h5M10 16h6" />
                    </>
                  )}
                </svg>
              </span>
              <span className="register-feature-text">
                <strong>{feature.title}</strong>
                <small>{feature.description}</small>
              </span>
            </article>
          ))}
        </div>

        <div className="register-illustration" aria-hidden="true">
          <div className="ri-plate" />
          <div className="ri-card ri-card--doc">
            <span className="ri-line ri-line--wide" />
            <span className="ri-line" />
            <span className="ri-line ri-line--short" />
            <span className="ri-bars">
              <i /><i /><i />
            </span>
          </div>
          <div className="ri-card ri-card--chat">
            <span /><span /><span />
          </div>
          <div className="ri-ring" />
          <div className="ri-chart">
            <span className="ri-chart-dot" />
            <span className="ri-chart-bar" style={{ height: "48%" }} />
            <span className="ri-chart-bar" style={{ height: "72%" }} />
            <span className="ri-chart-bar" style={{ height: "36%" }} />
          </div>
          <div className="ri-donut" />
          <div className="ri-bubble ri-bubble--1">
            <span className="ri-bline" />
            <span className="ri-bline ri-bline--short" />
          </div>
          <div className="ri-bubble ri-bubble--2">
            <span className="ri-bline" />
            <span className="ri-bline ri-bline--short" />
          </div>
        </div>
      </section>

      {/* ===== 右侧表单区 ===== */}
      <section className="register-main">
        <div className="register-top-action">
          <span>已有账号？</span>
          <button type="button" onClick={() => onNavigate("/login")}>立即登录</button>
        </div>

        <div className="register-card">
          <div className="register-card__header">
            <h2>创建账号</h2>
            <p>开始使用 DocPilot，让知识驱动你的效率</p>
          </div>

          <form className="register-form" noValidate onSubmit={handleSubmit}>
            {apiError ? <div className="register-alert">{apiError}</div> : null}

            <FormField
              name="username"
              icon="user"
              value={form.username}
              placeholder="用户名"
              autoComplete="username"
              error={errors.username}
              hint="3-20位字符，支持中文、字母、数字和下划线"
              onChange={updateField}
            />

            <FormField
              name="email"
              icon="mail"
              value={form.email}
              placeholder="邮箱地址"
              autoComplete="email"
              inputMode="email"
              error={errors.email}
              hint="请输入有效的邮箱地址，用于接收验证邮件"
              onChange={updateField}
            />

            <FormField
              name="password"
              icon="lock"
              type="password"
              value={form.password}
              placeholder="密码"
              autoComplete="new-password"
              error={errors.password}
              hint="8-20位字符，包含大小写字母、数字和特殊字符"
              revealable
              onChange={updateField}
            />

            <FormField
              name="confirmPassword"
              icon="lock"
              type="password"
              value={form.confirmPassword}
              placeholder="确认密码"
              autoComplete="new-password"
              error={errors.confirmPassword}
              hint="请再次输入密码"
              revealable
              onChange={updateField}
            />

            <div className="register-form-row">
              <label className={`register-checkbox${errors.agree ? " register-checkbox--error" : ""}`}>
                <input name="agree" type="checkbox" checked={form.agree} onChange={updateField} />
                <span>
                  我已阅读并同意
                  <span className="register-link">《用户协议》</span>
                  和
                  <span className="register-link">《隐私政策》</span>
                </span>
              </label>
            </div>
            {errors.agree ? <p className="register-field-error register-field-error--standalone">{errors.agree}</p> : null}

            <button className="register-btn register-btn--primary" type="submit" disabled={loading}>
              {loading ? <span className="register-spinner" /> : null}
              <span>{loading ? "注册中..." : "注册"}</span>
            </button>

            <div className="register-divider">
              <span>或使用以下方式注册</span>
            </div>

            <div className="register-social">
              <SocialButton provider="GitHub" onClick={handleUnsupportedAuth} />
              <SocialButton provider="Google" onClick={handleUnsupportedAuth} />
            </div>
          </form>
        </div>
      </section>
    </main>
  );
}
