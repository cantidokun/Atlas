# Controller Context Compatibility Fix — 2026-09-03

The first implementation of entrypoint-owned execution context introduced a regression in existing controller tests.

The regression had two causes:

1. `AgentControllerHost` rejected an explicitly supplied `AgentExecutionContext` when a pre-existing `AtlasAgentEntrypointRuntime` was also supplied.
2. Some adapter tests construct `AtlasAgentEntrypointRuntime` with `__new__` to isolate the loop adapter. Those objects do not have `_execution_context`.

The fix keeps the intended ownership model while preserving those seams:

- `AtlasAgentEntrypointRuntime` owns an `AgentExecutionContext` and exposes `bind_execution_context()` for an explicitly supplied host context.
- `AgentControllerHost` binds a caller-supplied context to an existing runtime instead of rejecting it, preserving one context identity for host/runtime/loop.
- `AgentControllerLoopAdapter` uses the runtime-owned context during normal construction and falls back to a new empty context only for runtimes that bypass initialization.

No authorization is created by these compatibility paths. The default context remains empty and protected Unreal capability execution continues to fail closed until trusted state is explicitly installed.
