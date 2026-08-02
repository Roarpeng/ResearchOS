# 04 — 实体与图谱 Schema

## 目标

定义 ResearchOS 知识图谱的节点类型、关系类型、属性约定与写入幂等规则，使实体抽取结果可在 Neo4j 中稳定合并，并与 Qdrant / OpenSearch 中的 chunk 证据互链。

## 设计原则

1. **证据优先**：任何实体或关系应能通过 `REFERENCES` 回到 chunk / 文档。
2. **幂等合并**：`(label, canonical_key)` 唯一；别名进入 `aliases`。
3. **关系少而稳**：先落地五类核心关系，避免关系类型爆炸。
4. **业务可读**：节点面向工业调研（产品、规格、专利、评测），不是通用 NLP 百科。

## 节点类型（Entities）

### Product

产品或可对比的型号单元。

| 属性 | 说明 |
|------|------|
| `id` | 稳定 ID |
| `canonical_key` | 归一化键，如 `vendor:model` |
| `name` | 显示名 |
| `aliases` | 别名 / 内部代号 |
| `models` | 型号字符串列表 |
| `category` | 品类 |
| `created_at` / `updated_at` | 时间 |

### Feature

可被描述的能力或功能点（未必有数值）。

| 属性 | 说明 |
|------|------|
| `canonical_key` | 如 `feature:absolute_encoder` |
| `name` | 功能名 |
| `description` | 短描述 |
| `aliases` | 同义说法 |

### Specification

可量化或可枚举的规格项（常与数值、单位、条件绑定）。

| 属性 | 说明 |
|------|------|
| `canonical_key` | 如 `spec:rated_torque` |
| `name` | 规格名 |
| `value` | 主值（字符串或数值序列化） |
| `unit` | 单位 |
| `condition` | 测试条件 / 工况 |
| `value_norm` | 可选归一化 SI 值 |

`Specification` 可通过关系挂到 Product；同一规格名在不同产品上是不同节点或同一节点多边——默认 **每产品规格边属性持有值**，节点表示规格定义。

推荐模式：

```text
(:Product)-[:HAS_FEATURE]->(:Feature)
(:Product)-[:HAS_FEATURE {value, unit, condition}]->(:Specification)
```

若实现上将 Specification 作为独立实测节点，必须包含 `product_id` 于 `canonical_key`。

### PainPoint

用户或评测中的痛点 / 缺陷主题。

| 属性 | 说明 |
|------|------|
| `canonical_key` | 主题键 |
| `name` | 痛点标题 |
| `severity` | 严重度启发式 |
| `polarity` | 默认 negative |

### Review

一条评测、评论或测评文档单元。

| 属性 | 说明 |
|------|------|
| `canonical_key` | 如 `review:{doc}:{anchor}` |
| `title` | 可选 |
| `rating` | 可选评分 |
| `timestamp` | **近期窗口过滤关键字段** |
| `source` | 来源站点 / 文件 |
| `language` | 语言 |

### News

新闻或公告事件。

| 属性 | 说明 |
|------|------|
| `canonical_key` | URL 或标题哈希 |
| `title` | 标题 |
| `timestamp` | 发布时间 |
| `url` | 原文 |

### Company

组织 / 厂商。

| 属性 | 说明 |
|------|------|
| `canonical_key` | 如 `company:acme` |
| `name` | 官方名 |
| `aliases` | 别名 |
| `country` | 可选 |

### Patent

专利文献。

| 属性 | 说明 |
|------|------|
| `canonical_key` | 专利号归一化 |
| `title` | 标题 |
| `patent_no` | 公开号 / 授权号 |
| `filing_date` / `publish_date` | 日期 |
| `assignee` | 专利权人文本（同时应链到 Company） |

### 辅助节点（推荐）

| Label | 用途 |
|-------|------|
| `Document` | 文档登记，链到 MinIO |
| `Chunk` | 可选物化，便于图上溯源 |
| `Standard` | 标准号（扩展） |
| `Version` | 产品或文档版本（扩展） |

## 关系类型（Relations）

### HAS_FEATURE

```text
(Product|Company)-[:HAS_FEATURE]->(Feature|Specification)
```

属性：`value`、`unit`、`condition`、`confidence`、`chunk_id`。

语义：主体具备某功能或规格。

### COMPARES

```text
(Product|Feature|Specification)-[:COMPARES]->(Product|Feature|Specification)
```

属性：`aspect`、`verdict`（better/worse/similar/unknown）、`confidence`、`chunk_id`。

语义：文本中出现显式或可解析的对比。

### REFERENCES

```text
(Entity)-[:REFERENCES]->(Chunk|Document|Patent|News|UrlNode)
```

