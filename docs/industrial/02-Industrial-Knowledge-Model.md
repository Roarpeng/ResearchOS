# Industrial Knowledge Model

## 基础对象

```
EngineeringProject
 |
 + PLCSystem
 + RobotSystem
 + MechanicalSystem
 + ProductionProcess
```

## PLC Domain

```
PLCProject
 |
 + CPU
 + IO
 + ProgramBlock
 |      + OB
 |      + FB
 |      + DB
 + Variable
 + Alarm
 + Axis
```

## Motion Domain

```
Axis
 |
 + Servo
 + Encoder
 + MotionProfile
 + Homing
 + Limit
```

## Relationship

```
FB
 |
CALLS
 |
FB

FB
 |
CONTROLS
 |
Axis

Axis
 |
USES
 |
Servo
```

工业知识模型用于支撑 GraphRAG 和工程推理。
