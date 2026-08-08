# ResearchOS PLC Intelligence Architecture

Version: 0.1
Status: Architecture Design

## 1. Vision

ResearchOS extends from a general AI research agent platform into an industrial AI engineering platform.

New capability:

- TIA Portal project understanding
- PLC program analysis
- LAD/FBD/STL/SCL semantic parsing
- PLC knowledge graph construction
- SCL generation
- PLC engineering review and optimization

The goal is not only LAD to SCL conversion, but building a PLC semantic model that allows AI agents to understand industrial control logic.

---

## 2. Overall Architecture

```
ResearchOS Core
        |
Agent Orchestration
        |
Industrial Intelligence Layer
        |
PLC Intelligence Engine
        |
+----------------+
| TIA Connector  |
+----------------+
        |
PLC Parser
        |
PLC Intermediate Representation (PLC-IR)
        |
PLC Knowledge Graph
        |
AI Reasoning Agent
        |
Code Generator
```

---

## 3. Core Modules

## 3.1 TIA Portal Connector

Responsibilities:

- Connect Siemens TIA Portal through Openness API
- Export PLC blocks
- Read PLC variables
- Extract project structure

Input:

```
.apxx
.ap17
.ap18
.ap19
```

Output:

```
PLC Project Model
```

---

## 3.2 PLC Parser Engine

Supports:

- LAD
- FBD
- STL
- SCL

Parsing objects:

- Contacts
- Coils
- SET/RESET
- Timers
- Counters
- FB calls
- DB access
- Motion instructions

---

## 3.3 PLC Intermediate Representation

The architecture does not directly convert:

```
LAD -> SCL
```

Instead:

```
LAD/FBD/STL/SCL
        |
      PLC-IR
        |
       SCL
```

Example:

```json
{
  "network":1,
  "logic":{
    "type":"AND",
    "inputs":["Start","Safety_OK"],
    "output":"Motor_Enable"
  }
}
```

PLC-IR becomes the universal representation layer.

---

## 4. PLC Knowledge Graph

Storage:

- Neo4j
- Graphiti

Entities:

```
PLC
 ├── CPU
 ├── Block
 ├── FC
 ├── FB
 ├── DB
 ├── Variable
 ├── Sensor
 └── Actuator
```

Relations:

```
Sensor
  |
controls
  |
Logic
  |
drives
  |
Actuator
```

Example reasoning:

```
Motor_Enable = FALSE

-> Safety_FB FALSE

-> Door sensor abnormal

-> Motor blocked
```

---

## 5. Agent Design

### PLC Analyst Agent

Functions:

- Understand PLC project
- Generate documentation
- Explain control sequences

### PLC Review Agent

Checks:

- Logic errors
- Safety risks
- Missing interlocks
- Timer problems
- State machine issues

### PLC Migration Agent

Functions:

```
Legacy LAD
      |
 PLC-IR
      |
Optimized SCL
```

### PLC Generator Agent

Pipeline:

```
Requirement
    |
Control Design
    |
PLC-IR
    |
SCL
    |
TIA Block
```

---

## 6. Integration With ResearchOS Agents

Existing agents:

- Research Agent
- Planning Agent
- Knowledge Agent

New industrial agents:

- PLC Agent
- Robot Agent
- Motion Agent
- AGV Agent

Unified architecture:

```
ResearchOS Agent OS
        |
Knowledge Graph
        |
Domain Agents
```

---

## 7. Industrial Domain Support

### Servo Motion

Support:

- MC_MoveAbsolute
- MC_Home
- Position
- Velocity
- Torque

### Robot

Support:

- KUKA KRL
- ROS2
- IsaacSim

### AGV

Support:

- State machine
- Navigation
- Task scheduling

---

## 8. AI Reasoning Pipeline

```
User Requirement
        |
Intent Analysis
        |
5 Why Analysis
        |
Six Thinking Hats
        |
Control Requirement
        |
PLC Design Agent
        |
PLC-IR
        |
Code Generation
        |
Test and Verification
```

---

## 9. Development Roadmap

### Phase 1

PLC project extraction:

- [x] TIA Openness connector（`tools/industrial-mcp/tia-openness` MCP：`tia.get_status` / `open_project` / `list_blocks` / `export_block`）
- [x] XML/source export（单块 MCP + 既有 `industrial/tia_adapter` 整工程导出）
- [x] Project model（SimaticML → 既有 PLC-IR / KG 管线）

### Phase 2

PLC semantic layer:

- LAD parser
- SCL parser
- PLC-IR

### Phase 3

AI understanding:

- PLC Analyst Agent
- Automatic documentation

### Phase 4

Code generation:

- PLC-IR to SCL
- PLC modification assistant

### Phase 5

Industrial Copilot:

```
Engineer request
        |
AI analysis
        |
PLC modification
        |
Validation
```

---

## 10. Final Goal

ResearchOS + PLC Intelligence becomes:

```
Industrial AI Engineer

=
PLC Engineer
+
Automation Designer
+
Code Reviewer
+
Process Analyst
```

The core asset is the PLC Semantic Model, not a simple code converter.
