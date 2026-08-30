# Atlas Unreal Render Operation Contract

## Scope

This document defines the stable boundary for Atlas render configuration and future render submission work in Unreal Engine.

## Configuration operation

`configure_render` accepts explicit render dimensions, frame range, output directory, and output format. The Unreal transport validates these values before mutating the Movie Render Pipeline configuration.

The initial supported output format is PNG. Invalid dimensions, frame ranges, or unsupported formats must fail deterministically rather than partially applying a request.

## Inspection operation

`inspect_render_state` returns the effective render resolution, frame range, output directory, output format, and configuration asset path. Inspection is the authoritative read-back boundary used by orchestration and verification.

## Native ownership

Render configuration logic belongs in the committed Unreal C++ implementation. CI workflows must verify repository source; they must not be the production mechanism that injects implementation into the source tree.

## Future submission layer

Actual Movie Render Queue submission should be introduced as a separate operation after configuration/inspection are stable. It should expose an operation identifier and deterministic lifecycle state (`queued`, `running`, `completed`, `failed`) without coupling callers to Unreal UI state.

## Interoperability

The transport contract remains language-agnostic. Python orchestration may call the contract, while performance-sensitive Unreal execution remains replaceable or extensible in C++ without changing the external operation schema.
