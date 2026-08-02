# 02 — 文档解析路由（Document Parser Router）

## 目标

按文件类型把原始对象路由到最合适的解析器，产出统一的中间表示（IR），供语义分块与实体抽取使用。

ResearchOS **不**使用单一万能 parser；路由表是一等配置。

## 路由表（默认）

| 条件 | Parser | 原因 |
|------|--------|------|
| `application/pdf` / `.pdf` | **Docling** | 版面、表格、页码、多栏工业 PDF 表现好 |
| `application/vnd.*presentation*` / `.pptx` / `.ppt` | **MarkItDown** | 幻灯片转 Markdown 结构清晰、工程成本低 |
| `text/html` / `.html` / `.htm` / 爬取正文 | **Unstructured** | HTML 噪声清洗、元素分类成熟 |
| `.md` / `.txt` | Pass-through / 轻量结构化 | 已是文本 |
| `.docx` 等未列类型 | Unstructured（兜底） | 覆盖长尾 |
| 未知 MIME | 魔数嗅探 → 再路由；失败则 `quarantined` | 安全与可观测 |

路由伪代码：

```text
function route(doc):
  mime, ext = sniff(doc)
  if ext in {pdf} or mime == application/pdf:
    return Docling
  if ext in {pptx, ppt} or mime is presentation:
    return MarkItDown
  if ext in {html, htm} or mime == text/html:
    return Unstructured
  if ext in {md, txt}:
    return TextPassThrough
  return UnstructuredFallback
```

## 统一中间表示（Parse IR）

所有 parser 适配器输出同一 IR，避免上游绑定具体库：

```json
{
  "doc_id": "doc_...",
  "parser": {"name": "docling", "version": "x.y.z"},
  "language": "zh",
  "pages": [
    {
      "page": 1,
      "blocks": [
        {
          "id": "b1",
          "type": "heading",
          "level": 1,
          "text": "产品规格",
          "bbox": [0, 0, 0, 0],
          "paragraph": 1
        },
        {
          "id": "b2",
          "type": "table",
          "text": "| 参数 | 值 |\n| 扭矩 | 12Nm |",
          "table": {
            "headers": ["参数", "值"],
            "rows": [["扭矩", "12Nm"]]
          },
          "paragraph": 2
        }
      ]
    }
  ],
  "markdown": "# 产品规格\n\n| 参数 | 值 |\n|---|---|\n| 扭矩 | 12Nm |\n",
  "warnings": []
}
```

### Block `type` 枚举（建议）

`heading` | `paragraph` | `list` | `table` | `code` | `figure_caption` | `footer` | `header` | `slide_title` | `slide_body` | `faq_q` | `faq_a` | `review_body` | `unknown`

IR 中的 `type` 是分块 `section_type` 映射的主要输入。

## Docling（PDF）

**适用**：说明书、白皮书、论文、专利 PDF、扫描件（若启用 OCR）。

**关注点**：

1. 保留 **page** 号 — citation 强依赖。
2. 表格尽量结构化，而不是拍成一张图描述。
3. 页眉页脚降权或标记 `header`/`footer`，默认不进入高价值 chunk。
4. 多栏顺序按阅读序重建。
5. OCR 开启时在 IR `warnings` 记录置信度。

**输出适配**：Docling 原生树 → ResearchOS Parse IR；同时落盘 `document.md` 与 `document.json` 到 MinIO `parsed/`。

## MarkItDown（PPTX）

**适用**：路演、产品介绍、方案汇报。

**关注点**：

1. 一页幻灯片 → 一个逻辑 page（`page` = slide index）。
2. 标题与正文分离为 `slide_title` / `slide_body`。
3. 嵌入图片以 caption / alt 文本进入 IR；二进制仍在 MinIO。
4. 动画与备注：备注文本可选并入，标记 `notes=true`。

PPTX 常见「规格表截图」质量差时，应在 `warnings` 提示，供抽取阶段降低置信度。

## Unstructured（HTML）

**适用**：官网产品页、新闻、博客、文档站、爬虫正文。

**关注点**：

1. 去导航、广告、页脚模板噪声。
2. 保留规范 `url` 与抓取 `timestamp`。
3. FAQ 折叠面板尽量识别为 `faq_q` / `faq_a`。
4. Review / 评论区可按容器 CSS / 结构启发式标为 `review_body`。
5. 主内容空时返回失败，触发 crawl 策略重试或 `quarantined`。

## 路由配置与覆盖

配置文件示例（逻辑）：

```yaml
parser_router:
  rules:
    - match: { extensions: [pdf] }
      parser: docling
    - match: { extensions: [pptx, ppt] }
      parser: markitdown
    - match: { extensions: [html, htm] }
      parser: unstructured
  fallback: unstructured
  overrides:
    # 特定数据源强制某 parser
    - match: { source_prefix: "patents/" }
      parser: docling
```

运营可对单 `doc_id` 强制 `reparse_with`，生成新 `parsed/v{n}`，不覆盖旧 IR。

## 错误处理

| 情况 | 行为 |
|------|------|
| Parser 超时 | 一次指数退避重试；再失败标记阶段失败 |
| 空文本（可提取字符 < 阈值） | 对 PDF 尝试 OCR 路径；仍空则 `quarantined` |
| 加密 PDF | `failed` + 错误码 `encrypted_pdf` |
| 超大文件 | 流式 / 分页解析；超硬限额拒绝 |
| 兜底 parser 也失败 | `quarantined`，保留原始 MinIO 对象供人工 |

## 安全

1. 解析在隔离 worker 中运行，限制 CPU / 内存 / 时间。
2. 不执行 HTML 中的脚本；不跟随解析期外链下载（外链抓取走 crawl 工具链）。
3. MIME 嗅探与扩展名不一致时写 warning，并按魔数路由。
4. 病毒扫描钩子（可选）在 Parse 前；不通过则 `quarantined`。

## MCP 暴露

Parser 能力通过 MCP `parser` 工具暴露，例如：

- `parser.parse_document(doc_id | object_key | bytes_ref)`
- `parser.detect_type(...)`
- `parser.list_parsers()`

Agent 不应硬编码 Docling API；只调用 MCP，便于替换实现。详见 [`../mcp/04-parser-tools.md`](../mcp/04-parser-tools.md)。

## 验收标准

1. 样例 PDF 保留页码且表格可结构化。
2. 样例 PPTX 幻灯片序号完整进入 IR。
3. 样例 HTML 去除导航噪声后主内容完整。
4. 三种 parser 输出均可被同一 Chunker 消费。
5. 路由错误可观测（metrics：`parser_route_total{parser=...}`）。
