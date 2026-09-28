## Current U1 validation pause — September 28, 2026 UTC

The portable read-only extraction mechanism is now landed via PR #146 at main 8f601184e62da2362ec38c948e61b7ff8058f95b.

The current synthetic validation project is:

C:\Users\Gavin's PC\Desktop\AtlasU1MockTwin_CleanValidation\AtlasU1MockTwin.uproject

Status: MOCK TWIN VALIDATION INCOMPLETE.

Positive actor and sequencer extraction are validated; direct sequence inspection proves two camera possessables and one camera-cut section bound to MockCamera_Main. The negative/lossy/incomplete/foreign extraction responses are invalid because they report the positive world. The immediate blocker is target-map isolation.

No mock data may populate planning/m12/expectation.py. U1 PRODUCTION AUTHORITY: NOT ESTABLISHED.

R2-B REV10 is the frozen external normative baseline, exact SHA 5d2409cf2ee0c15e35f73ecbae59ab2e03ddbd70abdb3f8c5e4dfc1d9b0d452f; fresh GLM and GPT-SOL-6 reviews are CLEAR. R2-B implementation remains unauthorized pending U1/U7 and human-gate closure.\n\n# M12 — semantic → runtime line (`planning/m12`)

Status of the M12 milestones as landed on `main`.

| Milestone | Module | Status |
|---|---|---|
| M12.1 | `semantic_task.py` | landed |
| M12.2 | `catalog.py`, `fragments.py`, `fragments_registry.py`, `composition.py` | landed |
| M12.3 | `execution_plan.py` | landed |
| M12.4 | `runtime_adapter.py` | landed |
| M12.5 | `verification.py`, `verification_result.py` | landed (frozen) |
| M12.6 R1 | normative design chain (R16 → … → R25) | **R25 frozen — sole normative authority** |
| M12.6 R2-A | `expectation.py` (refusal-only machinery) | **LANDED — independently reviewed, CI-green** |
| M12.6 R2-B | normative external design (REV4) | **REV4 REVIEW GATE — implementation unauthorized** |

## M12.6-R2-A — refusal-only machinery (LANDED 2026-09-27)

**M12.6-R2-A — IMPLEMENTED, INDEPENDENTLY REVIEWED, CI-GREEN, LANDED**

- Landed implementation commit `7b591445d1a11e0ae181330fafaf0956d6cebdbb` (tree `4f84f832b5e59d1fa8f47eecc382122a631faeb1`) via PR #143; merge commit `e9a572c2104153285b1139d7dc09d1e9acd479ac`
  (2026-09-27); functional baseline before it: `4897d9d4524df6cc2fa59caf0c86fa0b269f35a6`.
- Normative authority: `ATLAS_M12_6_R1_NORMATIVE_DESIGN_REV25.md`, SHA-256 `8f9cccc6c59635a554cc63f200c719d80c09dce0372e13715c83aee1809ae1c8`
  (declaration-field self-digest `e80a4398db4816310720139e61b9772d6fa92615e25a23f017a4a0311b5ec5fa`).
- Independent implementation gate: GLM CLEAR and GPT-SOL-6 CLEAR on the exact implementation SHA (the human
  gate's attestation).
- Evidence: focused R2-A suite 96 PASS / 0 FAIL (pinned CPython 3.11.16); `tests/m12` 486 passed; full
  deterministic suite 4442 passed / 132 skipped / 0 failed.
- Landed behaviour (Part XVII item 6 / XXIV.1, Option C): the verifier and resolver expose **no
  render-evidence parameter**; rows 32/42/43/44 are unconditional for a render-bearing input; rows 36/37 are
  unreachable and refused at the result boundary; no M5 provenance is imported, called, inspected or
  re-derived; `DURABLE_RECORD_BACKED` is R2-B-only; the three render identity members are `null`;
  `render_state` stays `NOT_VERIFIED`; every outcome is a refusal. R1 (`render_task` ↔ render rows) and R2
  (S4-stage row membership ⇒ render rows, from the frozen Part XV table) are enforced at the trusted result
  boundary at construction, at serialization and after mutation.
- Not landed (R2-B, not started): render-evidence provenance and the M5→M12 provenance gate, target
  population/registration, positive semantic verification and receipts.
- `PR #142` is historical and untouched; it is not an implementation base.
## M12.6-R2-B — normative design paused at REV4 review gate (2026-09-27)

**M12.6-R2-B — REV4 EXISTS; IMPLEMENTATION NOT AUTHORIZED**

- External normative candidate: ATLAS_M12_6_R2B_NORMATIVE_DESIGN_REV4.md.
- Exact SHA-256: 6fc8027cd79908be0b8a551cf94f9ceafd6ada6f2237a372bca4fbb739c5fc7d.
- Declaration self-digest: 7e2a2012b019300ef58e8514ebf2f67bb064b21aa1b003930a3e3c1798158581.
- REV4 is a document-only architecture artifact; no production code has been changed for R2-B.
- REV3 historical review state: GLM **CLEAR**; GPT-SOL-6 **BLOCKED** on three concrete blockers.
- REV4 explicitly closes those three blocker classes:
  - SATISFIED => deciding_stage = null; S6 evaluated mismatch => S6;
  - positive render serialization/digest requires live PCA-backed re-establishment of H1-H5 from trusted source inputs;
  - evidence_source_class is internally derived from H3 and compared with M5's validated class.
- Adversarial matrix: **41 cases**.
- Route discriminator remains the existing canonical verifier_revision member: R2-A m12.6-v1, R2-B m12.6-r2b-v1.
- R2-A/R25, U1/U6/U7, the ten-field journal-attestation boundary, exact render identity recipe, and read-only H1 semantics remain protected.
- **Fresh exact-SHA GLM review: pending.**
- **Fresh exact-SHA GPT-SOL-6 review: pending.**
- Implementation is **not authorized** until both fresh independent reviews are CLEAR and the required human-gate/rider decisions are explicitly dispositioned.
