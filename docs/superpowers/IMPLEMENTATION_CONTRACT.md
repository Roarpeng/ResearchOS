# ResearchOS Implementation Contract (MVP)

Agents MUST follow this contract. Target: Phase 1–5 MVP scaffolding meeting roadmap exit criteria at demo quality.

## Layout (do not invent new top-level dirs)

Per `docs/03-Repository-Layout.md`:
- `deploy/` — compose, env, litellm config, optional n8n
- `gateway/` — FastAPI only
- `runtime/` — LangGraph graph, checkpoint, MCP client, events
- `agents/` — supervisor, planner, research, analysis, reviewer, writer, memory, citation
- `tools/` — MCP servers (hello, search_router, browser, documents, knowledge_graph, vector_store, report, repo)
- `knowledge/` — parsers, chunking, extract, retrieval, worker, cli
- `frontend/` — minimal React/Vite research console (or static MVP)
- `industrial/` — connectors + Decision Memo templates
- `tests/` — unit + contract
- `scripts/` — smoke / bootstrap

## Non-negotiables

1. n8n is peripheral only (profile `automation`); never put research logic there.
2. Agents must NOT import vendor search SDKs; tools go through MCP.
3. Model calls go through LiteLLM (`LITELLM_BASE_URL`), not direct OpenAI SDK in agents.
4. Citations are first-class; result claims should reference citation ids when present.
5. Structured logs include `task_id` / `request_id` where applicable.
6. Secrets only via env / `.env.example` placeholders — never real keys.
7. Python 3.11+, type hints, pydantic v2.
8. Do NOT commit unless asked. Do NOT edit other agents' owned paths.
9. Reply in Chinese summary when done; code/comments in English.

## Shared settings

Use env vars from `docs/deployment/02-configuration.md`. Prefer `pydantic-settings`.

## MVP quality bar

- Runnable locally with mocks when infra down.
- Compose brings up data plane + litellm + gateway skeleton.
- One end-to-end path: create task → plan → (demo tools) → markdown result with citations.
- Unit tests for core state reducers, supervisor routing, RRF fusion, health endpoints.
