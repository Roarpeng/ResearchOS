# TIA Openness MCP Server (Milestone 1)

ResearchOS industrial MCP foundation for Siemens **TIA Portal V19** via Openness.

```text
ResearchOS Agent
        |
       MCP
        |
TIA Openness Server   ← this package
        |
TIA Portal V19
```

After Milestone 1, the export XML feeds the existing offline stack:

```text
XML → PLC Parser → PLC-IR → Neo4j → PLC Agent
```

## Tools (v0.1)

| Tool | Purpose |
|------|---------|
| `tia.get_status` | Detect TIA Portal process + Openness PublicAPI availability |
| `tia.open_project` | Open `.ap19` (also `.ap17`/`.ap18`/`.ap20`) via Openness |
| `tia.list_blocks` | List `OB` / `FB` / `FC` / `DB` |
| `tia.export_block` | Export one block as SimaticML XML |
| `tia.export_project` | Full official Openness chapter-6 export (`--full`, default) or legacy `Blocks/` (`blocks_only` / `--blocks-only`) |
| `tia.import_block` | Import SimaticML XML into the open project (`ImportOptions.Override` / `None`) |
| `tia.save_project` | Persist the open project (`Project.Save`) after import |
| `tia.archive_project` | Archive open project to compressed `.zap*` (`Project.Archive` + `Compressed`) |

Write-back flow: `tia.open_project` → `tia.import_block` → `tia.save_project` → `tia.archive_project`.

**License:** Export/Import/Archive require a valid STEP 7 / TIA license (e.g. STEP 7 Basic).

## Downstream

```text
tia.export_* / .apxx
      → plc.tia.ingest
      → Parser → PLC-IR → KG → Neo4j (optional)
      → PLC Agent
```

## Layout

```text
tia-openness/
├── README.md
├── TiaOpenness.sln
├── src/
│   ├── TiaOpenness.Server/
│   │   ├── Program.cs
│   │   ├── TiaConnection.cs
│   │   ├── ProjectService.cs
│   │   ├── BlockService.cs
│   │   ├── ExportSurface.cs
│   │   └── OpennessExport.cs
│   └── TiaOpenness.Models/
└── tests/
    └── TiaOpenness.Tests/
```

## Prerequisites

1. Windows + **TIA Portal V19** with Openness / PublicAPI
2. User in Windows group **Siemens TIA Openness** (installer name; sometimes shown as TIA Portal Openness)
3. **Sign out and sign back in** after being added to the group so the logon token includes it  
   (`tia.get_status` → `opennessGroupInToken` must be `true`)
4. .NET **8 SDK** + **.NET Framework 4.8.1 targeting pack** (server targets `net481` because Siemens.Engineering uses Remoting)
5. Optional env:
   - `TIA_VERSION` (default `V19`)
   - `TIA_PORTAL_ROOT` (override Portal install path)
6. **Openness firewall** (the Yes / Yes to all dialog): click **Yes to all** once, or run
   `.\scripts\Register-TiaOpennessWhitelist.ps1` as Administrator. `Start-ResearchOS`
   does this after locating the exe. Clicking only **Yes** never persists; rebuilding
   the exe changes SHA256 and needs a whitelist refresh.

## Build & test

```powershell
cd tools\industrial-mcp\tia-openness
dotnet build -c Release
dotnet test
```

## Run (stdio MCP)

```powershell
dotnet run --project src\TiaOpenness.Server -c Release
```

## Run (one-shot CLI — Python importer)

```powershell
dotnet run --project src\TiaOpenness.Server -c Release -- --cli status
dotnet run --project src\TiaOpenness.Server -c Release -- `
  --cli export-project --project "C:\Projects\Line.ap19" --export-dir "C:\Export\Line"
# default is --full (official chapter-6 surface). Legacy blocks: add --blocks-only
dotnet run --project src\TiaOpenness.Server -c Release -- `
  --cli import-block --project "C:\Projects\Line.ap19" --xml "C:\Export\Line\Blocks\FB_Motor.xml"
dotnet run --project src\TiaOpenness.Server -c Release -- `
  --cli archive-project --project "C:\Projects\Line.ap19" --out-dir "C:\Out" --name "Line.zap19"
