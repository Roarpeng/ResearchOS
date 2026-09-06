# RESEARCHOS-MAP:已核实的仓库结构与集成触点

> 2026-09-06 抓取(Roarpeng/ResearchOS @ main)。用于 R0–R4 落地时的事实基准;克隆后如有出入以仓库为准。
>
> **克隆后勘误(2026-09-06)**:仓库已推进到 HEAD `8abd71f`。**frontend/ 已存在**(npm + Vite 6 + React 19
> 单应用,含 `src/api.ts` 客户端与 workbench/plc 模块),**tools/ 已存在**(documents/knowledge/vector_store/
> knowledge_graph/report/search_router/plc/ros2/github/isaac/cad/browser 等多套 MCP)。故本文「frontend 未落地、
> tools 未落地」的早期表述作废,集成方式见 ADR-0011(向现有 frontend 追加 manuscript 模块)与
> pyproject `[project.scripts]`/hatch packages 注册范式。

## 1. 运行环境(来自 README/ROADMAP quick start)

- Python ≥3.13 + uv(`uv venv .venv --python 3.13 && uv pip install -e ".[dev]"`)
- Gateway:`DEV_AUTO_APPROVE=true .venv/bin/uvicorn gateway.app.main:app --port 8000`
- Runtime(独立进程):`DEV_AUTO_APPROVE=true .venv/bin/researchos-runtime`
- 前端约定:`cd frontend && npm install && npm run dev`(frontend/ 已存在 npm Vite 应用)
- 数据面:`cp deploy/env/.env.example deploy/env/.env && cd deploy/compose && docker compose --env-file ../env/.env up -d`
- 测试:`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -p pytest_asyncio tests/ -q`

## 2. 顶层目录(已核实)

agents/ · deploy/ · docs/ · gateway/ · industrial/ · knowledge/ · runtime/ · scripts/ · tests/
+ pyproject.toml · researchos_shared.py · Start-ResearchOS.cmd · Stop-ResearchOS.cmd · skills-lock.json
(README.md / ROADMAP.md 在根;无 frontend/、无 tools/、无 sdk/ —— 目标布局尚未全部落地)

## 3. Gateway(app = FastAPI)

- 文件:`gateway/app/main.py`、`config.py`、`deps.py`、`middleware/`、`routers/`、`schemas/`、`services/`、`ws/`
- 既有 routers:`auth.py`、`chat.py`、`health.py`、`knowledge.py`(10.8KB)、`plc.py`、`research.py`(7.4KB)、`sessions.py`、`settings.py`
- 既有 schemas 镜像:auth / chat / common / health / knowledge / llm / plc / research / sessions / agent_workspace
- ws:`gateway/app/ws/` → manager.py、research.py、events.py
- 含义:论文域的「检索/问答/任务」可先复用 `knowledge` + `research` + `chat` 路由;
  Manuscript 任务专用路由/字段待克隆后按 research.py 契约扩展(候选 `routers/manuscript.py`)。

## 4. Runtime(researchos_runtime)

- 模块:checkpoint.py · events.py · graph.py(10KB) · mcp_client.py(13.6KB) · server.py(7.8KB) ·
  settings.py · state.py(4.6KB) + `__init__.py`
- 含义:新增论文域图在此注册(graph.py / server.py),MCP 工具经 mcp_client.py 挂接。

## 5. Agents(agents/,registry.py)

- supervisor / planner / research / analysis / reviewer / writer / memory(核心七件)
- 工业扩展:motion / failure / plc(+plc/tia 众多子模块)/ tia_cli.py
- **agents/citation/(node.py 5.8KB)** —— 疑似已有引用处理 Agent,克隆后先确认用途与输出契约
- 含义:论文域按 ADR-0010 在 supervisor 之上注册子工作流;writer/reviewer 复用 + 域规则注入。

## 6. Knowledge(knowledge/)

