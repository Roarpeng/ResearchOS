# TIA Portal Openness Adapter

Exports a Siemens TIA Portal project to SimaticML XML for the ResearchOS PLC Agent (read-only analysis).

## Prerequisites

1. TIA Portal **V17+** with Openness / PublicAPI installed
2. Windows user in group **Siemens TIA Portal Openness**
3. Project path to a `.ap17` / `.ap18` / `.ap19` / `.ap20` file

## Export

```powershell
cd industrial\tia_adapter
.\ExportProject.ps1 `
  -ProjectPath "C:\Projects\MyLine.ap19" `
  -ExportDir "C:\Export\MyLine" `
  -TiaVersion V19 `
  -PlcName "PLC_1"   # optional; default = first PLC found
```

Output layout:

```
C:\Export\MyLine\
  Blocks\           # recursive groups preserved as subfolders
  TagTables\
```

## Analyze (offline, no TIA needed)

```powershell
researchos-tia-cli --exports "C:\Export\MyLine" --out .\scl_out --kg kg.json
# or
python -m agents.plc.tia_cli --exports "C:\Export\MyLine" --out .\scl_out --kg kg.json
```

Exit code is non-zero if the folder is missing, has no XML, or yields zero blocks.

## Agent / UI

- Env: `RESEARCHOS_TIA_EXPORTS=C:\Export\MyLine`
- API: `tia_export_dir` on Gateway create / Runtime `/runs`
- Frontend: industrial mode → optional “TIA 导出目录” field

## Safety

This adapter only **exports** XML. It never downloads programs to a PLC.
