# ResearchOS 仓库布局 / Repository Layout

> 目标布局（Target Layout）。Phase 0 以 `docs/` 为主；代码目录随 Phase 1+ 落地。命名与边界变更需更新本文。

```text
ResearchOS/
├── frontend/                 # Web UI：任务、流式进度、引用与报告
├── gateway/                  # FastAPI：认证、会话、REST/WS、Webhook
├── runtime/                  # LangGraph 执行引擎、Checkpoint、事件
├── agents/                   # Supervisor 与各专家 Agent
│   ├── supervisor/
│   ├── planner/
│   ├── research/
│   ├── analysis/
│   ├── reviewer/
│   ├── writer/
│   └── memory/
├── tools/                    # MCP Servers 与 Provider 适配器
│   ├── search_router/
│   ├── browser/
│   ├── documents/
│   ├── knowledge_graph/
│   ├── vector_store/
│   ├── repo/
│   └── report/
├── knowledge/                # ETL、分块、抽取、Hybrid 检索融合
│   ├── parsers/              # Docling / MarkItDown / Unstructured 适配
│   ├── chunking/
│   ├── extract/
│   └── retrieval/
├── sdk/                      # 可选：Python/TS 客户端
├── deploy/                   # Docker Compose、K8s、环境模板
│   ├── compose/
│   ├── k8s/                  # 后期
│   └── optional/n8n/         # 明确标注 peripheral
├── docs/                     # 设计文档与 ADR（Single Source of Truth）
│   ├── core/
│   ├── adr/
│   ├── agents/
│   ├── runtime/
│   ├── knowledge/
│   ├── mcp/
│   ├── api/
│   ├── workflows/
│   ├── frontend/
│   ├── deployment/
│   ├── industrial/
│   └── reference/
├── scripts/                  # 开发、评测、迁移脚本
├── tests/                    # 单测 / 契约测 / 评测集（随阶段）
├── README.md
└── ROADMAP.md
```

---

## 模块职责

### `frontend/`

用户交互与流式界面。消费 Gateway API；不持有模型密钥；不做检索融合。

### `gateway/`

边缘 API 层：鉴权、会话、任务入口、流式转发、可选 Webhook。保持薄。

### `runtime/`

LangGraph 图编译与执行、Checkpointer、中断恢复、MCP Client 会话、事件发射。见 [ADR-0001](./adr/0001-agent-runtime-langgraph.md)。

### `agents/`

纯业务策略与节点实现。依赖 Runtime 抽象与工具契约，不直接依赖具体搜索 SDK。

### `tools/`

MCP Server 实现。每个子目录尽量独立版本与 Dockerfile。Search Router 见 [ADR-0007](./adr/0007-search-router-mcp.md)。

### `knowledge/`

文档入库与 Hybrid 检索核心算法/管道。可被 MCP Server 调用，避免 Agent 直访数据库驱动散落。

### `deploy/`

容器与配置。`optional/n8n` 不得被描述为「核心依赖」。

### `docs/`

架构与产品 SoT。索引见 [docs/README.md](./README.md)。

---

## 依赖方向（允许 / 禁止）

```text
frontend → gateway (HTTP)
gateway → runtime
runtime → agents
runtime → tools (MCP)
agents ↛ concrete provider SDKs
tools → knowledge / storage drivers
knowledge → storage
agents → LiteLLM (via runtime model client) ✓
n8n → gateway only ✓
n8n → runtime/agents  ✗
```

---

## 文档与代码同步规则

| 变更类型 | 必须更新 |
|----------|----------|
| 新 MCP Server | `tools/` + `docs/mcp/` + 必要时 ADR |
| 新 Agent 角色 | `agents/` + `docs/agents/` + 系统设计 |
| 存储拓扑变化 | ADR + `04-Technology-Selection.md` + deploy |
| 阶段交付完成 | `ROADMAP.md` + `05-Development-Roadmap.md` + 根 README Status |

---

## 相关文档

- [架构](./01-Architecture.md)
- [技术选型](./04-Technology-Selection.md)
- [路线图](../ROADMAP.md)
