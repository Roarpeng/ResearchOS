# ADR-0002: 工具层 — MCP-Native Tools

## Status

Accepted

## Context

深度研究依赖大量外部能力：Web/学术搜索、浏览器阅读、GitHub、文档解析、知识图谱读写、对象存储、报告渲染等。

若每个 Agent 直接调用 SDK / HTTP API：

- 凭证与权限散落
- 工具 schema 不一致，Prompt 难维护
- 无法形成可替换的工具生态
- 难做统一审计、限流与沙箱

业界出现 **Model Context Protocol (MCP)** 作为 LLM/Agent 工具与资源的开放协议，契合 ResearchOS「可扩展研究 OS」定位。

## Decision

ResearchOS **工具层以 MCP 为原生协议（MCP-Native）**：

1. 所有外部能力以 **MCP Server** 暴露为 Tools / Resources。
2. Agent Runtime 通过 MCP Client 发现与调用工具；Agent 代码依赖工具契约而非具体实现。
3. 首批 MCP 域（示例）：
   - `search-router` — 多源搜索路由（ADR-0007）
   - `browser` — 页面读取
   - `documents` — 解析与入库触发
   - `knowledge-graph` — Neo4j 读写查询
   - `vector-store` — Qdrant 检索/upsert
   - `repo` — GitHub/Git 只读分析
   - `report` — Markdown/Typst 渲染
4. 工具调用必须可审计：task_id、tool_name、args hash、latency、error。
5. 权限模型：按部署策略授予 Server 级/ Tool 级 ACL；默认拒绝高危写操作。

过渡期允许薄适配层（把现有 Python 函数 wrap 成 MCP Tool），但**新集成禁止长期旁路**。

## Consequences

### 正面

- 工具可独立版本化、独立部署、多语言实现。
- 与设计原则「MCP Native」一致，便于开源贡献者扩展。
- 统一观测与配额（Tool Budget）。
- 未来可兼容其他 MCP 客户端（不仅限 ResearchOS Runtime）。

### 负面 / 成本

- 多一层协议与进程模型，本地开发需 Compose 或进程编排。
- MCP Server 质量参差，需要契约测试与金丝雀工具集。
- 部分低延迟内部调用需谨慎避免不必要的序列化开销（可同进程 MCP 或受控 in-proc bridge，但契约仍按 MCP schema）。

### 强制约束

- Agent 内禁止直接嵌入第三方 API SDK 作为生产工具路径（模型网关 LiteLLM 除外，见 ADR-0004）。
- 密钥只存在于 MCP Server / Secret 后端，不进入 Prompt。

## Alternatives Considered

| 方案 | 结论 |
|------|------|
| LangChain Tools 作为唯一标准 | 生态可用，但偏框架绑定；MCP 更利于跨运行时与外部贡献 |
| OpenAPI 工具自动导入 | 适合补齐企业 API，可作为 MCP Server 的生成来源，而非顶层协议 |
| 纯插件 Python 包（import tools） | 耦合部署与权限，难沙箱化 |
| n8n 节点当工具层 | 否决为 Agent 主路径；n8n 仅外围，见 ADR-0005 |