属性：`page`、`paragraph`、`url`、`score`、`chunk_id`。

语义：证据链；**所有关键断言应能走到 REFERENCES**。

### UPDATED_BY

```text
(Product|Document|Specification)-[:UPDATED_BY]->(Document|News|Version)
```

属性：`at`、`change_summary`、`chunk_id`。

语义：新文档 / 版本更新了旧知识。

### PRODUCED_BY

```text
(Product|Patent|News|Review)-[:PRODUCED_BY]->(Company)
```

属性：`role`（manufacturer/assignee/publisher/author_org）、`confidence`。

语义：产出或归属关系。

## 约束与索引（Neo4j）

逻辑约束：

```cypher
CREATE CONSTRAINT product_key IF NOT EXISTS
FOR (n:Product) REQUIRE n.canonical_key IS UNIQUE;

CREATE CONSTRAINT feature_key IF NOT EXISTS
FOR (n:Feature) REQUIRE n.canonical_key IS UNIQUE;

CREATE CONSTRAINT company_key IF NOT EXISTS
FOR (n:Company) REQUIRE n.canonical_key IS UNIQUE;

CREATE CONSTRAINT patent_key IF NOT EXISTS
FOR (n:Patent) REQUIRE n.canonical_key IS UNIQUE;

CREATE CONSTRAINT review_key IF NOT EXISTS
FOR (n:Review) REQUIRE n.canonical_key IS UNIQUE;
```

建议索引：

- `Review(timestamp)`
- `News(timestamp)`
- `Product(name)`
- `Chunk(chunk_id)` / `Document(doc_id)`

## 抽取与写入流程

```
Chunk → Candidate spans → Normalize → MERGE node → MERGE rel → REFERENCES evidence
```

1. **候选**：规则（单位、专利号）+ LLM JSON schema 抽取。  
2. **归一化**：大小写、空白、单位（Nm vs N·m）、公司法律后缀。  
3. **MERGE**：按 `canonical_key`；更新 `aliases`、`updated_at`。  
4. **关系**：低置信度进入待审或仅写属性 `confidence<0.5` 供查询过滤。  
5. **证据**：始终写 `REFERENCES` 到 chunk。

## 示例子图

```text
(Company:Acme)-[:PRODUCED_BY]-(Product:RS-200)
(Product:RS-200)-[:HAS_FEATURE {value:'12', unit:'Nm'}]->(Specification:rated_torque)
(Product:RS-200)-[:COMPARES {aspect:'torque'}]->(Product:RS-100)
(Review:r1)-[:REFERENCES]->(Chunk:chk_9)
(PainPoint:noise)-[:REFERENCES]->(Chunk:chk_9)
(Product:RS-200)-[:UPDATED_BY]->(Document:manual_v3)
(Patent:US123)-[:PRODUCED_BY]->(Company:Acme)
(Patent:US123)-[:REFERENCES]->(Document:patent_pdf)
```

## 查询模式（供检索层）

1. **产品规格**：Product → HAS_FEATURE → Specification，过滤 `name/unit`。  
2. **竞品对比**：双向 COMPARES 或共有 Feature 集合差。  
3. **痛点聚合**：Product ← Review → PainPoint，按 `Review.timestamp` 窗口。  
4. **来源追溯**：任意节点 → REFERENCES → Chunk → Document。  
5. **版本演化**：Product → UPDATED_BY → Document/Version 链。

Cypher 示意（近期痛点）：

```cypher
MATCH (p:Product {canonical_key: $key})<-[:ABOUT]-(r:Review)-[:REFERENCES]->(c:Chunk)
WHERE r.timestamp >= $since
OPTIONAL MATCH (pain:PainPoint)-[:REFERENCES]->(c)
RETURN r, pain, c
ORDER BY r.timestamp DESC
LIMIT 50
```

> `ABOUT` 为可选实现关系；也可用 Review 属性 `product_keys` 或 `(Review)-[:REFERENCES]->(Product)` 表达。实现需在代码与本文保持一种主模式并文档化。

## 与向量 / 全文的对齐

| 图谱 | 向量 payload / BM25 |
|------|---------------------|
| `Product.models` | `model` 过滤字段 |
| `REFERENCES.chunk_id` | Qdrant point id |
| `Review.timestamp` | payload `timestamp` + 近期窗口 |
| 关系路径文本化 | 可选「图叙述」一并 embed |

## 非目标

- 不在 v1 建模完整企业组织架构或通用 Wikidata。  
- 不把整段原文存进 Neo4j 作为主存储（原文在 MinIO + chunk 索引）。  
- 不引入无证据的大量弱关系污染图。
