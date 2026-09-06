# 交接助手产品简报 v1.1

> 路径：Gateway PLC + Knowledge Canvas 日常交接（**不是** LangGraph Research `TaskState`）。  
> 隐喻：**带引用的现场解说员** — 只解说已导出/已索引的现场，不编造未看见的逻辑。

## 工程师三问

交接叙事固定为三问，默认提示写在 Brief 与对话芯片上，**不启用自动 SCL 写回**。

| 编号 | 问题 | 期望答案 |
|------|------|----------|
| Q1 | 这个工程有哪些硬件和传感器？ | 设备/传感器钩子 + 引用；没有证据则标 **未导出/未索引** |
| Q2 | 主循环怎么跑？入口和顶层调用链是什么？ | 主 OB/入口一行 + CALLS；块名 + 网络/行 + 源片段 |
| Q3 | 如果要改这段逻辑，HITL 该怎么确认调整？ | 理解 → 显式「优化SCL」预览 → 人工「确认反写」；禁止自动写回 |

## 里程碑

| 切片 | 目标 | 本仓库落点 |
|------|------|------------|
| **M1** 结构可信 | 导出状态、设备卡 | 其他 agent。Brief **消费** `export_status` / `device_cards`；缺失则用占位枚举降级 |
| **M2** 分层 Project Brief | 1–3 分钟可读的结构简报 | `GET /api/v1/plc/jobs/{id}/brief`；ingest 在 SCL 全文翻译前落结构快照 |
| **M3** 带引用问答 | 禁止无引用臆造 | 节点对话 / 理解路径强制 `block + locator + snippet`；缺口回 **未导出/未索引** |

## 非目标（本切片不做）

- 自动优化 SCL / 确认反写扩面
- Volta
- 改写 Research LangGraph
- 把交接状态塞进 Research `TaskState`

## M2 — Layered Brief

### 结构先行

1. Openness / 已有 XML 抽出块清单、接口、注释、硬件后即可 `brief_ready`。
2. 程序体（SCL/LAD）进入 `body_pull_queue`，**不阻塞首份 Brief**。
3. Job `ingest_phase`：`queued → skeleton/structure → bodies_queued → ready`。

### Brief 字段

- `purpose`：一行工程目的
- `main_ob` / `main_entry`：主入口
- `block_counts_by_status`：按导出状态计数（M1 枚举，否则由 flags 推导）
- `top_level_calls`：入口顶层调用
- `device_sensor_summary`：设备/传感器钩子（M1 卡优先，否则硬件 XML / I 区启发式）
- `run_logic_entry`：一行主运行逻辑入口
- `export_gaps`：未导出/保护/仅接口/未索引列表
- `engineer_prompts`：三问模板
- `timing.assumptions`：时效假设

### 时效假设（最佳努力）

- 中等工程：约 200–800 块。
- 目标：打开后 **1–3 分钟**可读 Brief（取决于 Openness `list_blocks` 或已导出 XML，**不含**全文 LAD→SCL）。
- 全文翻译可到十几分钟以上；Brief 不得等它。

### UI

画布顶部紧凑卡 +「简报」页。对话在无节点范围时出示三问芯片。

## M3 — 引用契约

每条理解/节点问答必须带：

1. **块名**
2. **定位符**：网络号或 SCL 行（最佳可得）
3. **源片段**

结构化字段：`block` / `locator`（兼容 `network`）/ `snippet` / `source_status`。

若块或程序体未导出、未建索引：回答必须出现 **`未导出/未索引`**，只陈述接口与已验证 CALLS/I/O，**禁止编造内部逻辑**。

可选廉价预计算：`block_stubs`（职责一行 / I/O / 调用者），不做深翻译。

## 协调

- M1 导出状态、Q1 设备卡由其他 agent 拥有。本切片 API 可加、UI 宜薄。
- 若 M1 状态尚未写入，Brief 接受占位枚举：`converted | parsed | protected | interface_only | unknown | not_exported | not_indexed`。

## 已知缺口

- 真实 Openness「只 list、后按需 export_block」的懒下载队列仍是编排钩子；当前实现是结构快照后继续既有全文转换，但 Brief 已可提前读。
- 传感器列表为启发式，不是 IO 表权威源；等 M1 设备卡后应替换钩子数据。
- 节点卡片路径的引用主要靠收尾契约补齐，LLM 长文仍须人工核对 snippet。
- 未把 Brief 写入离线 ZIP 报告（可后续加 `reports/project_brief.json`）。
