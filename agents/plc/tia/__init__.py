"""TIA Portal Openness bridge for the PLC Agent.

- `simaticml`: SimaticML XML -> PLC-IR (offline, no TIA Portal needed)
- `kg`: PLC-IR -> typed knowledge graph
- `scl`: PLC-IR -> SCL translation
- `pipeline`: end-to-end analysis entry point

Live TIA extraction (requires TIA Portal + Siemens.Engineering.dll) is
provided by `industrial/tia_adapter/ExportProject.ps1`, which produces
the SimaticML export folder consumed by this package.
"""

from agents.plc.tia.pipeline import analyze_tia_exports, interpretation_report

__all__ = ["analyze_tia_exports", "interpretation_report"]
