# Industrial extension guide (Phase 5)

This package provides **read-only** Engineering Copilot connectors, a TIA Openness
export adapter, and Decision Memo templates. Real device write paths are intentionally absent.

## Layout

```
industrial/
  connectors/
    ros2_docs.py   # ROS2 docs catalog interface + fake data
    plc_docs.py    # PLC manuals interface + fake data (token-scored search)
    cad_meta.py    # CAD metadata interface + fake data
  tia_adapter/
    ExportProject.ps1   # TIA Portal → SimaticML XML (recursive groups)
    README.md
  templates/
    decision_memo.md
  README.md
```

Related components outside this package:

- `agents/plc/` — PLC Agent (manuals + optional TIA analysis → KG/SCL)
- `agents/plc/tia_cli.py` — offline CLI (`researchos-tia-cli`)
- `tools/plc/server.py` — `mcp-plc` (`plc.manual.*`, `plc.tia.analyze`, writes refused)
- `agents/planner/` — inserts the `plc` step when `workflow=industrial`

## Self-test with your own PLC project

1. Export (requires TIA Portal + Openness):

```powershell
.\industrial\tia_adapter\ExportProject.ps1 `
  -ProjectPath "C:\Projects\MyLine.ap19" `
  -ExportDir "C:\Export\MyLine" `
  -TiaVersion V19
```

2. Offline analyze (no TIA needed after export):

```powershell
researchos-tia-cli --exports "C:\Export\MyLine" --out .\scl_out --kg kg.json --json-summary
```

3. Run industrial agent with the export folder:

```powershell
# Option A — environment
$env:RESEARCHOS_TIA_EXPORTS = "C:\Export\MyLine"
# then create a Gateway task with mode=industrial

# Option B — API field
# POST /api/v1/research/tasks  { "query": "...", "mode": "industrial", "tia_export_dir": "C:\\Export\\MyLine" }

# Option C — Frontend: mode=industrial + “TIA 导出目录”
```

## Connector contract

Each connector exposes:

1. A `Protocol` describing read-only methods (`search`, `get`, list helpers)
2. A `Fake*Connector` backed by an in-memory `FAKE_CATALOG`
3. `as_dict()` helpers for MCP / JSON serialization

Agents and MCP servers should depend on the **Protocol**, not a vendor SDK.

## How to extend

1. Add a new file under `connectors/` with `Protocol` + fake catalog.
2. Register an MCP tool that calls the connector.
3. Whitelist the tool for `mode=industrial` research tasks in Gateway/Runtime.
4. Keep **default read-only**; any write/download-to-device path requires HITL interrupt + ADR.
5. Prefer citing standards in Decision Memo safety sections.

## Safety

- Do not connect these stubs to production PLC/robot endpoints.
- Do not overwrite CAD vault files from agents.
- Simulation / field writes belong behind explicit feature flags and dual approval.
