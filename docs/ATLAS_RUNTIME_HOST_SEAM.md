# Atlas Controller Host Seam

The `AgentControllerHost` is the host-owned lifecycle boundary for controller execution.

It owns the `AtlasAgentEntrypointRuntime`, the `AgentExecutionContext`, and the
`AgentControllerLoopAdapter` for one agent execution. The host can now also accept
an explicit `AgentTaskRequest` through `dispatch()`, making the host itself a
drop-in controller entrypoint seam for agent-facing code.

This seam does not create authorization. Protected Unreal execution still requires
trusted, host-installed Unreal context, and the default context remains empty so
protected capabilities fail closed.

The legacy Blender tool loop remains outside this boundary and is not changed by
this seam.