# optional: --plc <name>  --no-overwrite
```

`import-block` opens the project, imports the XML, saves, then disconnects (JSON on stdout).
`archive-project` opens the project and writes a compressed `.zap*` via Openness `Project.Archive`.

Then:

```powershell
# offline bridge
uv run researchos-tia-cli --exports C:\Export\Line --result-dir .\ResearchOS_PLC_Result
# or via MCP tool plc.tia.ingest
```

## Official Openness export / parse surface (chapter 6, 11/2023)

Source of truth: *TIA Portal Openness API for automation of engineering workflows* (do **not** commit the PDF).
C# walks compositions with reflection (`Export(FileInfo, ExportOptions.WithDefaults)`). Know-how / inconsistent / no-license / missing Export are recorded in `manifest.json` and never crash the job.

Default CLI: `--full`. Old `Blocks/` only: `--blocks-only` (or `RESEARCHOS_TIA_EXPORT_BLOCKS_ONLY=1`). Python ingest accepts both layouts.

```text
export_dir/
  plc/<plcName>/blocks|types|tags|watch|force|to|alarms|cfc|safety/
  hardware/          # devices.xml always; project.aml when CAx exists
  hmi/<hmiName>/     # tags, scripts, textlists, screens, … (structure only)
  opcua/             # optional
  project/texts.xml  # multilingual project texts when Export exists
  manifest.json      # counts + skipped (know_how, inconsistent, no_export, …)
  _exported.jsonl    # incremental Python parse journal
```

| Manual | Object | Export | Parse | Skip-with-reason |
|--------|--------|--------|-------|------------------|
| 6.4.2 | Blocks OB/FB/FC/DB (SCL, GRAPH, F-blocks, system, snapshots) | yes | existing PLC-IR | `know_how` (interface-only), `inconsistent`, `no_license` |
| 6.4.2.27–31 | PlcTypes / UDT (`TypeGroup`) | yes | IR UDT | same |
| 6.4.4 | PLC tag tables + constants | all groups | `tag_tables` | `no_export` |
| 6.4.2.26 | Watch & Force tables | yes | `watch_tables` / `force_tables` | `no_export` |
| 6.4.3 | Technology objects (Motion/PID/Counting) | yes | `technology_objects[]` | `no_export` / `no_license` |
| 6.4.2.19–25 | Alarms / ProDiag | yes | `alarms[]` / `prodiag[]` | `no_export` |
| 6.4.1 | CFC charts | yes | name + blocks/wires best-effort | `password_protected` (listed, not decrypted) |
| 5.11.7 / 6.4.2.9 / 6.5.39 | SafetyUnit / F-program | enumerate + supervisions | `safety_units[]`, F-blocks flagged | `safety_login` / `no_export` (non-F projects skip cleanly) |
| 6.4.2.29 | OPC UA XML | if API present | `opcua_nodes` | `no_export` (optional) |
| 6.5 | Hardware AML + device tree | `hardware/devices.xml`; `project.aml` if CAx | `PlcProject.hardware` (failsafe, racks, modules, subnets) | missing AML does **not** fail block parse |
| 6.3 | HMI / HmiUnified (tags, VB, lists, connections, screens/templates/popups/slide-ins/faceplates/permanent) | XML under `hmi/<device>/` | `hmi_devices[]` structure (name, folder, linked tags) — not pixel layout | `no_export` |
| 6.2 | Project texts | `project/texts.xml` if Export exists | `project_texts` | `no_export`; binary graphics dump skipped |
| — | HMI / AML **Import** write-back | **not in this PR** | — | parse/export only (HITL **block** import stays) |
| 5.20+ | Teamcenter / SINAMICS / SINUMERIK extras | skip unless they appear as normal PlcSoftware children | — | out of scope |

Skip-reason vocabulary (C# ↔ `coverage.json`): `know_how` · `inconsistent` · `no_license` · `no_export` · `password_protected` · `safety_login` · `openness_error`.

## Safety

Cursor / Claude MCP example (`mcp.json`):

```json
{
  "mcpServers": {
    "tia-openness": {
      "command": "dotnet",
      "args": [
        "run",
        "--project",
        "C:/path/to/ResearchOS/tools/industrial-mcp/tia-openness/src/TiaOpenness.Server"
      ],
      "env": {
        "TIA_VERSION": "V19"
      }
    }
  }
}
```

## Safety

- Openness surface: open / list / export XML, plus optional SimaticML **import + save** write-back.
- Does **not** download programs to a PLC.
- Prefer attaching to an already-running Portal; otherwise starts `WithoutUserInterface`.

## Relation to existing adapters

- PowerShell bulk export remains at `industrial/tia_adapter/ExportProject.ps1`
- Python offline analyzer: `researchos-tia-cli` / `agents.plc.tia`
- This MCP server is the Agent-facing Openness foundation for interactive block access
