export default function Logo({ compact = false }) {
  return (
    <div className={`brand-logo${compact ? " brand-logo--compact" : ""}`} aria-label="DocPilot">
      <span className="brand-logo__mark" aria-hidden="true">
        <span />
      </span>
      <span className="brand-logo__text">DocPilot</span>
    </div>
  );
}
