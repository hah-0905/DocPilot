-- MySQL 8.0; repeatable, additive upgrade. No existing credentials/data are changed.
CREATE TABLE IF NOT EXISTS user_model_configs (
    user_id BIGINT UNSIGNED NOT NULL,
    provider_id VARCHAR(32) NOT NULL,
    model_name VARCHAR(128) NOT NULL,
    encrypted_credential TEXT NOT NULL,
    credential_last_four VARCHAR(4) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id),
    CONSTRAINT fk_user_model_configs_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- The application supplies MODEL_NAME on first creation. Remove stale DeepSeek default.
ALTER TABLE workspace_model_settings ALTER COLUMN model_key DROP DEFAULT;
