# Industrial Knowledge Graph

## Neo4j Schema

## Nodes

- PLCProject
- CPU
- Block
- Variable
- Axis
- Servo
- Sensor
- Alarm

## Relationships

```
PLCProject
 |
HAS_CPU
 |
CPU

CPU
 |
HAS_BLOCK
 |
FB

FB
 |
USES
 |
DB

FB
 |
CONTROLS
 |
Axis

Axis
 |
CONNECTED_TO
 |
Servo
```

## Query Example

问题：哪个程序控制 Axis_X？

Cypher:

```cypher
MATCH (axis:Axis{name:"Axis_X"})<-[:CONTROLS]-(fb:FB)
RETURN fb
```
