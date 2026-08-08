import Icon from "./Icon";
import Logo from "./Logo";

export default function AuthShell({
  variant = "login",
  title,
  titleHighlight,
  subtitle,
  features,
  children,
  topAction
}) {
  return (
    <main className={`auth-page auth-page--${variant}`}>
      <section className="auth-side" aria-label="DocPilot 产品介绍">
        <Logo compact={variant === "register"} />

        <div className="auth-side__copy">
          <h1 className="auth-side__title">
            {title}
            {titleHighlight ? <span>{titleHighlight}</span> : null}
          </h1>
          <p className="auth-side__subtitle">{subtitle}</p>
        </div>

        <div className="feature-list">
          {features.map((feature) => (
            <article className="feature-item" key={feature.title}>
              <span className={`feature-icon feature-icon--${feature.tone}`}>
                <Icon name={feature.icon} />
              </span>
              <span>
                <strong>{feature.title}</strong>
                <small>{feature.description}</small>
              </span>
            </article>
          ))}
        </div>

        <ProductIllustration variant={variant} />
      </section>

      <section className="auth-main">
        {topAction ? <div className="auth-top-action">{topAction}</div> : null}
        <div className={`auth-card auth-card--${variant}`}>{children}</div>
      </section>
    </main>
  );
}

function ProductIllustration({ variant }) {
  return (
    <div className={`product-illustration product-illustration--${variant}`} aria-hidden="true">
      <div className="product-plate" />
      <div className="product-card product-card--doc">
        <span className="doc-line doc-line--wide" />
        <span className="doc-line" />
        <span className="doc-line doc-line--short" />
        <span className="doc-bars">
          <i />
          <i />
          <i />
        </span>
      </div>
      <div className="product-card product-card--chat">
        <span />
        <span />
        <span />
      </div>
      <div className="product-ring" />

      {variant === "login" ? (
        <>
          <div className="product-chart-card">
            <span className="chart-dot" />
            <span className="chart-bar chart-bar--1" />
            <span className="chart-bar chart-bar--2" />
            <span className="chart-bar chart-bar--3" />
          </div>
          <div className="product-donut" />
          <div className="product-bubble product-bubble--1">
            <span className="bubble-line" />
            <span className="bubble-line bubble-line--short" />
          </div>
          <div className="product-bubble product-bubble--2">
            <span className="bubble-line" />
            <span className="bubble-line bubble-line--short" />
          </div>
          <span className="product-dot product-dot--1" />
          <span className="product-dot product-dot--2" />
          <span className="product-dot product-dot--3" />
        </>
      ) : null}

      {variant === "register" ? (
        <>
          <div className="product-window">
            <span className="window-dot" />
            <span className="window-dot" />
            <span className="window-dot" />
            <i className="window-message" />
            <i className="window-line window-line--a" />
            <i className="window-line window-line--b" />
            <i className="window-line window-line--c" />
          </div>
          <div className="product-chart-card">
            <span className="chart-dot" />
            <span className="chart-bar chart-bar--1" />
            <span className="chart-bar chart-bar--2" />
            <span className="chart-bar chart-bar--3" />
          </div>
          <div className="product-donut" />
          <div className="product-bubble product-bubble--1">
            <span className="bubble-line" />
            <span className="bubble-line bubble-line--short" />
          </div>
          <div className="product-bubble product-bubble--2">
            <span className="bubble-line" />
            <span className="bubble-line bubble-line--short" />
          </div>
          <span className="product-dot product-dot--1" />
          <span className="product-dot product-dot--2" />
          <span className="product-dot product-dot--3" />
          <span className="leaf leaf--left" />
          <span className="leaf leaf--right" />
        </>
      ) : null}
    </div>
  );
}
