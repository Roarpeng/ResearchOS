# ResearchOS MCP 工具层

ResearchOS 以 **MCP Native** 为原则：Agent 不直连外部 SaaS SDK 或数据库驱动，一律通过 MCP Tool Server 访问能力。这样运行时可审计、可换实现、可按角色授权。

本目录描述 MCP 总体架构、各工具域契约，以及安全与权限模型。

## 工具域一览

| 域 | 文档 | 能力摘要 |
|----|------|----------|
| 架构总览 | [01-mcp-architecture.md](./01-mcp-architecture.md) | Server 拓扑、会话、与 LangGraph 集成 |
| 搜索 | [02-search-tools.md](./02-search-tools.md) | `search()` 路由：SearXNG / Tavily / Brave |
| 浏览与爬取 | [03-browser-and-crawl.md](./03-browser-and-crawl.md) | 浏览器自动化、站点爬取、正文提取 |
| 解析 | [04-parser-tools.md](./04-parser-tools.md) | Parser Router 暴露为 MCP |
| 知识 | [05-knowledge-tools.md](./05-knowledge-tools.md) | KG 读写、向量 upsert/search、混合检索 |
| 报告导出 | [06-report-export-tools.md](./06-report-export-tools.md) | Typst / Pandoc 导出 |
| 安全权限 | [07-tool-security-and-permissions.md](./07-tool-security-and-permissions.md) | ACL、出网、密钥、审计 |
| （交叉）Documents / GitHub | 见架构与知识文档 | 对象存储文档、仓库资料 |

## 设计原则

1. **能力工具化**：搜索、爬取、解析、图谱、向量、导出皆为工具。  
2. **路由器优先**：例如 `search()` 统一入口，背后可切换 SearXNG / Tavily / Brave。  
3. **副作用显式**：写图谱 / upsert 向量 / 导出文件必须在工具 schema 标明 `side_effect`。  
4. **可观测**：每次调用带 `tool_call_id`、耗时、错误码，进入 Runtime trace。  
5. **最小权限**：Planner 可看只读检索；仅 Memory / 授权 Research 可写 KG。

## 与知识层关系

MCP 是知识层的**唯一推荐写入/查询入口**。底层 Neo4j、Qdrant、OpenSearch、MinIO 的连接配置留在 tool server，不暴露给提示词。

知识设计详见 [`../knowledge/README.md`](../knowledge/README.md)。

## 阅读顺序

1. [01-mcp-architecture.md](./01-mcp-architecture.md)  
2. 按需阅读 `02`–`06` 各域  
3. 上线前必读 [07-tool-security-and-permissions.md](./07-tool-security-and-permissions.md)
