import Logo from "./Logo";

export default function AuthShell({
  variant = "login",
  title,
  subtitle,
  children,
  topAction
}) {
  return (
    <main className={`auth-page auth-page--${variant}`}>
      <div className="auth-workspace">
        <Logo compact />
        <div className="auth-workspace__intro">
          <h1>{title}</h1>
          <p>{subtitle}</p>
        </div>
        <section className="auth-main">
          <div className={`auth-card auth-card--${variant}`}>{children}</div>
        </section>
        {topAction ? <div className="auth-top-action">{topAction}</div> : null}
      </div>
    </main>
  );
}
