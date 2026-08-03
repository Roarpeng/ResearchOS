# ResearchOS Agents

Agent callables compatible with LangGraph nodes. Each package exposes `run(state: TaskState) -> dict`.

Phase 4 agents: `research`, `analysis`, `citation`, `reviewer`, `writer`, `memory`.

See `agents/registry.py` for name → callable mapping.
