# LangGraph Runtime

## Purpose

Runtime executes stateful research workflows.

## Responsibilities

- graph execution
- state persistence
- retries
- human interrupt
- streaming

## State Model

```
TaskState
 |
 +-- goal
 +-- plan
 +-- evidence
 +-- citations
 +-- result
```

## Execution

1. Receive task
2. Build graph
3. Execute nodes
4. Save checkpoints
5. Return result
