# Industrial extension guide (Phase 5 stubs)

This package provides **read-only** stubs for Engineering Copilot connectors and a Decision Memo template. Real device write paths are intentionally absent.

## Layout

```
industrial/
  connectors/
    ros2_docs.py   # ROS2 docs catalog interface + fake data
    plc_docs.py    # PLC manuals interface + fake data
    cad_meta.py    # CAD metadata interface + fake data
  templates/
    decision_memo.md
  README.md
```

## Connector contract

Each connector exposes:

1. A `Protocol` describing read-only methods (`search`, `get`, list helpers)
2. A `Fake*Connector` backed by an in-memory `FAKE_CATALOG`
3. `as_dict()` helpers for MCP / JSON serialization

Agents and MCP servers should depend on the **Protocol**, not a vendor SDK.

## How to extend

1. Add a new file under `connectors/` with `Protocol` + fake catalog.
2. Register an MCP tool (e.g. `industrial.ros2.search`) that calls the connector.
3. Whitelist the tool for `mode=industrial` research tasks in Gateway/Runtime.
4. Keep **default read-only**; any write/download-to-device path requires HITL interrupt + ADR.
5. Prefer citing standards in Decision Memo safety sections.

## Usage (Python)

```python
from industrial.connectors.ros2_docs import FakeRos2DocsConnector

ros = FakeRos2DocsConnector()
hits = ros.search("nav2")
```

## Decision Memo

Use `templates/decision_memo.md` as the Writer template when `goal.workflow` / mode is industrial. Citation markers must survive export (`tools/report`).

## Safety

- Do not connect these stubs to production PLC/robot endpoints.
- Do not overwrite CAD vault files from agents.
- Simulation / field writes belong behind explicit feature flags and dual approval.
