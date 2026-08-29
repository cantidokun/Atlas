# Atlas Unreal Composite Production Operation

## Purpose

Define the production-facing contract between Atlas orchestration and the Unreal render layer for deterministic composite/VFX operations.

## Verified contract

- Render requests are represented as explicit operations rather than ad-hoc editor actions.
- The Unreal layer owns render-queue configuration and execution state.
- The orchestration layer may submit and inspect operations without depending on Unreal UI state.
- Operation state is observable as queued, running, completed, or failed.
- Render presets and output configuration are explicit inputs to an operation.
- Completion and failure are surfaced through a stable callback/result boundary.
- The implementation must remain language-agnostic at the subsystem boundary so performance-sensitive internals can be replaced by C++ incrementally without changing the orchestration contract.

## Verification policy

Feature-branch pushes automatically execute the transactional regression workflow. The latest verified implementation has passed both the dispatch and regression suites.

## Next implementation layers

1. Expand native Unreal render-operation coverage.
2. Add deterministic preset validation and error reporting.
3. Add artifact/result metadata for downstream Atlas orchestration.
4. Keep Python/C++ contracts stable while moving runtime-heavy work into native code.
