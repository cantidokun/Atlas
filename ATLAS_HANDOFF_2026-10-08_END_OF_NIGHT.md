# ATLAS HANDOFF — 2026-10-08 END OF NIGHT

## Rev46-M1 — Duplicate-occurrence implementation

### Authoritative design

- **R12: CLEAR**
- Fresh independent reviewer: **GPT 6.1 Sol**
- Artifact: `REV46_M1_R12_FINAL_CLOSURE.txt`
- Artifact SHA-256: `75b32f8681a8e1b02110412ea68e0829bca0ae7a4a05208844088af02f8b7b18`
- Exact baseline: `3dc2fca3d1f26cadd45a6c4d773bcb2e24f7cad7`

R12 is frozen and implementation-authorizing. No new design revision is required or authorized unless implementation exposes a genuinely new material contradiction.

### Implementation closeout

**Branch:** `feat/rev46-m1-duplicate-occurrence`

**Implementation commit:** `90e4d0a862cedb0b79b33b703ba716a327230847` (parent `1717c0b8f1633abda9bae51cc9b53eea1f7e033b`).

### Independent implementation review — Claude Sonnet — CLEAR WITH MINOR FINDINGS

The review confirmed:

- duplicate occurrence selection is `face_ids[1]`;
- exact integer validation is enforced;
- no min/max/search/fallback target reconstruction exists;
- `expected_face_tuple` comes from the selected occurrence;
- `params["mesh_id"]` is only a consistency check;
- `corr.mesh_id` remains the authoritative target identity;
- exact-index mutation is enforced;
- the ordered postcondition is enforced;
- harness-side invocation evidence distinguishes identical `[A,X,A,A]` occurrences;
- W1/W1b live gates passed;
- no A-REF implementation exists;
- no authority/persistence/recovery/receipt/Unreal scope leakage was found.

Minor findings are non-blocking and must not trigger another R12 revision.

### Gate state

- **M1 implementation gate: CLOSED.**
- The identical-occurrence mutant (identical `[A,X,A,A]` tuples — the two removal candidates yield the same canonical child) is a documented R12 limitation, not a blocker.
- **No R13 is authorized or required.**
- A-REF implementation has **NOT** started.
- **Next gate: A-REF design red-team** — a fresh independent review of the A-REF design artifact is required before any A-REF implementation.

### Resume instructions

Rev46-M1 is complete and committed at `90e4d0a8...`. Do not amend or rebase that commit; do not author another design revision (no R13) unless a genuinely new material contradiction appears. The next task is the A-REF design red-team; no A-REF implementation may begin before that gate clears.

### Architectural boundary

R12 design is closed. The implementation must remain limited to the frozen duplicate-occurrence contract: executor-authoritative selection, exact-index mutation, expected-tuple validation, ordered duplicate postcondition, and harness-side invocation evidence. Winding, merge, degenerate semantics, approval authority, persistence, deployment, and unrelated architecture remain out of scope. A-REF remains a separate gate: the next gate is the A-REF design red-team, and no A-REF implementation is authorized by this closeout.
