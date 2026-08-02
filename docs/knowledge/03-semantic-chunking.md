# 03 — 语义分块（Semantic Chunking）

## 目标

按文档**语义结构**切分检索单元，使每个 chunk 对应一个可独立理解的信息单元（规格条目、参数块、表格、FAQ 对、评测段落等），而不是固定长度的 500-token 窗口。

固定 token 切块仅允许作为**最后兜底**，且必须打上 `section_type=fallback_window` 与告警，不得成为默认成功路径的静默行为。

## 为何拒绝默认固定 500-token

| 固定窗口问题 | 语义分块对策 |
|--------------|--------------|
| 表格被切断，BM25/抽取失效 | `table` 整表或按逻辑行组保留 |
| 规格名与数值拆到两块 | `specification` / `parameter` 同块 |
| FAQ 问答分离 | `faq` 以 Q+A 为原子 |
| Review 情感句被截断 | `review` 按条或按段落完整保留 |
| Citation 页码错位 | 块边界对齐 Parse IR 的 page/paragraph |

## Section 类型

| `section_type` | 中文 | 典型来源 IR block | 检索角色 |
|----------------|------|-------------------|----------|
| `title` | 标题 | `heading` level 1–2 | 主题定位、目录感 |
| `specification` | 规格 | 规格章节段落、关键规格表 | 产品能力断言 |
| `parameter` | 参数 | 参数列表、键值行 | 精确数值 / 单位 |
| `table` | 表格 | `table` | 结构化对比、多列参数 |
| `faq` | FAQ | `faq_q`+`faq_a` | 问题型查询 |
| `review` | 评测/评论 | `review_body`、评测章节 | 体验、痛点、HyDE |
| `news` | 新闻（可选扩展） | 新闻正文块 | 时效事件 |
| `narrative` | 叙述（可选） | 普通段落 | 背景说明 |
| `fallback_window` | 兜底窗 | 无法识别结构时 | 降质召回 |

主设计要求覆盖的六类：**标题 / 规格 / 参数 / 表格 / FAQ / Review**。

## 分块算法

### 1. 结构树构建

从 Parse IR 的 headings 重建层级树；无 heading 的 HTML/PPT 用 slide 或启发式标题。

### 2. 节类型分类

对每个节点 / 连续 block 序列打标签，信号来源：

1. 标题关键词：`规格`、`参数`、`Parameters`、`Specifications`、`FAQ`、`评测`、`用户评价` 等。
2. IR block type（`table`、`faq_q`、`review_body`）。
3. 版式启发：键值列、两列表格偏 `parameter`。
4. 可选轻量分类器（本地模型）——不得替代结构信号。

### 3. 原子切分规则

| 类型 | 原子单位 | 合并 / 拆分规则 |
|------|----------|-----------------|
| `title` | 单个标题 + 可选短导语 | 导语过长则标题单独成块 |
| `specification` | 同一小节内连贯规格叙述 | 超长按子标题再切；保持完整句 |
| `parameter` | 一组相关键值（建议 5–30 行） | 单行过碎则合并；变更主题则新块 |
| `table` | 整表优先 | 超大表按行窗切，行窗带表头重复 |
| `faq` | 一问一答 | 禁止把多个无关 Q 拼一块 |
| `review` | 单条评论或同一作者连续段 | 保留评分 / 时间到 metadata |

### 4. 软长度约束（非固定主策略）

语义完整优先。仅当单块极端过长时二次切分：

- 软上限目标：约 200–800 tokens（按模型 tokenizer 估算），**按句 / 按行**边界切。
- 硬上限：防止单点撑爆上下文（实现可配，如 1200–1500 tokens）。
- 二次切分后子块共享同一 `section_type` 与父 `section_id`。

### 5. 重叠策略

默认**不做**滑窗重叠。仅在 `narrative` / `fallback_window` 允许少量句级重叠；规格与表格默认零重叠，以免数值重复计分。

## Chunk 元数据模型

```json
{
  "chunk_id": "chk_...",
  "doc_id": "doc_...",
  "workspace_id": "ws_...",
  "section_type": "parameter",
  "section_path": ["产品手册", "电气参数", "额定值"],
  "text": "额定扭矩: 12 Nm\n峰值扭矩: 36 Nm",
  "model": ["RS-200"],
  "source_file": "rs200-manual.pdf",
  "object_key": "ws/.../raw/doc_.../original.pdf",
  "url": null,
  "page": 12,
  "paragraph": 3,
  "timestamp": "2025-11-02T00:00:00Z",
  "language": "zh",
  "parser": "docling",
  "token_estimate": 42,
  "parent_section_id": "sec_...",
  "content_hash": "sha256:..."
}
```

字段要求：

- `model`、`source_file`、`timestamp` 必须可被检索过滤（见 [06-hyde-and-metadata-filters.md](./06-hyde-and-metadata-filters.md)）。
- `page` / `paragraph` / `url` / `time` 服务 citation（见 [07-citation-provenance.md](./07-citation-provenance.md)）。

## 与实体抽取的衔接

优先从下列类型抽取实体：

1. `parameter` / `specification` / `table` → Product、Feature、Specification  
2. `review` → PainPoint、Review、Feature（抱怨点）  
3. `faq` → Feature、PainPoint  
4. `title` 通常不单独抽取，只提供上下文路径  

抽取器接收 chunk 时附带 `section_path`，提高型号归属准确率。

## 质量门禁

入库 Verify 抽样检查：

1. `section_type` 分布不能 100% 为 `fallback_window`（除非文档本身无结构）。
2. 表格样例：表头不得丢失。
3. FAQ 样例：Q 与 A 同块。
4. 每个 chunk `text` 去空白后长度 > 0。
5. citation 关键字段缺失率低于阈值。

## 反模式

1. 全局 `text.split(every=500 tokens)` 作为主路径。  
2. 把整本手册单块塞进向量库。  
3. 丢掉 page/slide 编号。  
4. 将页眉页脚与正文混为一个 `specification` 块。  
5. 无结构时静默成功且不打 `fallback_window` 标记。

## 实现位置

- 库代码建议：`knowledge/chunking/`  
- MCP：解析后由 ingestion worker 调用；也可暴露 `parser.chunk` 调试接口（见 [`../mcp/04-parser-tools.md`](../mcp/04-parser-tools.md)）。
