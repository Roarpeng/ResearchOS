# 03 — 浏览器与爬取（Browser and Crawl）

## 目标

在搜索命中之后获取**可信正文与结构化页面信息**，为解析入库与引用溯源提供原始 HTML / 主内容 / 快照。

两个互补能力：

| 能力 | 工具前缀 | 适用 |
|------|----------|------|
| **Crawl** | `crawl.*` | 单页或有限深度抓取、主内容提取、批量 URL |
| **Browser** | `browser.*` | 需 JS 渲染、登录态（受控）、点击展开 FAQ / 评论 |

默认优先 Crawl；失败或检测到强 SPA 再升级 Browser，以控制成本。

## Crawl 工具

### `crawl.fetch`

获取单个 URL 的规范化结果。

**输入：**

```json
{
  "url": "https://example.com/products/rs-200",
  "extract": "main",
  "timeout_ms": 20000,
  "store_snapshot": true
}
```

**输出：**

```json
{
  "ok": true,
  "url": "https://example.com/products/rs-200",
  "final_url": "https://example.com/products/rs-200",
  "status_code": 200,
  "title": "...",
  "content_text": "...",
  "content_html_ref": "minio://.../snapshots/....html",
  "fetched_at": "2026-08-02T01:00:00Z",
  "language": "zh",
  "links": [],
  "diagnostics": {"extractor": "readability_like"}
}
```

`content_html_ref` / 快照写入 MinIO，供 Parser（HTML → Unstructured）与审计；避免在 tool 响应中塞完整巨型 HTML。

### `crawl.fetch_many`

有限并发抓取 URL 列表；硬性 `max_urls`（如 20/调用）。部分失败时返回 per-item status。

### `crawl.site`（可选、高权限）

有限深度站点爬取：`max_depth`、`max_pages`、同主域约束。必须默认关闭或需 `crawl:site` 权限。

## Browser 工具

基于无头浏览器（Playwright 类）的受控自动化。

| 工具 | 说明 |
|------|------|
| `browser.open` | 打开 URL，返回可访问的 `session_id` |
| `browser.snapshot` | 无障碍树 / 精简 DOM 文本快照 |
| `browser.click` / `browser.type` | 有限交互（选择器白名单或由快照引用） |
| `browser.extract_main` | 提取主内容文本 |
| `browser.close` | 结束会话 |

约束：

1. 会话 TTL 短（如 5–15 分钟）。  
2. 禁止任意代码执行与下载可执行文件。  
3. 默认无持久登录；企业 SSO 需单独安全方案，不在默认文档启用。  
4. 并发浏览器数有全局上限。

## 主内容提取策略

1. 去导航 / 页脚 / 广告模板。  
2. 保留标题、正文、表格 HTML。  
3. FAQ 折叠：Browser 点击展开后再提取。  
4. Review 区：识别评论容器，标记后续 `section_type=review` 友好 HTML。  
5. 提取失败则保留原始 HTML 快照并返回 warning。

## 与知识入库衔接

```
crawl/browser 成功
  → documents.register + MinIO snapshot
  → parser.parse (html → Unstructured)
  → semantic chunk → embed / kg / bm25
```

`fetched_at` 写入 chunk `timestamp`（若页面无明确发布时间），供近期窗口与 citation `time` 使用。

## robots 与礼貌策略

1. 遵守组织配置的 robots 策略（可配置 `ignore_robots=false` 默认）。  
2. 同主机速率限制与并发限制。  
3. 尊重 `Retry-After`。  
4. 用户显式提供的上传文件不受 robots 限制。

## 错误处理

| 错误 | 处理 |
|------|------|
| HTTP 403/401 | 返回明确码；可建议换源而非盲重试 |
| 超时 | 一次重试；再失败升级 browser 或放弃 |
| 证书错误 | 默认失败；禁止默认关闭 TLS 校验 |
| 重定向出允许域 | 截断并 warning |
| 验证码 / 反bot | `blocked_by_antibot`，不循环暴力破解 |

## 权限

| 权限 | 能力 |
|------|------|
| `crawl:fetch` | 单页 / 小批量 |
| `crawl:site` | 站点爬取 |
| `browser:interactive` | 打开与交互 |
| `browser:admin` | 调整 TTL、并发、调试截图 |

截图若启用，仅存 MinIO 并按 workspace ACL 控制。

## 安全

详见 [07-tool-security-and-permissions.md](./07-tool-security-and-permissions.md)。要点：

- SSRF 防护：封锁链路本地地址、云元数据 IP、非 http(s) scheme。  
- Egress allowlist / denylist。  
- 响应体大小上限。  
- 工具输出给模型前做 HTML 消毒摘要。

## 验收

1. 静态文档页 `crawl.fetch` 得到可读 `content_text`。  
2. 强 JS 页在 browser 路径下可提取 FAQ。  
3. 快照可被 parser HTML 路由消费。  
4. 内网 IP 目标被 SSRF 规则拒绝。  
5. citation 可使用 `url` + `time=fetched_at`。
