# Atlas Blender Development

This directory contains the deterministic Blender health kernel, canonical scene/mesh contracts, bounded correction capabilities, and Blender boundary validation work.

## Current authoritative position — September 18, 2026

**Blender Extraction Fidelity v1 — CLEAR.** The bounded read-only extraction producer contract is complete and independently reviewed. The implementation in `planning/blender/bpy_extraction.py` is frozen from this milestone unless a concrete defect is discovered.

Key cleared references:

- design revision: `32eb4f76f82447fc468eeb3c4c86bbe47625297`
- implementation: `9a9e3e840371db46c79de43fe098c6c0846c7840`
- determinism-evidence repair: `a0f0071ceb514dc9f556c4a7fabe40840b1f2bc7`
- final canonicalization/verification closure: `b95d5ab3b1f92a803098c16e9d2af29e3c42aae9`

The cleared Extraction Fidelity v1 scope covers deterministic object membership, visibility, transforms including quaternion-mode handling, mesh vertices/faces, material-slot names, explicit omission semantics for normals/UV/local-frame, deterministic payload evidence, and preservation of the existing digest boundary. It does not add correction/write-back, persistence, event recognition, or temporal state.

## Current next architecture layer — Temporal Observation + State Delta v1

The next layer is **design-only** at present. Current revision:

- branch: `feat/temporal-observation-state-delta-design`
- revision 7: `44d0a1cc38dee7c34e996a1f7d7f2cd0504f6ed4`
- status: **HOLD — independent architectural review found residual consistency defects**
- implementation status: **NO IMPLEMENTATION AUTHORIZED**

Revision 7 correctly closes the previous purity gap by making `FromIdentity` an immutable explicit input of all four evaluation variants. The remaining corrections required for Revision 8 are:

1. remove stale `StateDelta(A,B)` purity wording;
2. reconcile the conceptual pair-domain wording with the complete four-variant evaluation-input domain;
3. correct T-25 / attack #39 so boundary identity mismatch does not incorrectly prohibit the `NEW_EPOCH` admission mutation;
4. update stale two-form `NEW_EPOCH` enumerations/exit criteria to include `PAIR_INPUT_IDENTITY_MISMATCH`;
5. define deterministic handling of multiple simultaneous boundary-cause fields.

Do not implement Temporal Observation/StateDelta, schema versions, Event Abstraction, or streaming/storage from this hold point.

## Development pattern

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

## Wave 12 — `REPAIR_PARENT_CYCLE`

Branch: `feat/blender-wave12-reference-integrity`

Status: **IMPLEMENTATION / VALIDATION COMPLETE — INDEPENDENT REVIEW PENDING**

Design gate: `BLENDER_WAVE12_PARENT_CYCLE_REPAIR_DESIGN.md`

Review packet: `docs/ATLAS_WAVE12_DEEPSEEK_REVIEW_HANDOFF.md`

Wave 12 extends the existing Wave 4 hierarchy-correction boundary to one additional malformed-reference class: a parent cycle. The canonical health kernel already reports hierarchy cycles through `OBJECT_HIERARCHY_INVALID`; Wave 12 makes cycle repair explicit without broadening Wave 4's dangling-parent correction.

The correction is intentionally bounded to one selected parent edge: the explicitly authorized target object's `parent_object_id` is detached to `None`. No new parent is inferred, no other hierarchy edge is changed, and no geometry, transform, naming, collection, persistence, recovery, receipt, workflow, or action-runner authority is introduced.

The canonical executor preserves the selected target's local `location`, `rotation`, and `scale`. A malformed cyclic graph has no defined world pose under the existing parent-chain engine, so world-pose preservation is proven separately at the live Blender boundary using an acyclic disposable parent relationship and `CLEAR_KEEP_TRANSFORM`.

## Validation status

The current Wave 12 validation gates are green:

- deterministic cycle/reference tests — **PASS**;
- adversarial fail-closed tests — **PASS**;
- combined Wave 12 topology + live Blender gate — **PASS**;
- full Wave 1–Wave 12 regression — **PASS**;
- real Blender **4.4.3** disposable boundary gate on the user's host — **PASS**;
- final-head GitHub Actions run **#1904** — **PASS** on Python 3.9 and 3.11, including M13.7 on 3.11.

The live gate verified parent detachment, world-matrix preservation within Blender float32 round-off tolerance (`1.1920928955078125e-07` measured delta against a `1e-6` acceptance threshold), object/mesh identity preservation, object-set preservation, no frozen asset opened, and no save attempt.

## Independent review gate

The remaining gate is an actually independent review of the final HEAD `a2bfdb19071594669f93cb6b81c448b36caf9600`.

The earlier Wave 12 review findings were incorporated, but the GitHub review submissions currently recorded on PR #102 were authored by the repository owner and therefore do **not** satisfy the independent-review requirement. Do not describe them as independent red-team approval.

DeepSeek is planned as the independent adversarial reviewer on the next development session. The reviewer must inspect the final HEAD and the complete Wave 12 contract, not an older checkpoint.

Workflow/action-runner tests remain excluded unless explicitly authorized.

Do not broaden a cycle repair into general hierarchy normalization. A multi-edge mutation, stale authorization acceptance, hidden re-parenting, canonical local-transform drift, world-pose drift at the live boundary, or ambiguous target selection blocks merge.
