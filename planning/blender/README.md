# Atlas Blender Development

This directory contains the deterministic Blender health kernel, canonical scene/mesh contracts, bounded correction capabilities, and Blender boundary validation work.

## Current completed baseline

Waves 1–10 are the completed Blender correction/analysis baseline as of September 15, 2026. Wave 10 merged to `main` at `d1c2a5a804ad801c67cc05d439bc6dc921ac8f4e`.

The development pattern is deliberately staged:

```text
bounded design
    ↓
implementation
    ↓
deterministic validation
    ↓
adversarial validation
    ↓
live Blender boundary validation
    ↓
focused regression + CI
    ↓
independent red-team review
    ↓
merge
```

Execution authority remains separate from the canonical analysis/model layer. Blender-facing adapters are boundary components; canonical executors do not gain persistence, receipt, recovery, workflow, or action-runner authority.

## Wave 11 — next

Branch: `feat/blender-wave11-empty-mesh-contract`

Status: **DESIGN / NOT IMPLEMENTED**

Design gate: `BLENDER_WAVE11_EMPTY_MESH_CONTRACT_DESIGN.md`

Wave 11 hardens the canonical `MeshModel` contract so a real mesh with vertices but zero polygon faces can be represented truthfully. This directly resolves the representation contradiction exposed by Wave 6's all-isolated/zero-face test requirement.

Wave 11 must not fabricate topology. `faces == ()` means exactly that no polygon faces are present. The zero-face mesh remains distinct from an absent mesh, and existing face/index validation remains unchanged.

The live Blender extraction adapter currently rejects a zero-face mesh; Wave 11 must remove that boundary mismatch by extracting the real vertices and returning `faces == ()` without mutation or persistence.

## Validation / merge rule

Wave 11 is not complete until its deterministic tests, adversarial checks, live Blender boundary gate, focused Wave 1–Wave 11 regression, final-head CI, and independent red-team review all pass.

Workflow/action-runner tests remain excluded unless explicitly authorized.

Do not weaken the model or tests to make the zero-face case pass. A representation-level failure blocks merge.
