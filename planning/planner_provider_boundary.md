# Planner provider boundary

Atlas separates model-specific planning from the control layer.

```text
model runtime
    ↓
provider adapter
    ↓
TaskPlanProposal
    ↓
Atlas validation / authorization
    ↓
evidence + action planning
    ↓
execution / verification
```

## Contract

`planning.planner_provider.PlannerProvider` is the stable interface. A provider accepts its model-specific output and returns either a validated `TaskPlanProposal` or `None` when no admissible plan is present.

The provider boundary does **not** authorize actions and does **not** execute tools.

## Qwen compatibility

`qwen.planner_provider.QwenPlannerProvider` adapts the existing structured Qwen bridge. `qwen.planning_runtime.parse_qwen_plan()` remains available as the compatibility API, but now delegates through the provider interface.

This keeps Qwen as the current implementation without making Qwen a dependency of the generic planning/execution layers. A future provider can implement the same interface without changing authorization, execution, verification, recovery, or continuation code.
