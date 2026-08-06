"""PLC Agent (Phase 5 industrial extension).

Read-only engineering assistant: searches PLC manuals via the
`industrial.connectors.plc_docs` connector and produces analysis blocks
(manual coverage, change advice, safety checks). Never writes to field
devices — see docs/industrial/02-plc-and-automation.md.
"""

from agents.plc.node import run

__all__ = ["run"]
