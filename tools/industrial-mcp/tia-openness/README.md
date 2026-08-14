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
| `tia.export_project` | Export all OB/FB/FC/DB into a folder |
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
│   │   └── BlockService.cs
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
