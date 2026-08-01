# ResearchOS System Design

## 1. Overview

ResearchOS is designed as an Agent Operating System for autonomous research and engineering intelligence.

The architecture follows:

- Agent First
- MCP Native
- Knowledge Centric
- Model Independent

## 2. System Layers

```
Frontend
    |
API Gateway
    |
Agent Runtime
    |
Supervisor Agent
    |
+----------------+
| Planner        |
| Research       |
| Reviewer       |
| Writer         |
| Memory         |
+----------------+
    |
MCP Tool Layer
    |
Knowledge Layer
    |
Storage Layer
```

## 3. Core Components

### API Gateway

Responsibilities:

- authentication
- session management
- streaming response
- API routing

### Agent Runtime

Based on LangGraph.

Responsibilities:

- state machine execution
- checkpoint recovery
- tool invocation
- human interruption

### Knowledge Engine

Hybrid architecture:

- Qdrant vector retrieval
- Neo4j knowledge graph
- PostgreSQL metadata

## 4. Research Flow

```
Question
 |
Planner
 |
Research Tasks
 |
MCP Tools
 |
Knowledge Retrieval
 |
Analysis
 |
Reviewer
 |
Report Generation
```

## 5. Design Principles

### Persistent Intelligence

Knowledge must accumulate over time.

### Tool Extensibility

Every external capability is exposed through MCP.

### Model Independence

Models are accessed through LiteLLM gateway.
