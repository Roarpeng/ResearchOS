# M1 Trusted Structure — Acceptance

> Engineer-handover slice M1. Daily PLC path is Gateway PLC jobs + Knowledge Canvas
> (not LangGraph Research TaskState). M2 Project Brief and M3 cited Q&A are out of
> scope here. SCL optimize / write-back stay deferred.

## Goal

Openness / structure ingest must produce a **trusted map** of the TIA project:
every exportable unit is present with an explicit status. Silent missing blocks
are a product defect.

Engineer questions this slice unblocks: (1) what hardware / sensors exist,
(2) which program blocks exist and how they call each other. HITL adjust
(question 3) remains M2/M3 + write-back.

## Status vocabulary

Every block / device / tag table / other exportable unit has exactly one of:

| Status | Meaning |
|--------|---------|
| `exported` | Unit is in the inventory and structure was parsed. **Body text may be empty** (Know-how / interface-only). |
| `failed` | Openness or parse attempted and failed (`inconsistent`, `no_license`, `openness_error`, XML parse error). |
| `skipped` | Intentionally not exported or not recognized (`know_how` without XML, `no_export`, `password_protected`, `unrecognized`, empty official category). |
| `pending` | Known (journal / list / CALLS target) but not yet exported. |

API: `GET /api/v1/plc/jobs/{id}` → `structure.units[]` and `blocks[].status`.
UI: coverage strip lists failed (red) / skipped+pending (warning) with **重试导出**.

Retry: `POST /api/v1/plc/jobs/{id}/structure/retry` re-runs Openness/structure
ingest from the same source. Feasible when the job source is still on disk
(export dir, `.zap`, or HostGateway `.apxx`).

## What the map must cover

| Layer | Source (extend existing, do not rewrite) |
|-------|------------------------------------------|
| Device tree | Openness hardware AML / `devices.xml` → `structure.layers.device_tree` + canvas `plc_device` |
| Program block list | Parsed IR + manifest/journal listed units → `blocks` + `layers.program_blocks` |
| Call graph | KG `CALLS` edges; missing callees become `pending` units |
| Interface DBs / tags | DB / UDT / tag tables → `layers.interface_dbs` + `layers.tags` |

## Acceptance (mid-size TIA project)

1. Block list **reconciles with TIA** object tree (names / types). Empty program
   body is acceptable; omitting the block is not.
2. If Openness fails or skips a unit, the unit remains in the inventory with
   `status` + `reason` + `detail`. Coverage strip shows red / warning.
3. `reports/structure.json` is written on the job package.
4. Retry path is visible when any unit is failed / skipped / pending.

Offline fixture used in CI: `tests/fixtures/tia_openness_surface`
(`FB_Vendor` must appear as `skipped` / `know_how`).

## Implementation map

- Builder: `agents/plc/tia/structure.py`
- Journal attach: `simaticml.extract_project` + `extract_stream` (failed journal
  lines are recorded, not dropped)
- Job / API: `gateway/app/services/plc/ingest.py`, `schemas/plc.py`,
  `POST .../structure/retry`
- UI: `frontend/src/plc/CoverageStrip.tsx`, canvas `export_status`
- Blocks-only Openness: `BlockService.ExportAllBlocks` writes `manifest.json`
  with per-listed-unit status

## Remaining gaps (not this slice)

- Live mid-size `.ap19` reconciliation still needs a Windows HostGateway + TIA
  Portal machine; CI uses fixtures.
- Per-unit Openness export (single-block CLI retry) is not implemented; retry
  re-walks the whole project.
- Canvas still caps **exported** extras at 120 (overflow node is shown). Failed /
  skipped units are never dropped for the cap.
- Volta topology, SCL optimize / write-back, and Research-graph PLC path are
  explicitly out of scope (M2/M3 / later).
- HMI / CFC / Safety / OPC UA appear in the inventory when present, but the
  canvas focuses on blocks, devices, DBs, and tags.
