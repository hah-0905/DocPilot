# 个人模型配置（BYOK）

设置页可以选择“平台默认”或“个人配置”。每个账号保存一套个人服务商、模型与凭据。普通聊天、流式聊天、知识库问答和报告共用运行配置解析层；文档和查询 Embedding 始终使用平台的 Embedding 配置。工作区原有的 owner/admin 权限保持不变，个人配置仅影响当前登录账号。

## 服务端配置

新增环境变量（只放在服务端环境或秘密管理服务中，不能使用 `VITE_` 前缀）：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `PERSONAL_MODEL_MASTER_KEY` | 未设置 | 稳定的 Fernet 主密钥，URL-safe Base64 编码的 32 字节随机值。必须持久保存并与数据库分离。 |
| `PLATFORM_MODELS` | `[]` | JSON 数组，额外允许的平台模型；`MODEL_NAME` 始终自动加入目录。 |
| `PERSONAL_MODEL_PROVIDERS` | `[]` | 服务端维护的额外服务商 JSON 数组，见下方示例。 |
| `LLM_TIMEOUT_SECONDS` | `60` | 模型及 Embedding 调用的超时秒数，范围 1–300。关闭 SDK 自动重试。 |

默认个人服务商 `platform` 使用已有 `OPENAI_BASE_URL`，模型目录为 `MODEL_NAME` 加 `PLATFORM_MODELS`。`platform` 是服务商 ID，与“平台默认 / 个人配置”这两个凭据来源无关：个人模式选择它时仍使用用户自己的 Key。额外服务商使用 OpenAI 兼容接口，ID 不能重复或使用保留值 `platform`；地址必须为 HTTPS，不能含用户名、密码、查询参数或片段。浏览器不能提交地址，也不会收到地址或平台 Key。

配置示例（以下均为公开配置或占位信息，不含凭据）：

```dotenv
MODEL_NAME=qwen3.8-flash
PLATFORM_MODELS=[]
PERSONAL_MODEL_PROVIDERS='[{"id":"deepseek","label":"DeepSeek","base_url":"https://api.deepseek.com/v1","models":["deepseek-chat","deepseek-reasoner"]}]'
LLM_TIMEOUT_SECONDS=60
```

管理员应按账户实际可用模型维护目录，目录不表示所有服务商账号都拥有该模型权限。实施时已核查本机后端配置：默认模型为 `qwen3.8-flash`；没有改动本机 `.env` 或已有凭据。

首次部署时生成一次主密钥并直接写入受限文件，下面命令不会向终端输出密钥。请将路径替换成数据库目录之外的安全位置：

```sh
umask 077
python -c 'from cryptography.fernet import Fernet; import sys; sys.stdout.buffer.write(Fernet.generate_key())' > /secure/path/docpilot-byok.key
```

由部署环境/秘密管理服务读取该文件并注入 `PERSONAL_MODEL_MASTER_KEY`。本地开发可以手工将值存入被忽略的后端 `.env`；Docker Compose 使用项目根目录的环境配置，新增变量已透传到后端。不要在每次启动时重新生成、不要提交到 Git、不要与数据库备份放在一起。多实例必须使用同一个主密钥。配置变更后重启后端。

缺少或格式错误的主密钥时：读取接口返回 `available=false` 和原因；保存、连接测试、已启用个人模式的生成调用返回 503。未启用个人模式的用户继续使用平台；删除操作仍可用。主密钥丢失或替换后，旧密文无法解密，必须恢复原密钥，或者由用户重新填写 Key。第一版不提供无损密钥轮换工具。

## 数据库升级

现有 MySQL 8.0 部署在上线前备份并执行：

```sh
mysql -h HOST -u USER -p DATABASE < docpilot-backend/migrations/20261014_personal_model_config.sql
```

使用交互密码提示，避免把密码放进命令行。该脚本可重复运行：新增 `user_model_configs` 表，`user_id` 同时为主键和级联删除外键，保存服务商、模型、认证加密凭据、末四位、启用状态和创建/更新时间；移除工作区模型字段写死的 DeepSeek 数据库默认值。脚本不修改现有工作区记录、用户资料、文档或向量数据。没有对本机真实数据库执行迁移。

