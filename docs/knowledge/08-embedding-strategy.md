# 08 — Embedding 策略

## 目标

为语义分块选择、切换与版本化 Embedding 模型，在效果、成本、隐私与本地可运行性之间取得可运营的默认策略。

## 推荐优先级

在线质量优先顺序（从高到低）：

1. **Voyage**（优先选用的托管高质量 embedding）  
2. **OpenAI `text-embedding-3-large`**  
3. **BGE-M3**  
4. **Nomic**

**本地 / 私有部署默认：BGE-M3**

该默认保证无外网密钥时仍可完成 GraphRAG 闭环；当环境配置了更高优先级提供商密钥时，可按优先级自动上移，但必须遵守「一 collection 一模型」规则。

## 选型对照

| 模型 | 部署形态 | 优势 | 代价 / 风险 | 适用 |
|------|----------|------|-------------|------|
| Voyage | 云 API | 检索效果强、迭代快 | 出网、成本、供应商依赖 | 效果优先的 SaaS / 联网环境 |
| OpenAI text-embedding-3-large | 云 API | 生态成熟、稳定 | 出网、成本、数据策略 | 已统一 OpenAI 账单的团队 |
| BGE-M3 | 本地或自托管 | 多语、长文本、可私有 | 需 GPU/CPU 容量与运维 | **默认本地**、政企内网 |
| Nomic | 本地 / API | 开源友好、易集成 | 效果通常低于上列前列 | 轻量本地备选、实验 |

## 配置模型

逻辑配置例：

```yaml
embedding:
  policy: prefer_highest_available
  priority:
    - voyage
    - openai_text_embedding_3_large
    - bge_m3
    - nomic
  local_default: bge_m3
  require_local: false   # true 时锁定 BGE-M3/Nomic，忽略云优先级
  providers:
    voyage:
      model: voyage-3-large   # 示例名，以实际开通为准
      dim: 1024
    openai_text_embedding_3_large:
      model: text-embedding-3-large
      dim: 3072
    bge_m3:
      model: BAAI/bge-m3
      dim: 1024
      device: cuda
    nomic:
      model: nomic-embed-text
      dim: 768
```

`require_local=true` 用于空气间隙或合规场景，此时优先级列表中的云模型不可选。

## Collection 与版本纪律

1. **同一 Qdrant collection 内所有点必须同一 `embed_model` + 同一维度。**  
2. 切换模型 = 新建 collection（或新命名空间）+ 全量 / 分批 re-embed，不能把不同模型向量混布。  
3. PostgreSQL `documents.embed_model` / `embed_version` 记录每文档所用模型；检索路由选择匹配 collection。  
4. 双跑期可保留 `collection_bge` 与 `collection_voyage`，由配置决定读写主集合。

命名建议：

```text
chunks_{workspace}_{model_slug}_{dim}
```

例如：`chunks_wsdemo_bge_m3_1024`。

## 入库时行为

```
Chunk text
  → 可选前缀（section_type / 型号提示，短前缀）
  → Embed(model)
  → Upsert Qdrant(point_id=chunk_id, vector, payload)
```

建议：

- 对 `parameter` / `specification` 可加短前缀如 `[parameter][RS-200]`，提升过滤后的语义区分；前缀策略变更视为模型版本变更的一部分。  
- 批量 embed，控制 RPM / 并发；失败写入重试队列。  
- 空文本跳过并告警。

## 查询时行为

1. 解析当前 workspace 的 **主 embedding 配置**。  
2. 用**同一模型**编码 query 或 HyDE 假想文。  
3. 禁止用模型 A 查 collection B。  
4. 若配置切换中，读请求钉在 `primary_collection`；写请求写 `primary`，异步回填 `secondary`。

## HyDE 与模型

HyDE 只改变「被 embed 的字符串」，不改变模型选择逻辑。假想文与 chunk 必须共享同一 embedding 空间（见 [06-hyde-and-metadata-filters.md](./06-hyde-and-metadata-filters.md)）。

## 多语言

- 工业文档常中英混排：**BGE-M3** 作为本地默认具有多语优势。  
- 纯英文语料且已有 Voyage/OpenAI 时，可按优先级上移。  
- 语言字段进入 payload，便于分析，一般不做强制分 collection。

## 成本与质量运营

| 手段 | 说明 |
|------|------|
| 抽样评测集 | 规格 / 对比 / 评测三类 query 的 Recall@K |
| 模型切换门槛 | 新模型在评测集增益稳定后再切 primary |
| 缓存 | 相同 `content_hash` 不重复 embed |
| 降维 | 仅当存储压力极大且评测可接受时考虑；优先换产品化压缩而非随意 PCA |

## 安全与合规

1. `require_local` 时禁止把 chunk 文本发往云 embedding。  
2. 云调用记录审计（时间、doc_id、字节数），不记录完整敏感正文到普通日志。  
3. 密钥仅存在于 Gateway / worker 密钥库，不进仓库。  
4. 与 MCP 权限模型一致：无 `vector.upsert` 权限的 Agent 不可批量改写向量。

## 故障降级

| 主模型失败 | 行为 |
|------------|------|
| 瞬时错误 | 重试；查询侧可短暂返回 BM25+Graph only |
| 持续不可用 | 若存在已建好的本地 BGE collection，切换 `primary` 到本地并告警 |
| 维度不匹配误配置 | 启动时自检失败，拒绝服务写入 |

## 验收清单

1. 干净环境无云密钥时，BGE-M3 可完成 embed + 检索。  
2. 配置 Voyage 密钥后，新 workspace 可按优先级创建 Voyage collection。  
3. 错误地将 OpenAI 查询打到 BGE collection 会被路由层拒绝。  
4. Re-embed 任务可追踪进度，旧 collection 可只读保留。  
5. 文档 `embed_model` 与 point payload 一致。

## 相关文档

- 混合检索：[05-hybrid-retrieval.md](./05-hybrid-retrieval.md)  
- 入库：[01-ingestion-pipeline.md](./01-ingestion-pipeline.md)  
- MCP 向量工具：[../mcp/05-knowledge-tools.md](../mcp/05-knowledge-tools.md)
