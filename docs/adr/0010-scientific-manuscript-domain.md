# ADR-0010: Scientific Manuscript Domain(学术论文垂直域)

Status: Draft(待并入 ResearchOS 后正式化)
Date: 2026-09-06
编号说明:ResearchOS ADR 已存在 0001–0009(其中 0008 = PLC Gateway Workbench Module Boundaries,
0009 = PLC Device Sensor Cards),故论文域相关 ADR 自 **0010** 起编号。
Context: [PaperHelp × ResearchOS 合并蓝图](../scientific/ResearchOS_Integration_Blueprint.md)

## 背景

PaperHelp(Figure-first 科研写作应用 + v3.0「资料记忆 + 论文执行」愿景)合并入 ResearchOS。
用户领域为植物/作物/农业科学;目标 Persona 为单研究者(架构预留小组)。
ResearchOS 产品定义已把「学术/技术文献综述」列为目标场景,但缺少论文写作垂直域的端到端编排与域规则。

## 决策

1. 在 ResearchOS 中新增 **Manuscript Domain(论文域)**:
   - Python 侧:领域包 `scientific/`(journal_styles / provenance / manuscript 状态机复用层),
     在既有 Runtime(Supervisor/Planner/Reviewer/Writer/Memory)之上注册论文子工作流,**不重造 Runtime**;
   - 前端侧:编辑器与 Figure Studio 从 PaperHelp 移植(见 ADR-0011)。
2. 论文域管线(域内固定阶段):
   `规划大纲(HITL 审批)→ 检索/证据(Vault + Scholar)→ 图与数据规划 → 逐节起草(仅锚定本人资料)→
   评审(覆盖度/矛盾/引用)→ 期刊化渲染 → 编辑器活对象或导出 PDF/投稿包 → 知识回流`
3. 域规则(写入域提示词与 Reviewer 策略,产品红线):
   - 查表不生成:引用元数据仅来自 mcp-scholar(DOI/Crossref/OpenAlex/Semantic Scholar),LLM 永不编引用;
   - 生成必有源:论断↔chunk↔来源 三级溯源,产出携带证据链;
   - 冲突并列不调和:矛盾证据显式列出,由用户裁决;
   - 人在环裁决:系统负责读过/查过/起草过,用户负责裁决/实验/署名;
   - 幽灵引用=0 才放行:导出前逐条行内引用必须可解析到真实 DOI;
   - 产物即活对象:草稿落编辑器、图落 Figure Studio,非一次性 Markdown 黑箱。
4. 知识层扩展:新增作物学实体 schema(genotype / treatment / measurement / result / figure /
   claim / experiment_design),与既有 Hybrid GraphRAG 共用管线,仅加 schema 与抽取提示。
5. 数据面策略(用户已确认):full Compose 数据面优先(PostgreSQL/Qdrant/Neo4j/MinIO/Redis),
   ResearchOS 标准部署;本地轻量模式作为后续增强(ADR-0003 存储抽象层之上),不阻塞首版。

## 明确不做(Non-Goals)

- 不在 Python 侧重做期刊排版/编辑器交互(排版是前端活对象);
- 不承诺零幻觉;通过 Reviewer + 引用核验 + 置信度降低风险;
- 不把论文域逻辑放进 n8n;
- 首版不做多人协作写作实时协同(保留既有 workspace_id 权限基座即可)。

## Consequences

- ROADMAP 增加 Phase 6 — Scientific Manuscript(见 ../scientific/merge/ROADMAP-phase6-proposal.md);
- 新增 MCP:mcp-scholar、mcp-plot、mcp-vault(见 ADR-0012);
- Gateway 复用既有 routers(research/knowledge/chat)+ 可选新增 manuscript 专属路由(见 RESEARCHOS-MAP);
- 论文域验收标准沿用 PaperHelp v3.0 M0–M3 并映射到 ResearchOS 组件。
