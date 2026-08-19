# Industrial extension guide (Phase 5)

This package provides Engineering Copilot **connectors** (read-only catalogs), a TIA
Openness **export adapter**, and Decision Memo templates.

**TIA write-back is not in this folder.** Official Openness mutate APIs
(`Blocks.Import`, `GenerateBlocksFromSource`, `GenerateSourceFromBlocks`,
`Projects.Retrieve`, `ICompilable.Compile`, `Project.Archive`) live in the
Windows HostGateway C# host:

- CLI / MCP: `tools/industrial-mcp/tia-openness/` (`TiaOpenness.Server`)
- Python wrappers: `agents/plc/tia/openness_cli.py`, `agents/plc/tia/writeback.py`

Linux Docker **stages** XML/SCL only; compile-gated `.zap` archive requires that
Windows host. Device download (`plc.program.download`) stays not-implemented.

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

**Preferred (you provide `.apxx`, ResearchOS does the rest):**

```powershell
researchos-tia-cli --project "C:\Projects\MyLine.ap19" --result-dir .\ResearchOS_PLC_Result --json-summary
```

Requires TIA Portal + Openness on this machine (auto-runs `industrial/tia_adapter/ExportProject.ps1`).

Output package:

```
ResearchOS_PLC_Result/
  converted_scl/          # generated .scl
  plc_ir/project.json
  knowledge_graph/graph.json
  reports/analysis.md
  reports/conversion_report.json
```

**Offline-only (already exported SimaticML):**

```powershell
researchos-tia-cli --exports "C:\Export\MyLine" --result-dir .\ResearchOS_PLC_Result
```

**Agent / UI:** `mode=industrial` + `tia_export_dir` / `RESEARCHOS_TIA_PROJECT` pointing at `.apxx` or export folder.

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
