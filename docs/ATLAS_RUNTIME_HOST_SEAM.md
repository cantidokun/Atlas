# Atlas Controller Host Seam

The `AgentControllerHost` is the explicit host-owned lifecycle boundary for controller execution.

It owns an `AtlasAgentEntrypointRuntime` and the trusted `AgentExecutionContext` used by the
controller loop for one agent execution. The entrypoint runtime now owns that execution context
itself. `AgentControllerHost` and `AgentControllerLoopAdapter` share the runtime-owned context
rather than creating competing context instances.

This gives the normal agent-facing construction path a single lifecycle owner while preserving the
legacy `AgentControllerLoopAdapter(runtime)` construction form. Its default context is empty, so
protected capabilities remain fail-closed until already-authorized provider state is explicitly
installed by the host.

`AgentControllerHost.dispatch()` is the explicit drop-in controller entrypoint seam. It validates
that the request is an `AgentTaskRequest` and delegates classification/execution to the existing
entrypoint runtime without performing authorization itself.

The legacy Blender tool loop remains outside this boundary and is not changed by the host seam.
