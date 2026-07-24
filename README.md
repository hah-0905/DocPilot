# DocPilot

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?style=flat-square&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-Frontend-3178C6?style=flat-square&logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-Dev_Server-646CFF?style=flat-square&logo=vite&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-8.4-4479A1?style=flat-square&logo=mysql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)

DocPilot 是一个面向多知识库场景的智能文档问答与报告生成平台。项目基于 FastAPI、React、MySQL 与 RAG（Retrieval-Augmented Generation）技术构建，支持文档上传、文档解析、文本切分、知识库管理、语义检索、智能问答和报告生成等能力。

本项目定位为一个完整的 AI 应用工程实践项目，重点展示从后端 API、数据库建模、文档处理、向量检索、大模型调用到前端交互页面的端到端开发能力。

---

## 项目特性

- 多知识库管理：支持创建、查看和管理多个知识库
- 文档上传与解析：支持 PDF、Word 等文档内容解析
- 文本切分：将文档内容切分为可检索的 chunk
- 向量化处理：对文档片段生成 embedding 并存储
- 语义检索：根据用户问题召回相关文档片段
- RAG 问答：结合检索结果调用大模型生成回答
- 会话管理：支持问答会话与历史消息管理
- 用户模块：提供用户注册、登录与鉴权基础能力
- 前后端分离：后端提供 REST API，前端负责页面展示与交互
- Docker Compose 部署：支持一键启动 MySQL、后端和前端服务

---

## 技术栈

### Backend

- Python
- FastAPI
- SQLAlchemy
- MySQL
- Pydantic
- OpenAI API
- pypdf
- python-docx
- ChromaDB / DashVector
- Uvicorn

### Frontend

- React
- Vite
- Tailwind CSS
- JavaScript

### Infrastructure

- Docker
- Docker Compose
- MySQL 8.0

---

## 项目结构

```text
DocPilot
├── docpilot-backend
│   ├── app
│   │   ├── api              # API 路由层
│   │   ├── core             # 核心配置
│   │   ├── db               # 数据库连接与会话管理
│   │   ├── models           # SQLAlchemy 数据模型
│   │   ├── schemas          # Pydantic 请求 / 响应模型
│   │   ├── services         # 业务逻辑层
│   │   └── utils            # 工具函数
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
│
├── docpilot-front-end
│   ├── src
│   │   ├── api              # 前端 API 请求封装
│   │   ├── components       # 通用组件
│   │   ├── pages            # 页面组件
│   │   ├── App.jsx
│   │   ├── index.css
│   │   └── main.jsx
│   ├── package.json
│   ├── tailwind.config.js
│   └── vite.config.js
│
├── docker-compose.yml
└── README.md
```

---

## 核心模块说明

### 1. 用户模块

负责用户注册、登录、密码加密、身份认证等基础能力，为后续知识库权限控制和会话隔离提供基础。

### 2. 知识库模块

用于管理知识库对象。每个知识库可以关联多个文档，后续问答时可以限定在指定知识库范围内进行检索和生成。

### 3. 文档模块

负责文档上传、文档元数据保存、文档内容解析、文本切分和 chunk 入库。

### 4. 向量检索模块

负责将文档 chunk 转换为向量，并在问答时根据用户问题进行相似度检索，返回与问题最相关的文档片段。

### 5. RAG 问答模块

问答流程主要包括：

1. 接收用户问题
2. 根据问题生成查询向量
3. 从知识库中召回相关 chunk
4. 构造 Prompt
5. 调用大语言模型生成回答
6. 返回回答与参考上下文

### 6. 前端页面模块

前端提供知识库管理、文档查看、文档上传、问答交互等页面，负责与后端 API 进行通信并展示结果。

---

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/hah-0905/DocPilot.git
cd DocPilot
```

### 2. 配置环境变量

复制开发环境模板，并仅在本地填写真实配置（不要提交该文件）：

```bash
cp .env.dev.example .env.dev
```

### 3. 启动服务

请使用下文的“阿里云服务器开发部署”流程启动服务；MySQL 和 Redis 由独立基础设施 Compose 管理。

启动后访问：

```text
前端地址：http://localhost:5173
后端地址：http://localhost:8000
接口文档：http://localhost:8000/docs
```

---

## 本地开发

### 后端开发

进入后端目录：

```bash
cd docpilot-backend
```

创建虚拟环境：

```bash
python -m venv .venv
```

激活虚拟环境：

```bash
# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

安装依赖：

```bash
pip install -r requirements.txt
```

启动后端服务：

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 前端开发

进入前端目录：

```bash
cd docpilot-front-end
```

安装依赖：

```bash
npm install
```

启动前端服务：

```bash
npm run dev
```

---

## 主要 API 模块

项目后端按业务领域拆分 API 路由，当前主要包括：

```text
用户模块：用户注册、登录、认证
知识库模块：知识库创建、查询、更新、删除
文档模块：文档上传、解析、chunk 查看
问答模块：基于知识库的智能问答
```

典型接口示例：

