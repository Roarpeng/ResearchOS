# Supervisor Agent

## Responsibility

The Supervisor Agent coordinates all sub agents.

## Architecture

```
User Task
   |
Supervisor
   |
+---- Planner
+---- Research
+---- Reviewer
+---- Writer
+---- Memory
```

## Functions

- task decomposition
- agent selection
- state control
- failure recovery
- final approval

## Rules

The supervisor does not directly perform research. It manages execution.
