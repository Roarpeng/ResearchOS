# ResearchOS Industrial Architecture

## 总体架构

```
User
 |
ResearchOS Agent Runtime
 |
Supervisor Agent
 |
Industrial Specialist Agents
 |
MCP Layer
 |
+-------------+-------------+-------------+
|             |             |
PLC MCP    Robot MCP     CAD MCP
 |             |             |
TIA        ROS2         SolidWorks
Openness   IsaacSim     FreeCAD
 |
Industrial Knowledge Layer
 |
Neo4j + Vector + Search
```

## 分层设计

### Engineering Source Layer

数据来源：

- TIA Portal
- Codesys
- Robot Controller
- CAD
- Simulation

### Industrial MCP Layer

统一工具接口：

```
tia.list_blocks()
robot.get_program()
cad.extract_bom()
```

### Knowledge Layer

工业对象：

- PLC
- Axis
- Servo
- Sensor
- Robot
- Program
- Alarm

### Agent Layer

包含：

- PLC Agent
- Motion Agent
- Robot Agent
- Failure Analysis Agent
- Engineering Reviewer

### Decision Layer

输出：

- Engineering Report
- Code
- Optimization Proposal
