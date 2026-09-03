# Atlas Controller Host Seam

The `AgentControllerHost` is the host-owned lifecycle boundary for controller execution.

It owns an `AtlasAgentEntrypointRuntime`, the `AgentExecutionContext`, and the
`AgentControllerLoopAdapter` for one agent execution. The host can also accept an
explicit `AgentTaskRequest` through `dispatch()`, making the host itself a drop-in
controller entrypoint seam for agent-facing code.

`AtlasAgentEntrypointRuntime` owns its execution context. When a caller constructs a
host with an already-created runtime and an explicitly supplied execution context,
the host binds that supplied context to the runtime before constructing the loop.
This preserves existing dependency-injection behavior while keeping one authoritative
context identity for the host/runtime/loop lifecycle.

The loop adapter uses the runtime-owned context on normal construction. Its isolated
legacy test seam also tolerates runtimes constructed without `__init__`, falling back
to a fresh empty context; this does not create authorization or bypass the trusted
context boundary.

This seam does not create authorization. The Unreal production capability itself now
requires a host-provided `UnrealAuthorizedProductionPlan` in addition to the explicit
production request. A model-supplied string or missing authorization therefore cannot
admit the protected Unreal production capability, and the default context remains
empty so protected capabilities fail closed.

The legacy Blender tool loop remains outside this boundary and is not changed by
this seam.
