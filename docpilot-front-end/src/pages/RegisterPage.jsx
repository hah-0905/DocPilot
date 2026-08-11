import { useState } from "react";
import { registerUser } from "../api/auth";
import AuthShell from "../components/AuthShell";
import FormField from "../components/FormField";
import SocialButton from "../components/SocialButton";

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
    <AuthShell variant="register" title="创建你的 DocPilot 工作区" subtitle="一个账号，连接你的文档与知识库">
      <div className="form-heading">
        <h2>创建账号</h2>
        <p>开始使用 DocPilot</p>
      </div>

      <form className="auth-form auth-form--register" noValidate onSubmit={handleSubmit}>
        {apiError ? <div className="form-alert">{apiError}</div> : null}

        <FormField label="用户名" name="username" icon="user" value={form.username} placeholder="3-20 位字符" autoComplete="username" error={errors.username} onChange={updateField} />
        <FormField label="邮箱" name="email" icon="mail" value={form.email} placeholder="name@example.com" autoComplete="email" inputMode="email" error={errors.email} onChange={updateField} />
        <FormField label="密码" name="password" icon="lock" type="password" value={form.password} placeholder="8-20 位，包含大小写、数字和特殊字符" autoComplete="new-password" error={errors.password} revealable onChange={updateField} />
        <FormField label="确认密码" name="confirmPassword" icon="lock" type="password" value={form.confirmPassword} placeholder="再次输入密码" autoComplete="new-password" error={errors.confirmPassword} revealable onChange={updateField} />

        <label className={`checkbox-control auth-agreement${errors.agree ? " auth-agreement--error" : ""}`}>
          <input name="agree" type="checkbox" checked={form.agree} onChange={updateField} />
          <span>我已阅读并同意《用户协议》和《隐私政策》</span>
        </label>
        {errors.agree ? <p className="field-error">{errors.agree}</p> : null}

        <button className="auth-button auth-button--primary" type="submit" disabled={loading}>
          {loading ? <span className="button-spinner" /> : null}<span>{loading ? "注册中..." : "创建账号"}</span>
        </button>

        <div className="auth-divider"><span>或使用</span></div>
        <div className="social-grid">
          <SocialButton provider="GitHub" onClick={handleUnsupportedAuth} />
          <SocialButton provider="Google" onClick={handleUnsupportedAuth} />
        </div>
        <p className="auth-switch">已有账号？<button type="button" onClick={() => onNavigate("/login")}>登录</button></p>
      </form>
    </AuthShell>
  );
}
