# M12 — semantic → runtime line (`planning/m12`)

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
