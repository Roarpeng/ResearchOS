# 07 — 引用溯源（Citation Provenance）

## 目标

保证 Agent 产出的事实性陈述可以回溯到具体证据位置。ResearchOS 将 citation 视为检索结果的一等公民，而不是写作阶段事后拼接的装饰。

每条进入 Context Bundle 的 passage **必须**携带 provenance：

| 字段 | 含义 |
|------|------|
| `source` | 人类可读来源名（文件名、站点名、专利号等） |
| `page` | 页码或幻灯片序号（适用时） |
| `paragraph` | 段落下标或块序（适用时） |
| `url` | 可点击原文链接（适用时） |
| `time` | 证据时间（文档日期 / 抓取时间 / 评论时间） |
| `score` | 融合或通道相关性分数 |

## 为何强制 Provenance

1. **工业与专利场景**需要可审计依据。  
2. **评测窗口**依赖 `time` 判断是否过期。  
3. **调试检索**依赖 `source` / `page` 快速定位解析错误。  
4. **Writer / UI** 据此渲染脚注、悬停预览与「打开原件」。

无 provenance 的文本不得标记为 `citable=true`。

## 数据流：从入库到脚注

```
Parse IR (page, paragraph, url)
        │
        ▼
Semantic Chunk 元数据固化
        │
        ▼
Qdrant payload / OpenSearch fields / Neo4j REFERENCES 属性
        │
        ▼
Hybrid Retrieval passage.citation
        │
        ▼
Agent evidence[] / Writer footnotes
        │
        ▼
Report export（Typst/Pandoc）参考文献或脚注
```

关键规则：**citation 字段在 chunk 创建时写入**；检索阶段只读取与透传，不允许模型「发明」页码。

## Citation 对象规范

```json
{
  "citation_id": "cite_...",
  "chunk_id": "chk_...",
  "source": "rs200-manual.pdf",
  "page": 12,
  "paragraph": 3,
  "url": null,
  "time": "2025-11-02T00:00:00Z",
  "score": 0.81,
  "section_type": "parameter",
  "object_key": "ws/.../raw/doc_.../original.pdf",
  "quote": "额定扭矩: 12 Nm",
  "locator_extra": {
    "slide": null,
    "bbox": null,
    "table_id": "t_3"
  }
}
```

### 字段完备性规则

| 来源类型 | 最低必备 |
|----------|----------|
| PDF / PPTX | `source` + (`page` 或 slide) + `time` + `score` |
| HTML / 网页 | `source` + `url` + `time` + `score` |
| 纯文本上传 | `source` + `paragraph`（或字符偏移）+ `time` + `score` |
| 专利 | `source`（专利号）+ `page`（若 PDF）或 `url` + `time` |

`paragraph` 在网页场景可用 DOM 路径或块 id 替代，放入 `locator_extra`。

## Score 语义

- `score` 默认取融合分；若需分通道展示，使用 `scores: {vector, bm25, graph, fused}`。  
- UI 可显示为相关性百分比，但导出报告应保留原始数值或归一化说明。  
- `score` **不是**事实置信度；事实置信度可另用 `confidence`（抽取阶段）。

## 与图谱 REFERENCES

图上证据边应对齐同一套字段：

```cypher
(e:Entity)-[:REFERENCES {
  chunk_id, page, paragraph, url, time, score, source
}]->(c:Chunk)
```

从图路径进入 Bundle 的 chunk，同样生成 `citation` 对象，`score` 可来自 `graph_score` 映射。

## Writer Agent 使用约定

1. 每个事实句绑定 ≥1 个 `citation_id`。  
2. 多证据冲突时并列引用并在正文提示冲突，禁止静默挑一。  
3. HyDE 假想文、模型先验、无检索支持的推理 → 标记为 `uncited` / `speculation`，不得伪造成脚注。  
4. 窗口外 Review 若被用户强制使用，脚注必须显示 `time`。

## 报告导出

Typst / Pandoc 导出时映射为：

- 脚注：`source, p.page, §paragraph` 或 URL  
- 参考文献表：按 `source` + `time` 聚合  
- 可选附录：chunk 短引用（quote）

详见 [`../mcp/06-report-export-tools.md`](../mcp/06-report-export-tools.md)。

## UI 行为建议

1. 行内脚标点击 → 侧栏展示 quote、页预览、打开 MinIO / URL。  
2. 无 `page` 有 `url` → 外链打开并高亮（若 crawl 存了附件）。  
3. 展示 `score` 仅调试模式默认开启，正式报告可隐藏数值。

## 质量门禁

| 检查 | 阈值建议 |
|------|----------|
| Bundle 内 `citable` passages 缺必备字段 | 0 |
| 最终报告事实句 citation 覆盖率 | ≥ 95%（研究模式可配） |
| 断链（object_key / url 404） | 告警并降级展示 |
| page 超出文档页数 | 入库 Verify 失败 |

## 反模式

1. 只存 `doc_id` 不存页码。  
2. 用 LLM「猜测」页码补全空字段。  
3. 把检索 `score` 当成实验测量置信度写进结论。  
4. 合并 chunk 时丢弃 locator。  
5. 导出报告剥离脚注只留散文。

## 隐私与权限

- citation 中的 `url` / `source` 仍受 workspace ACL 约束。  
- 导出前按权限剥离不可见附件的深链，改为「内部文档 ID」。  
- 详见 [`../mcp/07-tool-security-and-permissions.md`](../mcp/07-tool-security-and-permissions.md)。
