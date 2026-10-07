-- DocPilot 数据库表结构（由 SQLAlchemy 模型生成，与 init_db.py 的 create_all 一致）
-- MySQL 8.0 / utf8mb4 / utf8mb4_unicode_ci
--
-- 用法：先建库，再执行本文件
--   CREATE DATABASE docpilot CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
--   mysql -u docpilot -p docpilot < schema.sql

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ======================================================================
-- users
-- ======================================================================
CREATE TABLE users (
	id BIGINT UNSIGNED NOT NULL COMMENT '用户ID' AUTO_INCREMENT, 
	username VARCHAR(64) NOT NULL COMMENT '用户名', 
	email VARCHAR(128) NOT NULL COMMENT '邮箱', 
	password_hash VARCHAR(255) NOT NULL COMMENT '密码哈希', 
	display_name VARCHAR(128) COMMENT '显示名称', 
	avatar_url VARCHAR(512) COMMENT '头像URL', 
	status VARCHAR(32) NOT NULL COMMENT '用户状态' DEFAULT 'active', 
	last_login_at DATETIME(3) COMMENT '最后登录时间', 
	created_at DATETIME(3) NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(3), 
	updated_at DATETIME(3) NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3), 
	deleted_at DATETIME(3) COMMENT '软删除时间', 
	PRIMARY KEY (id), 
	CONSTRAINT uk_users_email UNIQUE (email), 
	CONSTRAINT uk_users_username UNIQUE (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ======================================================================
-- auth_action_tokens
-- ======================================================================
CREATE TABLE auth_action_tokens (
	id BIGINT UNSIGNED NOT NULL COMMENT '操作Token ID' AUTO_INCREMENT, 
	user_id BIGINT UNSIGNED NOT NULL COMMENT '用户ID', 
	token_hash CHAR(64) NOT NULL COMMENT 'Token哈希值，建议存sha256结果', 
	action_type VARCHAR(64) NOT NULL COMMENT '操作类型：email_verify / password_reset / change_email', 
	target VARCHAR(255) COMMENT '目标值，例如待验证的新邮箱', 
	expires_at DATETIME(3) NOT NULL COMMENT '过期时间', 
	used_at DATETIME(3) COMMENT '使用时间', 
	created_at DATETIME(3) NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(3), 
	PRIMARY KEY (id), 
	CONSTRAINT uk_auth_action_tokens_hash UNIQUE (token_hash), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX idx_auth_action_tokens_action ON auth_action_tokens (action_type);
CREATE INDEX idx_auth_action_tokens_expires_at ON auth_action_tokens (expires_at);
CREATE INDEX idx_auth_action_tokens_used_at ON auth_action_tokens (used_at);
CREATE INDEX idx_auth_action_tokens_user ON auth_action_tokens (user_id);

-- ======================================================================
-- workspaces
-- ======================================================================
CREATE TABLE workspaces (
	id BIGINT UNSIGNED NOT NULL COMMENT '工作空间ID' AUTO_INCREMENT, 
	name VARCHAR(128) NOT NULL COMMENT '工作空间名称', 
	description VARCHAR(512) COMMENT '工作空间描述', 
	owner_user_id BIGINT UNSIGNED NOT NULL COMMENT '工作空间所有者用户ID', 
	status VARCHAR(32) NOT NULL COMMENT '状态：active/disabled/deleted 等' DEFAULT 'active', 
	created_at DATETIME(3) NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(3), 
	updated_at DATETIME(3) NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(3), 
	deleted_at DATETIME(3) COMMENT '软删除时间', 
	PRIMARY KEY (id), 
	CONSTRAINT fk_workspaces_owner FOREIGN KEY(owner_user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX idx_workspaces_owner ON workspaces (owner_user_id);
CREATE INDEX idx_workspaces_status ON workspaces (status);

-- ======================================================================
-- chat_sessions
-- ======================================================================
CREATE TABLE chat_sessions (
	id BIGINT UNSIGNED NOT NULL COMMENT '聊天会话ID' AUTO_INCREMENT, 
	workspace_id BIGINT UNSIGNED NOT NULL COMMENT '工作空间ID', 
	user_id BIGINT UNSIGNED NOT NULL COMMENT '用户ID', 
	title VARCHAR(255) COMMENT '会话标题', 
	status VARCHAR(32) NOT NULL COMMENT '状态：active/deleted 等' DEFAULT 'active', 
	created_at DATETIME(3) NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(3), 
	PRIMARY KEY (id), 
	CONSTRAINT fk_chat_sessions_workspace FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE, 
	CONSTRAINT fk_chat_sessions_user FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX idx_chat_sessions_status ON chat_sessions (status);
CREATE INDEX idx_chat_sessions_user ON chat_sessions (user_id, created_at);
CREATE INDEX idx_chat_sessions_workspace ON chat_sessions (workspace_id, created_at);

-- ======================================================================
-- knowledge_bases
-- ======================================================================
CREATE TABLE knowledge_bases (
	id BIGINT UNSIGNED NOT NULL COMMENT '知识库ID' AUTO_INCREMENT, 
	workspace_id BIGINT UNSIGNED NOT NULL COMMENT '工作空间ID', 
	name VARCHAR(128) NOT NULL COMMENT '知识库名称', 
	description TEXT COMMENT '知识库描述', 
	visibility VARCHAR(32) NOT NULL COMMENT '可见性：private/public 等' DEFAULT 'private', 
	embedding_model VARCHAR(128) COMMENT '向量嵌入模型', 
	rerank_model VARCHAR(128) COMMENT '重排序模型', 
	chunk_strategy VARCHAR(64) NOT NULL COMMENT '分块策略' DEFAULT 'recursive', 
	chunk_size INTEGER NOT NULL COMMENT '分块大小' DEFAULT 800, 
	chunk_overlap INTEGER NOT NULL COMMENT '分块重叠大小' DEFAULT 100, 
	default_top_k INTEGER NOT NULL COMMENT '默认召回数量' DEFAULT 5, 
	status VARCHAR(32) NOT NULL COMMENT '状态：active/disabled/deleted 等' DEFAULT 'active', 
	created_by BIGINT UNSIGNED NOT NULL COMMENT '创建者用户ID', 
	created_at DATETIME(3) NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(3), 
	updated_at DATETIME(3) NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(3), 
	deleted_at DATETIME(3) COMMENT '软删除时间', 
	PRIMARY KEY (id), 
	CONSTRAINT uk_workspace_kb_name UNIQUE (workspace_id, name), 
	CONSTRAINT fk_kb_workspace FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE, 
	CONSTRAINT fk_kb_created_by FOREIGN KEY(created_by) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX idx_kb_created_by ON knowledge_bases (created_by);
CREATE INDEX idx_kb_workspace_status ON knowledge_bases (workspace_id, status);

-- ======================================================================
-- report_tasks
-- ======================================================================
CREATE TABLE report_tasks (
	id BIGINT UNSIGNED NOT NULL COMMENT 'Report task ID' AUTO_INCREMENT, 
	workspace_id BIGINT UNSIGNED NOT NULL COMMENT 'Workspace ID', 
	user_id BIGINT UNSIGNED NOT NULL COMMENT 'User ID', 
	title VARCHAR(255) NOT NULL COMMENT 'Report title', 
	report_type VARCHAR(64) NOT NULL COMMENT 'Report type' DEFAULT 'general', 
	instruction LONGTEXT COMMENT 'Report generation instruction', 
	status VARCHAR(32) NOT NULL COMMENT 'Task status' DEFAULT 'pending', 
	model_name VARCHAR(128) COMMENT 'LLM model name', 
	config JSON COMMENT 'Task config', 
	result_content LONGTEXT COMMENT 'Generated report content', 
	error_message TEXT COMMENT 'Error message', 
	started_at DATETIME(3) COMMENT 'Started at', 
	finished_at DATETIME(3) COMMENT 'Finished at', 
	created_at DATETIME(3) NOT NULL COMMENT 'Created at' DEFAULT CURRENT_TIMESTAMP(3), 
	updated_at DATETIME(3) NOT NULL COMMENT 'Updated at' DEFAULT CURRENT_TIMESTAMP(3), 
	PRIMARY KEY (id), 
	CONSTRAINT fk_report_tasks_workspace FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE, 
	CONSTRAINT fk_report_tasks_user FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX idx_report_tasks_status ON report_tasks (status);
CREATE INDEX idx_report_tasks_user ON report_tasks (user_id, created_at);
CREATE INDEX idx_report_tasks_workspace ON report_tasks (workspace_id, created_at);

-- ======================================================================
-- workspace_members
-- ======================================================================
CREATE TABLE workspace_members (
	id BIGINT UNSIGNED NOT NULL COMMENT '工作空间成员ID' AUTO_INCREMENT, 
	workspace_id BIGINT UNSIGNED NOT NULL COMMENT '工作空间ID', 
	user_id BIGINT UNSIGNED NOT NULL COMMENT '用户ID', 
	`role` VARCHAR(32) NOT NULL COMMENT '成员角色：owner/admin/member 等' DEFAULT 'member', 
	joined_at DATETIME(3) NOT NULL COMMENT '加入时间' DEFAULT CURRENT_TIMESTAMP(3), 
	PRIMARY KEY (id), 
	CONSTRAINT uk_workspace_user UNIQUE (workspace_id, user_id), 
	CONSTRAINT fk_workspace_members_workspace FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE, 
	CONSTRAINT fk_workspace_members_user FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX idx_workspace_members_role ON workspace_members (workspace_id, `role`);
CREATE INDEX idx_workspace_members_user ON workspace_members (user_id);

-- ======================================================================
-- workspace_model_settings
-- ======================================================================
CREATE TABLE workspace_model_settings (
	id BIGINT UNSIGNED NOT NULL COMMENT '模型设置 ID' AUTO_INCREMENT, 
	workspace_id BIGINT UNSIGNED NOT NULL COMMENT '工作空间 ID；每个工作空间仅一条设置', 
	model_key VARCHAR(128) NOT NULL COMMENT '模型内部标识，例如 deepseek-chat 或 gpt-4o-mini' DEFAULT 'deepseek-chat', 
	temperature DOUBLE NOT NULL COMMENT '采样温度，通常范围为 0 到 2' DEFAULT (0.7), 
	max_tokens INTEGER UNSIGNED NOT NULL COMMENT '单次回答的最大生成 Token 数' DEFAULT 4096, 
	response_language VARCHAR(32) NOT NULL COMMENT '默认回复语言' DEFAULT 'zh-CN', 
	created_at DATETIME(3) NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(3), 
	updated_at DATETIME(3) NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3), 
	PRIMARY KEY (id), 
	CONSTRAINT uk_workspace_model_settings_workspace UNIQUE (workspace_id), 
	CONSTRAINT fk_workspace_model_settings_workspace FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ======================================================================
-- workspace_report_settings
-- ======================================================================
CREATE TABLE workspace_report_settings (
	id BIGINT UNSIGNED NOT NULL COMMENT '报告设置 ID' AUTO_INCREMENT, 
	workspace_id BIGINT UNSIGNED NOT NULL COMMENT '工作空间 ID；每个工作空间仅一条设置', 
	report_type VARCHAR(64) NOT NULL COMMENT '默认报告类型' DEFAULT 'general', 
	length VARCHAR(32) NOT NULL COMMENT '默认报告长度：short/medium/long' DEFAULT 'medium', 
	citation_style VARCHAR(32) NOT NULL COMMENT '默认引用格式' DEFAULT 'apa', 
	export_format VARCHAR(32) NOT NULL COMMENT '默认导出格式' DEFAULT 'markdown', 
	created_at DATETIME(3) NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(3), 
	updated_at DATETIME(3) NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3), 
	PRIMARY KEY (id), 
	CONSTRAINT uk_workspace_report_settings_workspace UNIQUE (workspace_id), 
	CONSTRAINT ck_workspace_report_settings_report_type CHECK (report_type IN ('general', 'academic_review', 'project_analysis', 'contract_analysis', 'custom')), 
	CONSTRAINT ck_workspace_report_settings_length CHECK (length IN ('short', 'medium', 'long')), 
	CONSTRAINT ck_workspace_report_settings_citation_style CHECK (citation_style IN ('apa', 'mla', 'chicago', 'gb_t_7714')), 
	CONSTRAINT ck_workspace_report_settings_export_format CHECK (export_format IN ('pdf', 'docx', 'markdown', 'html')), 
	CONSTRAINT fk_workspace_report_settings_workspace FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ======================================================================
-- workspace_retrieval_settings
-- ======================================================================
CREATE TABLE workspace_retrieval_settings (
	id BIGINT UNSIGNED NOT NULL COMMENT '检索设置 ID' AUTO_INCREMENT, 
	workspace_id BIGINT UNSIGNED NOT NULL COMMENT '工作空间 ID；每个工作空间仅一条设置', 
	top_k INTEGER UNSIGNED NOT NULL COMMENT '每次检索返回的候选文档数量' DEFAULT 10, 
	similarity_threshold DOUBLE NOT NULL COMMENT '相似度过滤阈值，范围为 0 到 1' DEFAULT (0.65), 
	enable_rerank TINYINT(1) NOT NULL COMMENT '是否启用重排序' DEFAULT 1, 
	show_sources TINYINT(1) NOT NULL COMMENT '回答中是否展示引用来源' DEFAULT 1, 
	created_at DATETIME(3) NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(3), 
	updated_at DATETIME(3) NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3), 
	PRIMARY KEY (id), 
	CONSTRAINT uk_workspace_retrieval_settings_workspace UNIQUE (workspace_id), 
	CONSTRAINT ck_workspace_retrieval_settings_top_k CHECK (top_k BETWEEN 1 AND 50), 
	CONSTRAINT ck_workspace_retrieval_settings_similarity_threshold CHECK (similarity_threshold BETWEEN 0 AND 1), 
	CONSTRAINT fk_workspace_retrieval_settings_workspace FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ======================================================================
-- chat_messages
-- ======================================================================
CREATE TABLE chat_messages (
	id BIGINT UNSIGNED NOT NULL COMMENT '聊天消息ID' AUTO_INCREMENT, 
	session_id BIGINT UNSIGNED NOT NULL COMMENT '聊天会话ID', 
	parent_message_id BIGINT UNSIGNED COMMENT '父消息ID', 
	`role` VARCHAR(32) NOT NULL COMMENT '消息角色：system/user/assistant/tool 等', 
	content LONGTEXT NOT NULL COMMENT '消息内容', 
	model_name VARCHAR(128) COMMENT '模型名称', 
	prompt_tokens INTEGER COMMENT '提示词 token 数', 
	completion_tokens INTEGER COMMENT '生成 token 数', 
	total_tokens INTEGER COMMENT '总 token 数', 
	latency_ms INTEGER COMMENT '响应耗时（毫秒）', 
	metadata JSON COMMENT '消息元数据', 
	created_at DATETIME(3) NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(3), 
	PRIMARY KEY (id), 
	CONSTRAINT fk_chat_messages_session FOREIGN KEY(session_id) REFERENCES chat_sessions (id) ON DELETE CASCADE, 
	CONSTRAINT fk_chat_messages_parent FOREIGN KEY(parent_message_id) REFERENCES chat_messages (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX idx_chat_messages_parent ON chat_messages (parent_message_id);
CREATE INDEX idx_chat_messages_role ON chat_messages (`role`);
CREATE INDEX idx_chat_messages_session_created ON chat_messages (session_id, created_at);

-- ======================================================================
-- chat_session_kbs
-- ======================================================================
CREATE TABLE chat_session_kbs (
	id BIGINT UNSIGNED NOT NULL COMMENT '会话知识库关联ID' AUTO_INCREMENT, 
	session_id BIGINT UNSIGNED NOT NULL COMMENT '聊天会话ID', 
	kb_id BIGINT UNSIGNED NOT NULL COMMENT '知识库ID', 
	created_at DATETIME(3) NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(3), 
	updated_at DATETIME(3) NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(3), 
	deleted_at DATETIME(3) COMMENT '软删除时间', 
	PRIMARY KEY (id), 
	CONSTRAINT uk_session_kb UNIQUE (session_id, kb_id), 
	CONSTRAINT fk_chat_session_kbs_session FOREIGN KEY(session_id) REFERENCES chat_sessions (id) ON DELETE CASCADE, 
	CONSTRAINT fk_chat_session_kbs_kb FOREIGN KEY(kb_id) REFERENCES knowledge_bases (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX idx_chat_session_kbs_kb ON chat_session_kbs (kb_id);

-- ======================================================================
-- documents
-- ======================================================================
CREATE TABLE documents (
	id BIGINT UNSIGNED NOT NULL COMMENT 'Document ID' AUTO_INCREMENT, 
	kb_id BIGINT UNSIGNED NOT NULL COMMENT 'Knowledge base ID', 
	title VARCHAR(255) NOT NULL COMMENT 'Document title', 
	source_type VARCHAR(32) NOT NULL COMMENT 'Source type: upload/url/api' DEFAULT 'upload', 
	source_uri VARCHAR(1024) COMMENT 'Source URI', 
	original_file_name VARCHAR(255) COMMENT 'Original file name', 
	file_ext VARCHAR(32) COMMENT 'File extension', 
	mime_type VARCHAR(128) COMMENT 'MIME type', 
	size_bytes BIGINT UNSIGNED COMMENT 'File size in bytes', 
	sha256 CHAR(64) COMMENT 'File SHA256 hash', 
	language VARCHAR(32) COMMENT 'Document language', 
	current_version_id BIGINT UNSIGNED COMMENT 'Current document version ID; no DB FK to avoid cyclic DDL', 
	parse_status VARCHAR(32) NOT NULL COMMENT 'Parse status: pending/processing/success/failed' DEFAULT 'pending', 
	index_status VARCHAR(32) NOT NULL COMMENT 'Index status: not_indexed/indexing/indexed/failed' DEFAULT 'not_indexed', 
	enabled BOOL NOT NULL COMMENT 'Whether the document is enabled' DEFAULT 1, 
	created_by BIGINT UNSIGNED NOT NULL COMMENT 'Creator user ID', 
	created_at DATETIME(3) NOT NULL COMMENT 'Created at' DEFAULT CURRENT_TIMESTAMP(3), 
	updated_at DATETIME(3) NOT NULL COMMENT 'Updated at' DEFAULT CURRENT_TIMESTAMP(3), 
	deleted_at DATETIME(3) COMMENT 'Soft delete time', 
	PRIMARY KEY (id), 
	CONSTRAINT fk_documents_kb FOREIGN KEY(kb_id) REFERENCES knowledge_bases (id) ON DELETE CASCADE, 
	CONSTRAINT fk_documents_created_by FOREIGN KEY(created_by) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX idx_documents_created_by ON documents (created_by);
CREATE INDEX idx_documents_kb ON documents (kb_id);
CREATE INDEX idx_documents_kb_status ON documents (kb_id, parse_status, index_status);
CREATE INDEX idx_documents_sha256 ON documents (sha256);
CREATE INDEX idx_documents_title ON documents (title);

-- ======================================================================
-- report_exports
-- ======================================================================
CREATE TABLE report_exports (
	id BIGINT UNSIGNED NOT NULL COMMENT 'Report export ID' AUTO_INCREMENT, 
	task_id BIGINT UNSIGNED NOT NULL COMMENT 'Report task ID', 
	export_format VARCHAR(32) NOT NULL COMMENT 'Export format', 
	storage_uri VARCHAR(1024) NOT NULL COMMENT 'Storage URI', 
	file_name VARCHAR(255) COMMENT 'File name', 
	size_bytes BIGINT UNSIGNED COMMENT 'File size in bytes', 
	status VARCHAR(32) NOT NULL COMMENT 'Export status' DEFAULT 'success', 
	created_at DATETIME(3) NOT NULL COMMENT 'Created at' DEFAULT CURRENT_TIMESTAMP(3), 
	PRIMARY KEY (id), 
	CONSTRAINT fk_report_exports_task FOREIGN KEY(task_id) REFERENCES report_tasks (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX idx_report_exports_format ON report_exports (export_format);
CREATE INDEX idx_report_exports_task ON report_exports (task_id);

-- ======================================================================
-- report_sections
-- ======================================================================
CREATE TABLE report_sections (
	id BIGINT UNSIGNED NOT NULL COMMENT 'Report section ID' AUTO_INCREMENT, 
	task_id BIGINT UNSIGNED NOT NULL COMMENT 'Report task ID', 
	parent_section_id BIGINT UNSIGNED COMMENT 'Parent section ID', 
	order_no INTEGER NOT NULL COMMENT 'Section order number', 
	title VARCHAR(255) NOT NULL COMMENT 'Section title', 
	requirement TEXT COMMENT 'Section requirement', 
	content LONGTEXT COMMENT 'Section content', 
	status VARCHAR(32) NOT NULL COMMENT 'Section status' DEFAULT 'pending', 
	created_at DATETIME(3) NOT NULL COMMENT 'Created at' DEFAULT CURRENT_TIMESTAMP(3), 
	updated_at DATETIME(3) NOT NULL COMMENT 'Updated at' DEFAULT CURRENT_TIMESTAMP(3), 
	PRIMARY KEY (id), 
	CONSTRAINT uk_report_section_order UNIQUE (task_id, order_no), 
	CONSTRAINT fk_report_sections_task FOREIGN KEY(task_id) REFERENCES report_tasks (id) ON DELETE CASCADE, 
	CONSTRAINT fk_report_sections_parent FOREIGN KEY(parent_section_id) REFERENCES report_sections (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX idx_report_sections_parent ON report_sections (parent_section_id);
CREATE INDEX idx_report_sections_status ON report_sections (task_id, status);

-- ======================================================================
-- document_tags
-- ======================================================================
CREATE TABLE document_tags (
	id BIGINT UNSIGNED NOT NULL COMMENT 'Document tag link ID' AUTO_INCREMENT, 
	document_id BIGINT UNSIGNED NOT NULL COMMENT 'Document ID', 
	tag_id BIGINT UNSIGNED NOT NULL COMMENT 'Tag ID; validated in service layer', 
	created_at DATETIME(3) NOT NULL COMMENT 'Created at' DEFAULT CURRENT_TIMESTAMP(3), 
	PRIMARY KEY (id), 
	CONSTRAINT uk_document_tag UNIQUE (document_id, tag_id), 
	CONSTRAINT fk_document_tags_document FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX idx_document_tags_document ON document_tags (document_id);
CREATE INDEX idx_document_tags_tag ON document_tags (tag_id);

-- ======================================================================
-- document_versions
-- ======================================================================
CREATE TABLE document_versions (
	id BIGINT UNSIGNED NOT NULL COMMENT 'Document version ID' AUTO_INCREMENT, 
	document_id BIGINT UNSIGNED NOT NULL COMMENT 'Document ID', 
	version_no INTEGER NOT NULL COMMENT 'Version number', 
	storage_uri VARCHAR(1024) COMMENT 'Stored file URI', 
	original_file_name VARCHAR(255) COMMENT 'Original file name', 
	sha256 CHAR(64) COMMENT 'File SHA256 hash', 
	parser_name VARCHAR(128) COMMENT 'Parser name', 
	parser_version VARCHAR(64) COMMENT 'Parser version', 
	parser_config JSON COMMENT 'Parser config', 
	page_count INTEGER COMMENT 'Page count', 
	char_count INTEGER COMMENT 'Character count', 
	token_count INTEGER COMMENT 'Token count', 
	status VARCHAR(32) NOT NULL COMMENT 'Version status: pending/processing/success/failed' DEFAULT 'pending', 
	error_message TEXT COMMENT 'Error message', 
	created_by BIGINT UNSIGNED NOT NULL COMMENT 'Creator user ID', 
	created_at DATETIME(3) NOT NULL COMMENT 'Created at' DEFAULT CURRENT_TIMESTAMP(3), 
	PRIMARY KEY (id), 
	CONSTRAINT uk_document_version UNIQUE (document_id, version_no), 
	CONSTRAINT fk_doc_versions_document FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE, 
	CONSTRAINT fk_doc_versions_created_by FOREIGN KEY(created_by) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX idx_doc_versions_document ON document_versions (document_id);
CREATE INDEX idx_doc_versions_sha256 ON document_versions (sha256);
CREATE INDEX idx_doc_versions_status ON document_versions (status);

-- ======================================================================
-- document_chunks
-- ======================================================================
CREATE TABLE document_chunks (
	id BIGINT UNSIGNED NOT NULL COMMENT 'Chunk ID' AUTO_INCREMENT, 
	kb_id BIGINT UNSIGNED NOT NULL COMMENT 'Knowledge base ID', 
	document_id BIGINT UNSIGNED NOT NULL COMMENT 'Document ID', 
	version_id BIGINT UNSIGNED NOT NULL COMMENT 'Document version ID', 
	chunk_no INTEGER NOT NULL COMMENT 'Chunk sequence number', 
	chunk_uid VARCHAR(128) NOT NULL COMMENT 'Unique chunk identifier', 
	content MEDIUMTEXT NOT NULL COMMENT 'Chunk content', 
	content_hash CHAR(64) NOT NULL COMMENT 'Chunk content SHA256 hash', 
	token_count INTEGER COMMENT 'Token count', 
	char_count INTEGER COMMENT 'Character count', 
	page_start INTEGER COMMENT 'Start page', 
	page_end INTEGER COMMENT 'End page', 
	section_title VARCHAR(255) COMMENT 'Section title', 
	metadata JSON COMMENT 'Chunk metadata', 
	enabled BOOL NOT NULL COMMENT 'Whether the chunk is enabled' DEFAULT 1, 
	created_at DATETIME(3) NOT NULL COMMENT 'Created at' DEFAULT CURRENT_TIMESTAMP(3), 
	updated_at DATETIME(3) NOT NULL COMMENT 'Updated at' DEFAULT CURRENT_TIMESTAMP(3), 
	PRIMARY KEY (id), 
	CONSTRAINT uk_chunk_uid UNIQUE (chunk_uid), 
	CONSTRAINT uk_version_chunk_no UNIQUE (version_id, chunk_no), 
	CONSTRAINT fk_chunks_kb FOREIGN KEY(kb_id) REFERENCES knowledge_bases (id) ON DELETE CASCADE, 
	CONSTRAINT fk_chunks_document FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE, 
	CONSTRAINT fk_chunks_version FOREIGN KEY(version_id) REFERENCES document_versions (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE FULLTEXT INDEX ft_chunks_content ON document_chunks (content);
CREATE INDEX idx_chunks_document ON document_chunks (document_id);
CREATE INDEX idx_chunks_hash ON document_chunks (content_hash);
CREATE INDEX idx_chunks_kb_enabled ON document_chunks (kb_id, enabled);
CREATE INDEX idx_chunks_version ON document_chunks (version_id);

-- ======================================================================
-- document_processing_tasks
-- ======================================================================
CREATE TABLE document_processing_tasks (
	id BIGINT UNSIGNED NOT NULL COMMENT '任务数据库主键' AUTO_INCREMENT, 
	task_id CHAR(36) NOT NULL COMMENT '对外暴露的任务 UUID', 
	kb_id BIGINT UNSIGNED NOT NULL COMMENT '知识库 ID', 
	document_id BIGINT UNSIGNED NOT NULL COMMENT '文档 ID', 
	version_id BIGINT UNSIGNED NOT NULL COMMENT '文档版本 ID', 
	created_by BIGINT UNSIGNED NOT NULL COMMENT '任务创建用户 ID', 
	status VARCHAR(32) NOT NULL COMMENT 'queued/running/success/failed/cancelled' DEFAULT 'queued', 
	stage VARCHAR(32) NOT NULL COMMENT 'uploaded/parsing/splitting/embedding/vector_upserting/finalizing/completed' DEFAULT 'uploaded', 
	progress INTEGER NOT NULL COMMENT '处理进度，范围 0-100' DEFAULT 0, 
	total_chunks INTEGER NOT NULL COMMENT 'Chunk 总数' DEFAULT 0, 
	processed_chunks INTEGER NOT NULL COMMENT '已完成向量入库的 Chunk 数' DEFAULT 0, 
	failed_chunks INTEGER NOT NULL COMMENT '处理失败的 Chunk 数' DEFAULT 0, 
	retry_count INTEGER NOT NULL COMMENT '已重试次数' DEFAULT 0, 
	max_retries INTEGER NOT NULL COMMENT '最大重试次数' DEFAULT 3, 
	error_code VARCHAR(64) COMMENT '业务错误码', 
	error_message TEXT COMMENT '任务失败信息', 
	started_at DATETIME(3) COMMENT '任务开始时间', 
	completed_at DATETIME(3) COMMENT '任务完成时间', 
	created_at DATETIME(3) NOT NULL COMMENT '任务创建时间' DEFAULT CURRENT_TIMESTAMP(3), 
	updated_at DATETIME(3) NOT NULL COMMENT '任务更新时间' DEFAULT CURRENT_TIMESTAMP(3), 
	PRIMARY KEY (id), 
	CONSTRAINT uk_document_processing_tasks_task_id UNIQUE (task_id), 
	CONSTRAINT fk_document_processing_tasks_kb FOREIGN KEY(kb_id) REFERENCES knowledge_bases (id) ON DELETE CASCADE, 
	CONSTRAINT fk_document_processing_tasks_document FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE, 
	CONSTRAINT fk_document_processing_tasks_version FOREIGN KEY(version_id) REFERENCES document_versions (id) ON DELETE CASCADE, 
	CONSTRAINT fk_document_processing_tasks_created_by FOREIGN KEY(created_by) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX idx_document_processing_tasks_created_at ON document_processing_tasks (created_at);
CREATE INDEX idx_document_processing_tasks_document ON document_processing_tasks (document_id);
CREATE INDEX idx_document_processing_tasks_kb_status ON document_processing_tasks (kb_id, status);
CREATE INDEX idx_document_processing_tasks_status_stage ON document_processing_tasks (status, stage);

-- ======================================================================
-- chunk_embeddings
-- ======================================================================
CREATE TABLE chunk_embeddings (
	id BIGINT UNSIGNED NOT NULL COMMENT 'Embedding ID' AUTO_INCREMENT, 
	kb_id BIGINT UNSIGNED NOT NULL COMMENT 'Knowledge base ID', 
	chunk_id BIGINT UNSIGNED NOT NULL COMMENT 'Document chunk ID', 
	vector_store_type VARCHAR(64) NOT NULL COMMENT 'Vector store type', 
	vector_collection VARCHAR(128) NOT NULL COMMENT 'Vector collection name', 
	vector_id VARCHAR(256) NOT NULL COMMENT 'Vector ID in the vector store', 
	embedding_model VARCHAR(128) NOT NULL COMMENT 'Embedding model name', 
	embedding_dim INTEGER NOT NULL COMMENT 'Embedding vector dimension', 
	content_hash CHAR(64) NOT NULL COMMENT 'Chunk content SHA256 hash', 
	status VARCHAR(32) NOT NULL COMMENT 'Embedding status' DEFAULT 'active', 
	created_at DATETIME(3) NOT NULL COMMENT 'Created at' DEFAULT CURRENT_TIMESTAMP(3), 
	updated_at DATETIME(3) NOT NULL COMMENT 'Updated at' DEFAULT CURRENT_TIMESTAMP(3), 
	PRIMARY KEY (id), 
	CONSTRAINT uk_chunk_model UNIQUE (chunk_id, embedding_model), 
	CONSTRAINT uk_vector_mapping UNIQUE (vector_store_type, vector_collection, vector_id), 
	CONSTRAINT fk_chunk_embeddings_kb FOREIGN KEY(kb_id) REFERENCES knowledge_bases (id) ON DELETE CASCADE, 
	CONSTRAINT fk_chunk_embeddings_chunk FOREIGN KEY(chunk_id) REFERENCES document_chunks (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX idx_embeddings_content_hash ON chunk_embeddings (content_hash);
CREATE INDEX idx_embeddings_kb_model ON chunk_embeddings (kb_id, embedding_model);
CREATE INDEX idx_embeddings_status ON chunk_embeddings (status);

-- ======================================================================
-- report_sources
-- ======================================================================
CREATE TABLE report_sources (
	id BIGINT UNSIGNED NOT NULL COMMENT 'Report source ID' AUTO_INCREMENT, 
	task_id BIGINT UNSIGNED NOT NULL COMMENT 'Report task ID', 
	section_id BIGINT UNSIGNED COMMENT 'Report section ID', 
	kb_id BIGINT UNSIGNED NOT NULL COMMENT 'Knowledge base ID', 
	document_id BIGINT UNSIGNED NOT NULL COMMENT 'Document ID', 
	chunk_id BIGINT UNSIGNED NOT NULL COMMENT 'Document chunk ID', 
	citation_no INTEGER COMMENT 'Citation number', 
	quote_text TEXT COMMENT 'Quoted text', 
	score NUMERIC(10, 6) COMMENT 'Retrieval score', 
	created_at DATETIME(3) NOT NULL COMMENT 'Created at' DEFAULT CURRENT_TIMESTAMP(3), 
	PRIMARY KEY (id), 
	CONSTRAINT fk_report_sources_task FOREIGN KEY(task_id) REFERENCES report_tasks (id) ON DELETE CASCADE, 
	CONSTRAINT fk_report_sources_section FOREIGN KEY(section_id) REFERENCES report_sections (id) ON DELETE SET NULL, 
	CONSTRAINT fk_report_sources_kb FOREIGN KEY(kb_id) REFERENCES knowledge_bases (id) ON DELETE CASCADE, 
	CONSTRAINT fk_report_sources_document FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE, 
	CONSTRAINT fk_report_sources_chunk FOREIGN KEY(chunk_id) REFERENCES document_chunks (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE INDEX idx_report_sources_chunk ON report_sources (chunk_id);
CREATE INDEX idx_report_sources_section ON report_sources (section_id);
CREATE INDEX idx_report_sources_task ON report_sources (task_id);

SET FOREIGN_KEY_CHECKS = 1;
