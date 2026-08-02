# ADR 索引 / Architecture Decision Records

本目录记录 ResearchOS 的关键架构决策。格式统一为：

```markdown
# ADR-NNNN: Title
## Status
## Context
## Decision
## Consequences
## Alternatives Considered
```

## 状态约定

| Status | 含义 |
|--------|------|
| Proposed | 讨论中，尚未约束实现 |
| Accepted | 已采纳，实现应对齐 |
| Deprecated | 被新 ADR 取代，仅历史参考 |
| Superseded by ADR-XXXX | 明确指出继任决策 |

## 决策列表

| ID | 标题 | Status | 文件 |
|----|------|--------|------|
| 0001 | Agent Runtime 选型：LangGraph | Accepted | [0001-agent-runtime-langgraph.md](./0001-agent-runtime-langgraph.md) |
| 0002 | 工具层：MCP-Native | Accepted | [0002-mcp-native-tools.md](./0002-mcp-native-tools.md) |
| 0003 | 知识检索：Hybrid GraphRAG | Accepted | [0003-hybrid-graphrag.md](./0003-hybrid-graphrag.md) |
| 0004 | 模型网关：LiteLLM | Accepted | [0004-model-gateway-litellm.md](./0004-model-gateway-litellm.md) |
| 0005 | n8n 编排边界（非核心 Runtime） | Accepted | [0005-n8n-orchestration-boundary.md](./0005-n8n-orchestration-boundary.md) |
| 0006 | 报告管线：Markdown → Typst/Pandoc | Accepted | [0006-report-pipeline-markdown-typst.md](./0006-report-pipeline-markdown-typst.md) |
| 0007 | 搜索路由器：MCP Search Router | Accepted | [0007-search-router-mcp.md](./0007-search-router-mcp.md) |

## 如何新增 ADR

1. 复制上一编号，文件名 `NNNN-kebab-title.md`。
2. 填写 Context（问题与约束）、Decision（明确选择）、Consequences（正负影响）、Alternatives。
3. 更新本索引表格与 [`docs/README.md`](../README.md)。
4. 若推翻旧决策，将旧 ADR 标为 `Superseded by ADR-XXXX`。

## 阅读顺序（新成员）

1. [0005 n8n 边界](./0005-n8n-orchestration-boundary.md) — 先建立「什么不是核心」的共识  
2. [0001 LangGraph](./0001-agent-runtime-langgraph.md)  
3. [0002 MCP](./0002-mcp-native-tools.md) → [0007 Search Router](./0007-search-router-mcp.md)  
4. [0003 Hybrid GraphRAG](./0003-hybrid-graphrag.md)  
5. [0004 LiteLLM](./0004-model-gateway-litellm.md)  
6. [0006 Report Pipeline](./0006-report-pipeline-markdown-typst.md)  
