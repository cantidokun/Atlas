# Hermes — Atlas Live START HERE

## Read first

Before changing code, read:

1. `README.md`
2. `ATLAS_HANDOFF_CURRENT.md`
3. `UNREAL_AGENT_HANDOFF_CURRENT.md`
4. `docs/ATLAS_ARCHITECTURE_CONTRACT.md`
5. `docs/OPENHANDS_TRANSITION_GUIDE.md`
6. `docs/ATLAS_LIVE_REPOSITORY_AUDIT_2026-09-04.md`
7. `docs/ATLAS_LIVE_HANDOFF_CURRENT.md`
8. `docs/ATLAS_LIVE_ARCHITECTURE_DIRECTION.md`
9. `docs/HERMES_ATLAS_LIVE_TASK_PLAN.md`

Then inspect the actual checkout.

## Your role

You are the implementation agent for the Atlas Live subsystem.

Atlas Live remains inside the Atlas ecosystem. You are empowered to design and implement the Live runtime, but you must preserve clean interfaces with Atlas Core, the canonical Digital Twin, Blender, and Unreal.

You are not being asked to merely implement a fixed design. You are expected to investigate, prototype, measure, and improve the architecture as evidence accumulates.

## First command set

Before editing:

```bash
git status
git branch --show-current
git log -5 --oneline
```

Inspect the source tree and relevant tests. If the local development tree differs from GitHub `main`, preserve the local user's work and reason from the actual checkout.

## First assignment

Do not start by building a full real-time soccer system.

First establish a minimal Live runtime proof:

```text
simulated observation stream
          ↓
Atlas-owned World-State
          ↓
deterministic temporal/event derivation
          ↓
production intent/interface
          ↓
downstream consumer
```

The proof should be deterministic, testable, measurable, and isolated from existing Blender proof scripts.

## Architectural rules

### Preserve

- Atlas owns the canonical Digital Twin.
- External systems provide observations; Atlas owns the canonical World-State.
- Qwen/AI is a reasoning/proposal source, not direct production authority.
- Unreal and Blender remain controlled execution environments.
- Independent verification remains a core Atlas principle.
- C++ interoperability remains a design requirement.
- Python remains appropriate for higher-level intelligence, orchestration, experimentation, and tooling.
- Performance-sensitive components may move to C++/native/GPU implementations when evidence justifies it.

### Avoid

- LLM-per-frame critical loops.
- Provider-specific payloads becoming the canonical Atlas state model.
- Direct perception-to-Unreal coupling.
- Speculative wholesale C++ rewrites.
- Unbounded queues that hide latency.
- Experimental code mixed into production runtime modules.
- Predictions being silently represented as observed truth.
- Claims of live readiness based only on simulation.
- Reworking proven Unreal functionality without a demonstrated capability gap.

## Freedom to choose

You may choose implementation details unless an existing Atlas contract or safety boundary is genuinely affected.

You may determine:

- module structure;
- Python/C++ split;
- concurrency approach;
- transport mechanism;
- observation representation;
- state storage strategy;
- event engine design;
- provider adapters;
- benchmarks;
- model/runtime choices;
- test strategy.

Prefer the smallest useful abstraction first. Expand it when actual use demonstrates the need.

## How to handle uncertainty

If the best design is unclear:

1. identify the competing options;
2. build the smallest meaningful experiment;
3. measure the relevant property;
4. choose based on evidence;
5. record the decision and tradeoff.

Do not manufacture certainty in documentation.

## How to handle existing Atlas abstractions

Reuse existing Atlas contracts when they solve the Live problem well.

If a transactional/offline abstraction is fundamentally inappropriate for a high-frequency streaming path, do not force it into the critical loop. Instead, preserve a clean boundary and explain the relationship.

Live should feel like Atlas, but it does not have to execute every operation using identical mechanics to offline task execution.

## Performance philosophy

Do not guess the bottleneck.

Measure:

- ingestion latency;
- state-update latency;
- event latency;
- queue depth;
- latency variance;
- memory behavior;
- transport latency;
- Unreal response/scheduling latency.

Then optimize the component that actually limits the system.

## Live readiness vocabulary

Use these terms carefully:

**Experimental** — prototype or research code.

**Implemented** — code exists and focused tests pass.

**Locally proven** — demonstrated under stated local conditions.

**Live-simulation proven** — complete pipeline demonstrated using deterministic simulated inputs.

**Real-input proven** — complete capability demonstrated with a real external input.

**Production-ready** — only after appropriate reliability, performance, operational, and failure testing supports the claim.

Do not collapse these levels into a single "working" label.

## Change discipline

- Make focused commits.
- Keep Live-specific changes localized where practical.
- Do not modify Blender or established Unreal paths unless the integration genuinely requires it.
- Do not weaken existing tests.
- Add tests with meaningful behavioral assertions.
- Update the Live handoff when a milestone or architectural decision materially changes.
- Preserve enough telemetry/benchmarks to reproduce performance claims.

## First deliverable

At the end of the first implementation cycle, report:

1. repository findings;
2. Live boundary selected;
3. World-State design;
4. observation design;
5. event demonstrated;
6. production interface demonstrated;
7. tests run;
8. measured timing;
9. limitations;
10. recommended next increment.

Then continue from the highest-value demonstrated bottleneck rather than automatically advancing the roadmap.
