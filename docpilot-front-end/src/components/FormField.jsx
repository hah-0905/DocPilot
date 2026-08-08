import { useState } from "react";
import Icon from "./Icon";

export default function FormField({
  label,
  name,
  icon,
  type = "text",
  value,
  placeholder,
  autoComplete,
  inputMode,
  error,
  hint,
  revealable = false,
  onChange,
  onBlur
}) {
  const [visible, setVisible] = useState(false);
  const inputType = revealable && visible ? "text" : type;

  return (
    <div className="form-field">
      {label ? (
        <label className="form-label" htmlFor={name}>
          {label}
        </label>
      ) : null}
      <div className={`input-shell${error ? " input-shell--error" : ""}`}>
        {icon ? <Icon name={icon} className="input-icon" /> : null}
        <input
          id={name}
          name={name}
          type={inputType}
          value={value}
          placeholder={placeholder}
          autoComplete={autoComplete}
          inputMode={inputMode}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? `${name}-error` : hint ? `${name}-hint` : undefined}
          onChange={onChange}
          onBlur={onBlur}
        />
        {revealable ? (
          <button
            className="input-eye"
            type="button"
            aria-label={visible ? "隐藏密码" : "显示密码"}
            onClick={() => setVisible((current) => !current)}
          >
            <Icon name={visible ? "eye-off" : "eye"} />
          </button>
        ) : null}
      </div>
      {error ? (
        <p className="field-error" id={`${name}-error`}>
          {error}
        </p>
      ) : hint ? (
        <p className="field-hint" id={`${name}-hint`}>
          {hint}
        </p>
      ) : null}
    </div>
  );
}
