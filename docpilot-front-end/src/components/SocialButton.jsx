import Icon from "./Icon";

export default function SocialButton({ provider, onClick }) {
  const isGithub = provider === "GitHub";

  return (
    <button className="social-button" type="button" onClick={onClick}>
      <Icon name={isGithub ? "github" : "google"} className="social-icon" />
      <span>{provider}</span>
    </button>
  );
}
