# 06 — 报告导出工具（Report Export Tools）

## 目标

将 Writer Agent 产出的结构化研究报告导出为可交付文件（PDF / DOCX / HTML / Markdown 等），引擎优先 **Typst** 与 **Pandoc**，并保留 citation 脚注与附件清单。

导出是副作用操作：生成的对象写入 MinIO，并在 TaskState `artifacts` 登记。

## 工具

| 工具 | 说明 |
|------|------|
| `report.export` | 门面：选引擎与格式，执行导出 |
| `report.preview` | 生成短 HTML/Markdown 预览（可无 PDF） |
| `report.list_templates` | 可用模板（工业调研、专利分析、竞品对比等） |
| `report.validate_citations` | 导出前检查引用完备性 |

## `report.export`

### 输入

```json
{
  "task_id": "task_...",
  "title": "RS-200 竞品与评测综述",
  "format": "pdf",
  "engine": "auto",
  "template": "industrial_research_v1",
  "document": {
    "markdown": "...",
    "sections": [],
    "citations": [],
    "metadata": {
      "authors": ["ResearchOS"],
      "created_at": "2026-08-02T00:00:00Z",
      "workspace_id": "ws_..."
    }
  },
  "options": {
    "embed_footnotes": true,
    "include_bibliography": true,
    "locale": "zh-CN"
  }
}
```

可用 `format`：`pdf`、`docx`、`html`、`markdown`、`typst`（源码产物）。

### 引擎选择

| `engine` | 行为 |
|----------|------|
| `typst` | Markdown/IR → Typst → PDF（版式强、PDF 优先） |
| `pandoc` | Markdown → Pandoc → DOCX/HTML/PDF（需 PDF 引擎时显式配置） |
| `auto` | `pdf` 默认 Typst；`docx`/`html` 默认 Pandoc |

### 输出

```json
{
  "ok": true,
  "artifact_id": "art_...",
  "format": "pdf",
  "engine_used": "typst",
  "object_key": "ws/.../exports/task_.../report.pdf",
  "bytes": 248833,
  "checksum": "sha256:...",
  "citation_stats": {"total": 42, "uncited_claims": 0},
  "warnings": []
}
```

## 内容管道

```
Writer structured doc (Markdown + citations[])
        │
        ▼
report.validate_citations（可强制）
        │
        ▼
Template apply（封面、目录、章节样式）
        │
        ├─ Typst 渲染 ─→ PDF
        └─ Pandoc 转换 ─→ DOCX / HTML / PDF
        │
        ▼
MinIO + artifacts 登记 + 可选 Gateway 下载链
```

## Citation 映射

输入 `citations[]` 必须符合知识层 provenance 字段（source、page、paragraph、url、time、score）。  

导出映射：

| 字段 | Typst / Pandoc |
|------|----------------|
| source + page | 脚注或 `@fig` 类引用 |
| url | 可点击链接（HTML/DOCX）或脚注 URL |
| time | 参考文献年份 / 日期 |
| quote | 可选块引用附录 |

`report.validate_citations` 失败时：

- `on_policy=strict` → 拒绝导出  
- `on_policy=warn` → 导出但封面水印「含未引用断言」  

研究模式默认 `strict`。

## 模板

内置模板至少覆盖：

1. `industrial_research_v1` — 工业技术调研  
2. `competitor_analysis_v1` — 竞品对比  
3. `patent_brief_v1` — 专利速览  
4. `meeting_decision_v1` — 工程决策纪要  

模板只控制版式与章节骨架，不篡改证据正文。

## 权限

| 权限 | 能力 |
|------|------|
| `report:preview` | preview / list_templates / validate |
| `report:export` | 正式导出写 MinIO |
| `report:admin` | 上传自定义模板 |

## 资源与安全

1. 渲染在隔离 worker，CPU/内存/时间限额。  
2. 禁止模板包含任意网络请求（除非显式允许拉字体）。  
3. 用户 Markdown 按安全子集解析，防止注入 Typst/LaTeX 危险原语（allowlist 宏）。  
4. 导出链接带短 TTL 签名 URL。  

## 错误码

`invalid_document`、`citation_incomplete`、`engine_failed`、`template_not_found`、`render_timeout`。

## 验收

1. 含脚注的中文样例经 Typst 导出 PDF 成功。  
2. 同文档经 Pandoc 导出 DOCX 成功。  
3. 缺 citation 在 strict 下被拒绝。  
4. artifact 可在 documents/下载 API 取回且 checksum 一致。  
5. Writer Agent 仅需调用门面 `report.export`。
