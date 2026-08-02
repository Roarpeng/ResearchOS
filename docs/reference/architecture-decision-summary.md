# 架构决策速查（一页纸）

ResearchOS 架构期决策摘要。细节见 `docs/01`–`05` 与各子目录。

## 产品一句话

开源、可私有部署的 **Agent 研究操作系统**：Deep Research + Knowledge OS +（Phase 5）Engineering Copilot。

## 分层

```
Frontend (流式研究控制台)
    → FastAPI Gateway (auth / session / REST / WS)
        → LangGraph Runtime (state / checkpoint / interrupt)
            → Supervisor → Planner · Research · Reviewer · Writer · Memory
                → MCP Tools
                → Hybrid GraphRAG
                → LiteLLM → Cloud APIs | Ollama
```

## 技术选型（锁定方向）

| 能力 | 选择 |
|------|------|
| Agent 运行时 | LangGraph |
| API | FastAPI |
| 模型网关 | LiteLLM |
| 元数据 | PostgreSQL |
| 缓存 / 事件缓冲 | Redis |
| 对象存储 | MinIO |
| 向量 | Qdrant |
| 图谱 | Neo4j |
| 全文（可选） | OpenSearch |
| 导出（可选） | Gotenberg / Typst |
| 定时与通知（可选） | n8n（仅此） |
| 本地模型（可选） | Ollama |

## 六条硬原则

1. **Agent First** — 推理主链路不在 n8n  
2. **MCP Native** — 外部能力工具化  
3. **Knowledge Evolution** — 知识可累积回写  
4. **Model Independent** — 逻辑模型名，不绑供应商  
5. **Private Deployment** — 默认可内网/气隙  
6. **Docs Driven** — 契约先于代码  

## 研究主路径

`问题 → Plan → 工具+检索取证 → 反思/评审 →（可 interrupt）→ 带引用报告 → 可选入库`

## API 入口

- REST：`/api/v1/{auth,sessions,research,knowledge,health}`  
- WS：`/api/v1/ws/research/{task_id}`（事件带单调 `seq`）  

## 部署默认姿态

Docker Compose 拉起核心六依赖（PG/Redis/MinIO/Qdrant/Neo4j/LiteLLM）+ gateway/runtime/worker/frontend；search/export/automation/gpu 用 profile。

## Phase 路线

| Phase | 内容 |
|-------|------|
| 0 | 架构与文档（当前） |
| 1 | 基础设施 |
| 2 | Runtime + 流式 + checkpoint |
| 3 | 入库 + GraphRAG |
| 4 | Deep Research Agent |
| 5 | 工业：ROS2 / PLC / CAD / Isaac Sim |

## 明确不做什么（现阶段）

- 用 n8n 实现 Agent/RAG 主逻辑  
- 前端直连模型或向量库  
- Phase 5 对生产 PLC/机器人无人值守写操作  
- 绑定单一云模型厂商  

## 源决策溯源

竞品分析 n8n RAG → 平台化升级的 12 条改进见  
[source-conversation-summary.md](./source-conversation-summary.md)。

## 仓库

https://github.com/Roarpeng/ResearchOS
