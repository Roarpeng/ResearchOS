# 设计原则 / Design Principles

ResearchOS 的一切架构决策应能映射到以下六条原则。偏离时必须通过 ADR 说明理由。

---

## 原则总览

| # | 原则 | 英文 | 一句话 |
|---|------|------|--------|
| 1 | Agent 优先 | Agent First | 产品单元是可调度、可恢复的 Agent，而非脚本或 DAG 节点 |
| 2 | MCP 原生 | MCP Native | 外部能力一律以 MCP Tool 暴露，禁止旁路硬编码集成 |
| 3 | 知识进化 | Knowledge Evolution | 研究产物必须回流知识层，系统越用越聪明 |
| 4 | 模型无关 | Model Independent | 业务逻辑不绑定任何单一 LLM Provider |
| 5 | 私有可部署 | Private Deploy | 默认支持内网 / 私有云完整运行 |
| 6 | 文档驱动 | Docs-Driven | 重大能力先文档与 ADR，再写代码 |

---

## 1. Agent First（Agent 优先）

### 含义

系统的主抽象是 **Agent** 与 **Supervisor**：具备目标、计划、工具使用权、反思能力与可持久化状态。用户请求进入的是研究状态机，而不是一次性 Prompt。

### 要求

- 使用 LangGraph（或等价状态图运行时）管理计划、证据、引用与检查点。
- 支持中断（Human-in-the-loop）、重试与从 Checkpoint 恢复。
- Supervisor 负责编排，不亲自做深度检索与写作（职责分离）。

### 反模式

- 把多步研究写成巨型 Prompt 或单次 Function Calling。
- 用 n8n / Airflow DAG 表达 Agent 反思环与动态重规划。
- UI 直接拼装 Prompt 绕过 Runtime。

### 相关 ADR

- [ADR-0001 Agent Runtime → LangGraph](../adr/0001-agent-runtime-langgraph.md)

---

## 2. MCP Native（MCP 原生）

### 含义

**Model Context Protocol (MCP)** 是工具层的标准协议。搜索、浏览器、GitHub、文档解析、图谱读写、报告渲染等，均以 MCP Server / Tool 形式接入。

### 要求

- Agent 只依赖「工具契约」（名称、schema、权限），不依赖具体实现库。
- 新增外部系统优先写 MCP Server，再被 Runtime 发现与调用。
- 工具调用可观测、可审计、可限流。

### 反模式

- 在 Agent 代码里直接 `requests.get` 调搜索 API。
- 为每个工具复制一套私有插件 SDK，导致生态碎片化。
- 把密钥散落在 Agent Prompt 或前端。

### 相关 ADR

- [ADR-0002 MCP-Native Tools](../adr/0002-mcp-native-tools.md)
- [ADR-0007 Search Router MCP](../adr/0007-search-router-mcp.md)

---

## 3. Knowledge Evolution（知识进化）

### 含义

ResearchOS 是 **Knowledge OS**：每次研究不仅产出报告，还更新实体、关系、证据与向量索引。知识随任务累积，而不是会话结束即丢弃。

### 要求

- ETL 管道：解析（Docling / MarkItDown / Unstructured）→ 语义分块 → Embedding → 图谱抽取 → 索引。
- Hybrid 检索：Graph + Vector + Fulltext，由路由策略融合（见 Hybrid RAG）。
- Memory Agent 负责会话记忆与长期记忆的写入策略。
- 引用（Citation）与证据（Evidence）一等公民，可回溯到源文档段落或 URL。

### 反模式

- 只做「当次检索上下文塞进 Prompt」，不落库。
- 图谱与向量割裂更新，导致检索不一致。
- 无版本/无来源的实体覆盖写入。

### 相关 ADR

- [ADR-0003 Hybrid GraphRAG](../adr/0003-hybrid-graphrag.md)

---

## 4. Model Independent（模型无关）

### 含义

推理、嵌入、重排序等模型能力通过 **LiteLLM Model Gateway** 访问。更换供应商不应改写 Agent 业务代码。

### 要求

- 统一的模型路由、限流、fallback、成本记账入口。
- 支持云端 API 与本地 Ollama / vLLM 等。
- Prompt 与结构化输出 schema 与具体 SDK 解耦。

### 反模式

- 业务代码 `import openai` 并写死模型名散落各处。
- 某一 Agent 只能在某个厂商模型上运行且无文档说明。
- 把 Embeddings 提供商与 Chat 提供商强行绑死为同一家。

### 相关 ADR

- [ADR-0004 Model Gateway → LiteLLM](../adr/0004-model-gateway-litellm.md)

---

## 5. Private Deploy（私有可部署）

### 含义

默认交付形态是可私有化的容器化系统：数据、模型调用策略、工具访问均由部署方控制。

### 要求

- Docker Compose 覆盖核心依赖：PostgreSQL、Redis、MinIO、Qdrant、Neo4j、OpenSearch（或 BM25 组件）、LiteLLM、Gateway、Runtime。
- 密钥经环境变量 / Secret 管理；对象存储可切 S3 兼容后端。
- 可关闭所有出站工具，仅用内网知识库运行（降级模式需文档化）。

### 反模式

- 核心路径依赖单一公有 SaaS 且无自托管替代。
- 文档与向量强制上传到第三方托管向量库才能工作。

---

## 6. Docs-Driven（文档驱动开发）

### 含义

在实现复杂子系统前，先完成愿景/设计/ADR。文档是协作接口，也是评审清单。

### 要求

- 新模块：至少「问题 → 方案 → 接口 → 风险」四段说明或对应 ADR。
- 破坏性变更：更新 ADR Status 或新增 ADR，并改 ROADMAP。
- 术语统一维护于 [术语表](./03-glossary.md)。

### 反模式

- 「先写完再说文档」导致实现与架构叙事分叉。
- ADR 事后补写且与代码不一致。

---

## 原则冲突时的裁决顺序

当原则冲突时，按以下优先级裁决（除非新 ADR 明确推翻）：

1. **Private Deploy / 安全合规**（不可妥协的底线）
2. **Agent First**（保持可恢复的状态机语义）
3. **MCP Native / Model Independent**（可扩展与可替换）
4. **Knowledge Evolution**（长期价值）
5. **Docs-Driven**（过程约束；紧急热修可后补文档，但必须设期限）

---

## 架构演进对照

| 旧范式（拒绝） | ResearchOS 范式（坚持） |
|----------------|-------------------------|
| Search → Download → Embedding → RAG → LLM → PDF | Planner → Research → ETL → KG+Vector → Analysis → Reviewer → Report |
| n8n 作为业务大脑 | Python/LangGraph + MCP；n8n 可选外围 |
| 单次向量检索 | Hybrid RAG（Graph + Vector + Fulltext） |
| 厂商 SDK 直调 | LiteLLM Gateway |

详见 [竞争格局](./02-competitive-landscape.md) 与 [ADR-0005](../adr/0005-n8n-orchestration-boundary.md)。
