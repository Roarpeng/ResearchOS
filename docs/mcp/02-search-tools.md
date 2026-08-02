# 02 — 搜索工具（Search Tools）

## 目标

提供统一的 `search()`（对外工具名建议 `search.query`）门面，将查询路由到 **SearXNG / Tavily / Brave** 等提供商，返回归一化的搜索命中列表，供 Research Agent 决定是否继续 `crawl` / `browser`。

搜索工具只负责**发现 URL 与摘要**，不保证正文完整；正文获取见 [03-browser-and-crawl.md](./03-browser-and-crawl.md)。

## 为何需要路由器

| 提供商 | 特点 | 适合 |
|--------|------|------|
| **SearXNG** | 自托管元搜索、隐私友好、可聚合多引擎 | 私有部署默认、内网可出站场景 |
| **Tavily** | 面向 Agent 的检索 API、结果干净 | 托管质量优先、快速原型 |
| **Brave** | 独立索引、商业 API 成熟 | 补充多样性、地区/合规选项 |

路由器按策略选择主提供商，并在失败时降级，避免 Agent 绑定单一 SDK。

## 工具：`search.query`

### 输入

```json
{
  "query": "RS-200 absolute encoder IP rating",
  "limit": 8,
  "provider": "auto",
  "lang": "zh-CN",
  "freshness": "year",
  "include_domains": [],
  "exclude_domains": [],
  "safesearch": "moderate"
}
```

| 字段 | 说明 |
|------|------|
| `query` | 检索字符串 |
| `limit` | 返回条数上限 |
| `provider` | `auto` \| `searxng` \| `tavily` \| `brave` |
| `lang` | 语言偏好 |
| `freshness` | 可选时效：`day`/`week`/`month`/`year`/`any` |
| `include_domains` / `exclude_domains` | 域名约束 |
| `safesearch` | 安全检索级别 |

### 输出（归一化）

```json
{
  "ok": true,
  "provider_used": "searxng",
  "results": [
    {
      "title": "...",
      "url": "https://...",
      "snippet": "...",
      "score": 0.72,
      "published_at": null,
      "source": "manufacturer",
      "raw_provider": "searxng"
    }
  ],
  "diagnostics": {
    "tried": ["searxng"],
    "latency_ms": 410
  }
}
```

所有提供商结果映射到同一 `results[]` schema；禁止把提供商特有大 JSON 直接灌进模型上下文（可留 `raw_ref` 存对象存储供调试）。

## 路由策略

```text
provider == explicit → 只用该提供商
provider == auto:
  if require_local_search or prefer_privacy:
    primary = searxng
  else if tavily_key:
    primary = tavily
  else if brave_key:
    primary = brave
  else:
    primary = searxng
  on failure → next available in fallback_order
```

建议 `fallback_order`：

1. 配置的 primary  
2. SearXNG（若可达）  
3. Brave  
4. Tavily  

（顺序可按部署调整；关键是**可配置**且**可观测**。）

## 辅助工具

| 工具 | 用途 |
|------|------|
| `search.providers` | 列出可用提供商与健康状态 |
| `search.query_multi` | 并行打多个提供商并 RRF 合并（成本高，可选） |

`search.query_multi` 默认不对普通 Research Agent 开放，或限制 QPS。

## 与后续工具的衔接

典型链路：

```
search.query → 选 URL → crawl.fetch / browser.open → documents.store → parser.parse → knowledge ingest
```

Agent 提示词应说明：snippet 不足以下结论；需要事实时必须拉取正文并进入 citation 流程。

## 错误与降级

| 情况 | 行为 |
|------|------|
| 主提供商超时 | 自动 fallback，`diagnostics.tried` 记录 |
| 全部失败 | `ok=false`，`dependency_unavailable` |
| 域名被 egress 策略拦截 | 过滤结果或拒绝，见安全文档 |
| 空结果 | `ok=true` 且 `results=[]`，非错误 |

## 权限

- `search:read`：调用 `search.query`  
- `search:admin`：查看 raw、强制 provider、multi  

## 安全注意

1. 不把 API Key 返回给模型。  
2. 对 `query` 做长度限制，防止异常超长提示注入到上游。  
3. 遵守组织 egress allowlist（SearXNG 出站亦同）。  
4. 记录审计：query 哈希或截断文本、provider、结果 URL 主机名。

## 验收

1. 无 Tavily/Brave 密钥时 SearXNG 可单独工作。  
2. 强制 `provider=tavily` 在密钥缺失时返回明确错误而非空挂起。  
3. 归一化字段在三提供商下均可填充 `title/url/snippet`。  
4. Agent 仅绑定门面工具即可完成调研搜索步骤。
