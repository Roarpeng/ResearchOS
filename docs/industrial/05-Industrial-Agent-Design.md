# Industrial Agent Design

## PLC Agent

输入：

PLC Project

输出：

- PLC Architecture Report
- Program Analysis
- Risk Report

## Motion Agent

分析：

- Servo
- EtherCAT
- Homing
- Synchronization

示例：

为什么轴回零失败？

Reasoning:

```
MC_HOME
 ↓
6040
 ↓
6041
 ↓
6098
 ↓
Sensor
```

## Failure Analysis Agent

输入：

- Alarm
- Log
- Program

输出：

Root Cause Tree

方法：

- 5 Why
- Fault Tree
- FMEA
