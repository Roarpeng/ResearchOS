# ADR-0006: 报告管线 — Markdown → Typst / Pandoc

## Status

Accepted

## Context

深度研究的交付物通常是**可分享、可存档、可审计**的技术报告或决策备忘录，而非聊天窗口中的一次性回复。

需求：

- 中间态便于 Agent 编辑与 Git/Diff 审查
- 支持 Citation、图表、表格、版本元数据
- 可输出 PDF（主）与 DOCX（企标常见）
- 私有部署下不依赖闭源排版 SaaS
- Writer Agent 与渲染器解耦

常见选项：直接让 LLM 吐 PDF（不可控）、仅 HTML 打印、LaTeX 重、纯 Pandoc、Typst 等。

## Decision

采用 **两阶段报告管线**：

```text
Claims + Outline + Citations
        │
        ▼
  Writer Agent → Markdown (Canonical Intermediate)
        │
        ├─► Typst  → PDF   （默认高质量排版）
        └─► Pandoc → DOCX / 其它 （兼容办公流程）
```

细节：

1. **Markdown 为规范中间态（Canonical）**：含 YAML front matter（标题、作者、任务 ID、模型、时间、置信度摘要）。
2. **Citation 语法稳定**：例如 `[^cite:source_id]` 或项目约定的扩展，渲染前解析为参考文献表。
3. **Typst** 作为 PDF 主渲染引擎；提供官方模板（技术调研 / 竞品对比 / Decision Memo）。
4. **Pandoc** 负责 DOCX 等格式，或作为 Markdown 预处理工具。
5. 渲染通过 **MCP `report` Server** 暴露（对齐 ADR-0002），输入 Markdown artifact，输出对象存储路径（MinIO）。
6. Reviewer **在 Markdown 阶段**放行；渲染失败不得静默丢弃 Citation。

## Consequences

### 正面

- Agent 易于迭代正文；人类可用普通编辑器审阅中间态。
- PDF 排版质量可控，模板可版本化。
- 满足私有部署；制品可溯源到 task_id。

### 负面 / 成本

- 需维护 Typst 模板与 Citation 转换器。
- 复杂浮动图表布局可能需要模板约束 Writer 输出结构。
- Pandoc/Typst 二进制进入部署镜像，镜像体积上升。

### 强制约束

- 禁止以「LLM 直接生成 PDF 二进制」作为主路径。
- 正式发布的报告必须能回溯到 Markdown artifact 与 Citation 列表。

## Alternatives Considered

| 方案 | 结论 |
|------|------|
| 纯 LaTeX | 强大但工具链重、Agent 出错面大 |
| 仅 Pandoc → PDF | 可用，但复杂中文/工程模板体验弱于 Typst 路线 |
| HTML/CSS → PDF（Prince/Chrome） | 可行备选；默认不选以减少浏览器依赖 |
| Notion/Google Docs API | 违背私有化默认，可作可选导出 |
| n8n 拼装邮件 PDF | 否决为主路径（ADR-0005） |
