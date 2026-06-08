# DocPilot

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
