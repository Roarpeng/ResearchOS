# 07 — 工具安全与权限（Tool Security and Permissions）

## 目标

为 MCP 工具层定义**认证、授权、出网控制、副作用治理与审计**要求，防止 Agent 越权读写知识库、造成 SSRF / 数据泄漏，或滥用高成本提供商。

安全模型与 ResearchOS 私有部署原则一致：默认最小权限，显式授予写与外网能力。

## 信任边界

```
User → Gateway (AuthN) → Runtime (AuthZ / allowlist)
                         → MCP Client
                         → Tool Server (再校验 scope + workspace)
                         → Provider / DB / MinIO
```

要点：

1. **Gateway** 负责用户身份与会话。  
2. **Runtime** 按 Agent 角色绑定工具 allowlist。  
3. **Tool Server** 不信任模型：再次校验 token、workspace、scope、参数。  
4. 后端密钥只存在于 Tool Server / Secret Store，永不进入 prompt 或 tool 响应。

## 权限 Scope 目录

| Scope | 含义 |
|-------|------|
| `search:read` | 调用搜索 |
| `crawl:fetch` | 单页/小批量爬取 |
| `crawl:site` | 站点级爬取 |
| `browser:interactive` | 无头浏览器交互 |
| `parser:read` / `parser:write` | 检测与解析写入 |
| `documents:read` / `documents:write` | 对象读 / 上传删除 |
| `vector:read` / `vector:write` | 向量检索 / upsert |
| `kg:read` / `kg:write` | 图查询 / 写入 |
| `knowledge:retrieve` | 混合检索门面 |
| `report:preview` / `report:export` | 预览 / 导出 |
| `github:read` / `github:write` | 仓库读 / 受限写 |
| `admin:mcp` | raw Cypher、强制 provider、跨租户调试 |

Scope 绑定到 **Agent 角色 × Workspace 角色（human）** 的交集。

## Agent 默认画像

| Agent | 默认允许 | 默认拒绝 |
|-------|----------|----------|
| Planner | search 只读、knowledge.retrieve | 写库、browser、export |
| Research | search、crawl.fetch、browser、parser、documents.write、retrieve | kg.write / vector.upsert（除非任务授予） |
| Memory | kg.*、vector.*、parser、documents | 外网 search 可关 |
| Writer | retrieve、documents.read、report.* | kg.write、crawl.site |
| Reviewer | retrieve、validate_citations | 一切写与外网 |
| Supervisor | 编排；不直接持有宽泛写权限 | 避免超级工具集 |

任务级可临时提升（经 Human Approve）：例如允许 Research 在本任务 `kg.write`。

## Workspace 隔离

所有知识与文档工具强制 `workspace_id`：

1. 从会话上下文注入，**不允许**模型随意改写为其他租户。  
2. Qdrant / OpenSearch / Neo4j / MinIO 查询一律带 workspace 约束。  
3. 跨 workspace 仅 `admin:mcp` + 审计工单。

## 网络与 SSRF

适用于 `search`（间接触发）、`crawl`、`browser`、部分 `github`：

1. 仅 `http`/`https`。  
2. 拒绝私网、回环、链路本地、云元数据地址（169.254.169.254 等）。  
3. DNS 解析后再次校验 IP（防 DNS rebinding）。  
4. 可选 egress allowlist（域名后缀）。  
5. 最大重定向次数与 host 不变性策略。  
6. 响应体大小上限与超时。

## 副作用分级

| 级别 | 示例 | 控制 |
|------|------|------|
| L0 无副作用 | search、retrieve、kg.query | allowlist 即可 |
| L1 外部只读 | crawl.fetch | SSRF 策略 + 速率限制 |
| L2 状态写入 | vector.upsert、kg.write、documents.upload | scope + 可选人工确认 |
| L3 导出 / 外发 | report.export、github.write | scope + 审计 + TTL 链接 |
| L4 危险管理 | cypher_raw、跨租户 | admin + 双人审批（建议） |

## 速率与配额

按 `workspace_id` + `user_id` + `tool` 计量：

- 搜索 QPS / 日调用  
- crawl 页数 / 日  
- browser 会话分钟  
- embedding token / 日  
- 导出次数 / 日  

超限返回 `provider_rate_limit` 或 `quota_exceeded`。

## 输入消毒

1. JSON Schema 严格校验，拒绝附加未知字段（或剥离）。  
2. Cypher/SQL 仅模板参数绑定。  
3. 选择器 / URL / 文件名长度限制。  
4. Markdown 导出前做危险指令过滤（Typst/LaTeX）。  
5. 工具返回给模型的文本截断与脱敏（密钥、Cookie、Authorization 头）。

## 审计日志

每条工具调用记录：

| 字段 | 说明 |
|------|------|
| `timestamp` | 时间 |
| `actor_user_id` / `agent_name` | 谁发起 |
| `workspace_id` / `task_id` | 上下文 |
| `tool_name` | 工具 |
| `side_effect_level` | L0–L4 |
| `params_digest` | 参数哈希与安全摘要 |
| `status` / `error_code` | 结果 |
| `latency_ms` | 耗时 |
| `artifact_ids` | 若产生对象 |

写操作与导出日志保留期长于只读检索。禁止在日志中存完整文档正文。

## 密钥管理

1. Tavily / Brave / Voyage / OpenAI / GitHub Token 存 Secret Store。  
2. 轮换不影响 Agent 代码。  
3. Tool 响应不得回显密钥或签名查询串。  
4. MinIO 预签名 URL 短 TTL，权限与用户会话绑定。

## Human-in-the-Loop

下列默认建议打断确认：

- 首次在工作区启用 `crawl:site`  
- 批量 `vector.delete` / 文档硬删  
- `github:write`  
- 将知识库内容导出到外部 webhook（若未来支持）  

Runtime 已有 interrupt 能力，与 LangGraph human interrupt 对齐。

## 威胁场景与缓解（摘要）

| 威胁 | 缓解 |
|------|------|
| 提示注入诱使泄漏他租户 | workspace 强制注入 + server 侧校验 |
| 提示注入诱使任意 URL 打内网 | SSRF 防护 |
| 模型要求 raw Cypher 删库 | 默认无工具；admin 双人 |
| 用 HyDE/报告投毒写入假 citation | citation 仅来自索引字段；假想文不可引用 |
| 成本打爆第三方 API | 配额 + provider 路由 + 本地 BGE 默认 |
| 导出夹带机密 | ACL 检查附件；脱敏策略 |

## 上线检查清单

1. 生产关闭 `kg.cypher_raw` 与 `search.query_multi`（或仅 admin）。  
2. 验证跨 workspace 读取被拒绝。  
3. 验证私网 URL crawl 被拒绝。  
4. 验证 Research 角色默认不能 `vector.upsert`。  
5. 审计日志可按 `task_id` 检索完整工具链。  
6. 密钥扫描：仓库与日志无明文 Token。  

## 相关文档

- MCP 架构：[01-mcp-architecture.md](./01-mcp-architecture.md)  
- 知识检索：[05-knowledge-tools.md](./05-knowledge-tools.md)  
- Citation：[../knowledge/07-citation-provenance.md](../knowledge/07-citation-provenance.md)  
- Embedding 合规：[../knowledge/08-embedding-strategy.md](../knowledge/08-embedding-strategy.md)
