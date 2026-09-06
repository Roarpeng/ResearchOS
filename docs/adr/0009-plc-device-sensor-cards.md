# ADR-0009: Q1 Device/Sensor Cards（交接：硬件/传感器含义）

## Status

Accepted

## Context

工程师接手工程的第一问是：**每块硬件 / 每个传感器是干什么的？** 然后才是运行逻辑（Q2）和如何改（Q3 / HITL）。

已有事实来源：

- Openness ingest：`Tag` / `TagTable` / `HardwareDevice` / `HmiDevice`（`agents/plc/tia/ir.py`）
- Knowledge Graph：`Tag` 节点带 `address` / `comment` / `data_type`；`READS` / `WRITES`；`Device` 节点
- Knowledge Canvas：块选中后展开 IO 子图，但没有「含义状态」也没有工程师批注

约束：

- 日路径是 Gateway PLC jobs + Knowledge Canvas，**不是** LangGraph Research TaskState
- 角色是 **cited field narrator**：有注释就引用，没有就标未知。**禁止编造工艺含义**
- 不与 M1 export-status、Q2 运行逻辑、Q3 影响分析 / SCL 回写抢同一批大文件

## Decision

1. 新增 **Device/Sensor Card** 派生模型（不改 PLC-IR dataclass）。卡片至少包含：
   - `address`, `symbol_name`, `comment`, `io_type`（DI/DO/AI/AO/M/DB/CONSTANT/UNKNOWN）
   - `used_by`（哪些块 / 网络 READS 或 WRITES）
   - 可选 `hmi_texts`、`hardware`
   - `meaning_status` ∈ `cited` | `annotated` | `meaning_unconfirmed`
   - `meaning_text` / `meaning_source`
2. 含义解析优先级：**工程师批注 > 标签注释 > 非空 HMI 文本 > 空**。解析器哨兵注释（如 PlcConstant 的 `"constant"`）**不算**工艺含义。
3. 注释与 HMI 文本都缺失时：`meaning_status=meaning_unconfirmed` 且 `meaning_text=""`，UI 明确写「不会编造」。
4. API（additive）：
   - `GET /api/v1/plc/jobs/{id}/device-cards`
   - `GET /api/v1/plc/jobs/{id}/device-cards/{kind}/{name}`
   - `PUT|DELETE .../annotation`
   - `GET /api/v1/plc/jobs/{id}/brief` — **必须**含 `sections.device_sensor_summary`（M2 消费面）
5. 实现放在 `gateway/app/services/plc/device_cards.py` 与 `project_brief.py`。Facade 只 re-export。
6. 最小 UI：工作台「传感器」页 + 画布选中 tag 时的卡片。不把每个 Tag 永久铺进星系（避免淹没块依赖图）。

Schema 名：

| 文档 | 值 |
|------|-----|
| Card | `researchos.device_sensor_card.v1` |
| Brief | `researchos.project_brief.v1` |
| Brief section | `researchos.brief.device_sensor_summary.v1` |

## Acceptance

- [x] 电机 fixture：`StartCmd` 引用「HMI start pushbutton」，`io_type=DI`
- [x] Openness surface：`StartCmd` 无注释 → `meaning_unconfirmed`，不把符号名填进 `meaning_text`
- [x] 批注覆盖引用注释；清除批注后回到 cited
- [x] Brief 含 `device_sensor_summary`，含 `unconfirmed_ids` / `gaps`
- [x] 传感器页可打开卡片，约 30 秒内看到「测什么 / 谁用 / 未知」

## Remaining gaps

- 标签地址与机架/槽位的电气映射未做（避免臆造 Device↔Tag 边）
- 已折叠 `TagTable.Symbol` 访问名为同一符号；跨表重名仍可能拆成两张卡
- HMI 像素文案 / 多语言优先文化未解析；仅结构 `linked_tags` + 可选 comment
- Brief UI 仍是 stub（本切片只保证 API 段）
- 聊天「这个传感器做什么」未改 `chat_router`（避免与 Q2 抢路由）
- 作业存储仍是内存；批注重启即丢（与现有 plc_jobs 一致）

## Consequences

### Positive

- 交接第一问有稳定契约，M2 无需解析整张 KG
- 未知被显式建模，降低幻觉

### Negative / Cost

- 卡片是派生视图，ingest 后 HMI 需 export package 或 `hmi_index`
- Canvas 仍以块为中心，传感器要进「传感器」页或点 IO 子图

## Alternatives Considered

| Alternative | Conclusion |
|-------------|------------|
| 把工艺含义 LLM 补全进 comment | 否决：违反 narrator 隐喻 |
| 把每个 Tag 做成永久 Canvas 节点 | 否决：星系不可读；保留 ephemeral overlay |
| 扩展 `engineer_understanding` 存批注 | 部分采用：批注单独 `device_card_annotations`，避免和角色访谈打架 |