```text
POST /users/register
POST /users/login

GET  /knowledge-bases
POST /knowledge-bases

POST /knowledge-bases/{kb_id}/documents
GET  /knowledge-bases/{kb_id}/documents
GET  /knowledge-bases/{kb_id}/documents/{document_id}/chunks

POST /chat/completions
```

具体接口字段以 FastAPI 自动生成的 `/docs` 文档为准。

---

## RAG 流程

```text
用户问题
   ↓
问题向量化
   ↓
知识库向量检索
   ↓
召回相关文档片段
   ↓
构造上下文 Prompt
   ↓
调用大语言模型
   ↓
生成回答
   ↓
返回答案与相关上下文
```

---

## 数据模型概览

当前项目包含以下核心数据模型：

- User：用户信息
- Workspace：工作区
- WorkspaceMember：工作区成员
- KnowledgeBase：知识库
- Document：文档元数据
- ChunkEmbedding：文档片段与向量信息
- Chat / Message：会话与问答记录

---

## 当前进度

- [x] 项目初始化
- [x] Docker Compose 基础编排
- [x] MySQL 数据库接入
- [x] 后端项目分层结构
- [x] 用户模块
- [x] 知识库模块
- [x] 文档上传与解析
- [x] 文档 chunk 管理
- [x] 向量服务基础封装
- [x] RAG 服务基础封装
- [x] 问答接口基础实现
- [x] 前端基础页面
- [ ] 权限体系完善
- [ ] 检索效果优化
- [ ] 引用来源展示
- [ ] 报告生成能力完善
- [ ] 生产环境部署配置

---

## 后续规划

- 完善知识库权限控制
- 增加文档解析状态展示
- 支持更多文档格式
- 优化文本切分策略
- 增加混合检索能力
- 支持回答引用来源展示
- 增加流式问答输出
- 增加报告生成模板
- 增加接口测试与单元测试
- 增加生产环境部署文档

---

## 适用场景

- 课程资料问答系统
- 企业内部知识库问答
- 项目文档检索助手
- PDF / Word 文档智能问答
- 基于 RAG 的 AI 应用开发实践
- AI 后端工程能力展示项目

---

## 项目亮点

- 采用前后端分离架构，结构清晰，便于扩展
- 后端按照 API、Schema、Model、Service 分层组织
- 支持从文档解析到向量检索再到大模型回答的完整 RAG 链路
- 使用 Docker Compose 编排数据库、后端和前端，降低启动成本
- 适合作为 AI 应用开发、RAG 工程化和 FastAPI 后端能力展示项目

---

## 注意事项

1. 本项目仍处于持续开发阶段，部分功能可能尚未完全完善。
2. 本地启动前需要正确配置 `.env.dev`，并通过 Compose 的 `--env-file` 传入容器。
3. 使用大模型相关能力前，需要配置有效的 API Key。
4. 生产环境部署时应关闭 Debug 模式，并使用更安全的数据库密码和密钥管理方式。

---

## 阿里云服务器开发部署

部署流程为：本地修改并测试 → 推送 GitHub → 服务器拉取代码 → Docker Compose 更新前后端。基础设施（MySQL、Redis）独立运行，应用 Compose 不会创建、删除或重建其数据卷。

### 服务器拉取代码

```bash
sudo -iu warren
cd /srv/DocPilot
git status
git pull origin main
```

拉取前必须检查 `git status`。日常开发不要使用 root，也不要用 `git reset --hard` 覆盖服务器上的修改。

### 基础设施

```bash
docker compose \
  -f docker-compose.infra.yml \
  --env-file .env.infra \
  up -d
```

不要执行 `docker compose down -v`，以免删除持久化数据卷。

### 创建开发配置与启动前后端

```bash
cp .env.dev.example .env.dev
```

由部署人员填写 `.env.dev` 中的真实配置。随后启动应用服务：

```bash
docker compose \
  -p docpilot-dev \
  -f docker-compose.dev.yml \
  --env-file .env.dev \
  up -d --build
```

`docker-compose.dev.yml` 只包含 `backend` 和 `frontend`，通过外部网络连接 `mysql` 与 `redis` 服务。

### 日志与更新

```bash
docker compose \
  -p docpilot-dev \
  -f docker-compose.dev.yml \
  logs -f backend
```

Python/React 源码的普通修改会因源代码挂载和 `--reload` 自动生效。修改 `requirements.txt`、`Dockerfile`、`package.json`、`package-lock.json` 或 `docker-compose.dev.yml` 后，重新执行上述 `up -d --build` 命令。

### SSH 隧道

```bash
ssh \
  -L 5173:127.0.0.1:5173 \
  -L 8000:127.0.0.1:8000 \
  warren@服务器公网IP
```

本地浏览器访问 `http://localhost:5173` 和 `http://localhost:8000/docs`。不要向公网开放 3306、6379、5173 或 8000 端口。

---

## License

本项目暂未指定开源许可证。如需开源发布，建议补充 MIT、Apache-2.0 或其他合适的 License。