- 管道:cli.py · pipeline.py · worker.py · documents.py · store.py · persist.py · settings.py ·
  models.py(6.3KB)· embeddings.py · __init__.py
- chunking/semantic.py(10.8KB);extract/entities.py(7.2KB);parsers/router.py(23.9KB)
- retrieval/:bm25.py · filters.py · graph.py(16.4KB)· hybrid.py(12.2KB)· hyde.py · query_understanding.py · vector.py
- 含义:mcp-vault 摄取直接调 documents/parsers + pipeline;中文 BM25 需 CJK 配置(预分词或 n-gram)。
  克隆后确认 models.py 的 citation/source 字段,映射 PaperHelp 需要的 `论断↔chunk↔来源`。

## 7. Deploy 与模型

- deploy/compose/docker-compose.yml(8.2KB)+ docker-compose.hostgateway.yml
- deploy/configs/litellm.yaml(模型网关);deploy/env/.env.example(密钥模板);deploy/optional/n8n(外围)
- 含义:full Compose 数据面 = PostgreSQL/Redis/MinIO/Qdrant/Neo4j/BM25(或 OpenSearch)+ LiteLLM,
  具体服务清单克隆后以 compose 文件为准。

## 8. Docs/ADR(编号已核实)

- docs/:00-Vision ~ 05-Development-Roadmap、README、CONTRIBUTING、core/(00-product-definition …
  03-glossary)、adr/0001–0009、industrial/、runtime/、knowledge/ 等
- ADR 0001–0009 主题:agent-runtime-langgraph / mcp-native-tools / hybrid-graphrag / model-gateway-litellm /
  n8n-orchestration-boundary / report-pipeline-markdown-typst / search-router-mcp /
  plc-gateway-workbench-module-boundaries / plc-device-sensor-cards
- ⇒ 论文域 ADR 自 **0010** 起(drafts 已就绪:0010/0011/0012)

## 9. 集成触点清单(R0–R2 落地增删点)

| 动作 | 位置(ResearchOS) | 备注 |
|---|---|---|
| PaperHelp 历史并入 | `apps/paperhelp/`(git subtree) | 过渡保留,迁移后删除 |
| frontend/ TS workspace | `frontend/`(pnpm+Turbo) | packages: editor/figure/export/db/ui/shared + api-client;apps: 页面 |
| api-client 契约源 | `gateway/app/routers/{knowledge,research,chat,sessions,settings,auth}.py` | 先读路由后生成 TS 客户端 |
| 论文域 ADR | `docs/adr/0010/0011/0012` | drafts 在 PaperHelp docs/merge/adr-drafts/ |
| ROADMAP Phase 6 | `ROADMAP.md` + `docs/05-Development-Roadmap.md` | 草案在 PaperHelp docs/merge/ |
| 论文域包 | `scientific/`(新,顶层) | journal_styles/provenance/manuscript |
| Manuscript 路由 | `gateway/app/routers/manuscript.py` + `schemas/manuscript.py` | 复用 ws/research 事件 |
| 论文 Agent | `agents/manuscript/`(新)或 supervisor 注册 | 复用 writer/reviewer |
| MCP 工具 | `tools/mcp-vault/`、`tools/mcp-scholar/`、`tools/mcp-plot/`(新) | 接 runtime mcp_client |
| 作物学 schema | `knowledge/schemas/scientific/`(新) | genotype/treatment/measurement/… |
| 测试 | `tests/`(contract/unit) | 按既有 conftest 模式 |

## 10. 克隆后优先核实项(R0 开头)

1. pyproject 完整依赖与 entry-points(console scripts)
2. gateway research/knowledge router 的实际 endpoint 与 schemas(api-client 契约)
3. agents/citation 的真实职责;agents/registry 的注册方式
4. runtime graph 节点命名与 server 启动参数(state/events)
5. docker-compose 服务清单与 .env.example 键
6. tests 目录结构与 conftest(测试基线)
7. 是否已有 lint/format/CI 约定(ruff? mypy?)
