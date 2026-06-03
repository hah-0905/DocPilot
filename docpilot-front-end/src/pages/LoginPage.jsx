import { useState } from "react";
import { loginUser } from "../api/auth";
import AuthShell from "../components/AuthShell";
import FormField from "../components/FormField";
import SocialButton from "../components/SocialButton";

const loginFeatures = [
  {
    title: "多知识库管理",
    description: "集中管理各类文档与知识库，灵活连接，随需使用。",
    icon: "layers",
    tone: "blue"
  },
  {
    title: "可溯源问答",
    description: "基于知识库智能问答，答案可溯源，准确可靠。",
    icon: "chat",
    tone: "blue"
  },
  {
    title: "报告生成",
    description: "一键生成结构化报告，支持自定义模板与导出。",
    icon: "document",
    tone: "blue"
  }
];

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function LoginPage({ onNavigate, onAuthSuccess }) {
  const [form, setForm] = useState({
    account: "",
    password: "",
    remember: true
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
    const account = form.account.trim();

    if (!account) {
      nextErrors.account = "请输入邮箱或用户名";
    } else if (account.includes("@") && !emailPattern.test(account)) {
      nextErrors.account = "请输入有效的邮箱地址";
    } else if (!account.includes("@") && account.length < 3) {
      nextErrors.account = "用户名至少 3 位";
    }

    if (!form.password) {
      nextErrors.password = "请输入密码";
    } else if (form.password.length < 6) {
      nextErrors.password = "密码至少 6 位";
    }

    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }

  async function handleSubmit(event) {
    event.preventDefault();

    if (!validate()) {
      return;
    }

    const account = form.account.trim();
    const payload = account.includes("@")
      ? { email: account, password: form.password }
      : { username: account, password: form.password };

    try {
      setLoading(true);
      setApiError("");
      const data = await loginUser(payload);
      onAuthSuccess(data, { remember: form.remember });
    } catch (error) {
      setApiError(error.message || "登录失败，请稍后重试");
    } finally {
      setLoading(false);
    }
  }

  function handleUnsupportedAuth() {
    setApiError("当前后端暂未配置第三方登录接口");
  }

  return (
    <AuthShell
      variant="login"
      title="多知识库智能问答与报告生成平台"
      subtitle="连接您的知识，提升团队效率，让知识驱动决策。"
      features={loginFeatures}
    >
      <div className="form-heading">
        <h2>欢迎登录</h2>
        <p>登录后开始使用 DocPilot</p>
      </div>

      <form className="auth-form" noValidate onSubmit={handleSubmit}>
        {apiError ? <div className="form-alert">{apiError}</div> : null}

        <FormField
          label="邮箱 / 用户名"
          name="account"
          icon="mail"
          value={form.account}
          placeholder="请输入邮箱或用户名"
          autoComplete="username"
          error={errors.account}
          onChange={updateField}
        />

        <FormField
          label="密码"
          name="password"
          icon="lock"
          type="password"
          value={form.password}
          placeholder="请输入密码"
          autoComplete="current-password"
          error={errors.password}
          revealable
          onChange={updateField}
        />

        <div className="form-row form-row--split">
          <label className="checkbox-control">
            <input name="remember" type="checkbox" checked={form.remember} onChange={updateField} />
            <span>记住我</span>
          </label>
          <button className="text-link" type="button" onClick={() => setApiError("当前后端暂未提供找回密码接口")}>
            忘记密码?
          </button>
        </div>

        <button className="auth-button auth-button--primary" type="submit" disabled={loading}>
          {loading ? <span className="button-spinner" /> : null}
          <span>{loading ? "登录中..." : "登录"}</span>
        </button>

        <button className="auth-button auth-button--secondary" type="button" onClick={() => onNavigate("/register")}>
          注册账号
        </button>

        <div className="auth-divider">
          <span>或使用以下方式登录</span>
        </div>

        <div className="social-grid">
          <SocialButton provider="GitHub" onClick={handleUnsupportedAuth} />
          <SocialButton provider="Google" onClick={handleUnsupportedAuth} />
        </div>

        <p className="auth-switch">
          还没有账号？
          <button type="button" onClick={() => onNavigate("/register")}>
            立即注册
          </button>
        </p>
      </form>
    </AuthShell>
  );
}
