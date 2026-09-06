# Scientific Domain Spec(论文域规范)— PaperHelp 并入 ResearchOS 的可移植设计

> 目标目录:ResearchOS `scientific/`(顶层 Python 域包)+ `frontend/` 编辑器活对象(ADR-0011)。
> 决策与红线见 ADR-0010;工具契约见 ADR-0012。克隆后此规范即为 `scientific/` 的实现蓝本。

## 1. 定位与边界

- **做**:期刊化写作垂直域的「编排 + 检索证据 + 起草中间态(Markdown/JSON)+ 核验 + 图规划」;
- **不做**:期刊排版/编辑器交互(前端活对象,不搬进 Python);不承诺零幻觉;不做多人实时协同(首版)。

## 2. 建议包布局(ResearchOS/scientific/)

```text
scientific/
├── __init__.py
├── manuscript/          # 论文任务状态机(复用层,注册到 runtime graph)
│   ├── stages.py        # outline→evidence→figure_plan→drafting→review→journalize→exported
│   ├── prompts.py       # 域提示词(查表不生成/生成必有源/冲突并列/人在环)
│   └── release_gate.py  # 放行闸:引用 100% DOI 可解析 + AI 使用声明
├── provenance/          # 论断↔chunk↔来源 记录(schemas/provenance.json 见 scientific-port)
│   ├── record.py
│   └── verify.py        # 幽灵引用扫描(调 mcp-scholar)
├── journal_styles/      # 期刊模板(数据驱动 JSON,CSS/Typst 双渲染)
│   ├── template.journal.json
│   ├── plant-physiology.json     # 起步样例(值需对官方指南核验)
│   ├── crop-journal.json
│   └── icsa-cn.json              # 作物学报(中文)占位
└── figure/              # 图规范(作物学)dpi≥300、字号、双栏宽 → 对接 mcp-plot 与 Figure Studio
```

## 3. 论文域状态机与 runtime 映射

| 域阶段 | 内容 | runtime 承载 | 产物/事件 |
|---|---|---|---|
| outline | 大纲生成 | Planner + HITL | `plan` 事件;用户编辑器审批 |
| evidence | Vault+Scholar 检索/证据 | Research + knowledge | `evidence[]`,`citations[]` |
| figure_plan | 原图/数据→图规划 | Analysis | figure 清单 ↔ Figure Studio |
| drafting | 逐节起草(仅锚定资料) | Writer | Markdown 中间态 + provenance |
| review | 覆盖度/矛盾/引用/声明 | Reviewer | 阻断报告 |
| journalize | 模板渲染 | Writer + Report | CSS/Typst |
| exported | PDF/投稿包 + 归档 | Report/export | PDF/ZIP + vault_refs |

TaskState 复用 `goal / plan / evidence / citations / result`;新增域字段放入独立命名空间
(如 `state["domain"]={"kind":"manuscript","stage":...}`),不改 runtime 核心字段名。

## 4. Provenance 记录(最小可用)

每条论断记录:claim_id → text → source_id + chunk_ids + locator(页码)→ quote → doi?(外部文献)
→ confidence → verified → artifact_id(编辑器段落/Figure)→ model/prompt_hash → created_at。
持久化:PostgreSQL(Postgres 表 proposals 见下),随任务与 .paper 导出可携带。JSON Schema 见
`scientific-port/schemas/provenance.json`。

建议表(postgres,克隆后并入既有 metadata 库):
```sql
CREATE TABLE IF NOT EXISTS manuscript_provenance (
  id UUID PRIMARY KEY,
  task_id UUID NOT NULL,
  claim_id TEXT NOT NULL,
  claim_text TEXT NOT NULL,
  source_id TEXT,
  chunk_ids JSONB,
  locator TEXT,
  quote TEXT,
  doi TEXT,
  confidence TEXT,
  verified BOOLEAN NOT NULL DEFAULT FALSE,
  artifact_id TEXT,
  model TEXT,
  prompt_hash TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## 5. Reviewer 域规则(阻断式)

1. 关键论断无 provenance → 阻断;
2. 矛盾证据必须并列呈现,不自动调和 → 提示;
3. 行内引用必须可解析(调 mcp-scholar),幽灵引用率>0 → 阻断放行;
4. 外链/通用知识引用未标注 → 阻断;
5. 导出附 AI 使用声明草稿。

## 6. 验收映射(R 里程碑 ↔ PaperHelp v3.0 M0–M3)

| ResearchOS 里程碑 | 对应 | 验收 |
|---|---|---|
| R1 知识底座 | v3.0 M0 | 真实文件夹文本解析 ≥90%;中英 top-10 命中 ≥80%;问答引用 100% 可回溯 |
| R2 论文纵切 | v3.0 M1 | 新论文 ≤2h 结构完整初稿;引用 100% 可解析;每段可溯源 |
| R3 图与数据闭环 | v3.0 M2 | CSV → 期刊风格图 ≤30min(含人工复核),脚本可复现 |
| R4 习惯与小组 | v3.0 M3 | 快捕→入库 ≤5s;连续使用留存;小组评估 |

## 7. 期刊模板目录(起步,值需核验)

Plant Physiology · Crop Journal · Field Crops Research · Theoretical and Applied Genetics ·
Journal of Integrative Plant Biology · 作物学报/中国农业科学(中文)。模板字段见
`scientific-port/journal_styles/template.journal.json`。

## 8. 风险注记

- 模板样式值来自记忆,并入后须对照期刊官方 Author Guidelines 核验(风险低但必须走);
- 中文期刊样式(字号/图表/文献格式)差异大,首批仅模板壳;
- provenance 表结构为草案,并入时按既有 metadata 规范(SQLAlchemy 或迁移工具)对齐。
