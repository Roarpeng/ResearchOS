# n8n — PERIPHERAL ONLY

> **ADR-0005 / ResearchOS contract:** n8n is **not** the research runtime.
> Do **not** put Agent planning, reflection loops, RAG pipelines, or model
> orchestration inside n8n workflows.

## Allowed uses

1. **Schedule** — Cron / webhook that calls Gateway `POST /api/v1/research/tasks`
2. **Notify** — On task completed/failed, push email / IM / Slack
3. Temporary glue to legacy IT systems (with a sunset plan)

## Forbidden

- Multi-step research Agent graphs
- Embedding → RAG → report as the “official” research path
- Holding exclusive MCP tool access that Runtime cannot use

## Enable

```bash
cd deploy/compose
docker compose --env-file ../env/.env --profile automation up -d
```

UI: http://localhost:5678

## Sample notify webhook note

When a research task finishes, Gateway/Runtime (or a thin hook) can `POST`
to an n8n webhook. Example payload shape:

```json
{
  "event": "research.task.completed",
  "task_id": "tsk_01H...",
  "status": "completed",
  "workspace_id": "ws_01H...",
  "report_url": "https://example.invalid/reports/...",
  "ts": "2026-08-03T04:00:00Z"
}
```

Create an n8n workflow with a **Webhook** trigger, then a **Slack / Email**
node. Point `N8N_WEBHOOK_URL` / workflow URL at that trigger. Keep research
logic in Gateway → Runtime only.