新部署可用更新后的 `schema.sql` 初始化；应用启动的 `create_all` 也会创建个人配置表，但不会修改现有列的默认值，所以旧部署仍需执行升级脚本。首次创建工作区设置（包括只更新温度时）由应用显式继承 `MODEL_NAME`。

旧工作区如果仍引用已不在平台目录中的模型，会返回明确的 422；管理员/所有者应在设置页重新选择。不会静默重写用户的工作区配置，也不会把不同服务商模型路由到错误地址。需要继续使用某个旧平台模型时，只应在确认平台地址支持它后将其加入 `PLATFORM_MODELS`。

## 接口与行为

所有接口都从现有 Bearer 登录凭证获取用户身份，不接受目标 `user_id`。个人配置没有按用户 ID 访问的路由。

| 方法与路径 | 行为 |
| --- | --- |
| `GET /api/settings/model-catalog` | 返回平台默认模型、平台允许列表、个人服务商及其模型目录。 |
| `GET /api/settings/personal-model` | 返回可用性、配置状态、来源开关、服务商、模型和末四位掩码；不返回 Key 或密文。 |
| `PUT /api/settings/personal-model` | 保存 `provider_id`、`model_name`、`enabled` 和可选 `api_key`。省略 Key 或传 `null` 时保留原凭据；首次保存和切换服务商需提供新 Key。空字符串不是删除。 |
| `POST /api/settings/personal-model/test` | 测试当前表单配置，可复用本账号已保存 Key；不写数据库。 |
| `DELETE /api/settings/personal-model` | 仅删除本账号配置，恢复平台来源。 |
| `GET /api/settings/model/{workspace_id}` | 加载工作区设置，复用原 owner/admin 权限检查。 |

保存不隐含外部连接测试。测试连接发送固定的极短输入，最多生成 16 tokens，SDK 超时 10 秒、整体预算 12 秒且不重试，可能产生少量费用。配置请求体最多 8 KiB；Key 限 8–4096 个可打印、非空白 ASCII 字符。测试、保存、删除后页面清空输入，Key 只暂存于组件内存，不存入 localStorage、sessionStorage 或 URL。

运行配置：个人配置已启用时，采用该用户的服务商、模型与解密 Key；其他情况下使用工作区模型和平台 Key。温度、生成长度和语言字段沿用工作区配置。个人凭据错误、超时、已下架模型及解密失败都明确报错，绝不重试平台凭据。报告的旧 `model_name` 请求字段继续接受，但不控制路由；数据库记录实际使用模型。流式错误保持原 SSE `event: error` 协议，内容已经脱敏。

凭据用 Fernet 认证加密，认证载荷绑定用户 ID 和服务商，防止数据库密文被跨账号或服务商交换。数据库驱动关闭 SQL echo 并隐藏参数；供应商异常和配置校验错误不回显请求内容；SDK 请求日志被限制为 WARNING。每次模型/Embedding 调用创建并关闭独立客户端，流结束、失败、取消或提前关闭时释放资源。

## 验证

在后端虚拟环境运行完整现有测试和新增测试：

```sh
cd docpilot-backend
.venv/bin/python -m unittest discover -s tests -v
```

前端：

```sh
cd docpilot-front-end
npm run build
```

新增测试采用内存 SQLite、模拟令牌存储和模拟模型 SDK，不连接真实模型、不修改真实用户或运行数据。覆盖真实 Bearer 认证、跨用户隔离、密文与响应/日志脱敏、凭据保留/替换/删除、运行配置、三种生成入口、并发隔离、错误/超时/不支持模型不回退、测试预算、缺失/错误/轮换主密钥、客户端释放及工作区默认值与权限。

本次验证结果：后端完整套件 99 项通过；前端 Vite 生产构建通过（308 个模块）。MySQL 升级脚本未在真实数据库执行，部署时按上述步骤应用。
