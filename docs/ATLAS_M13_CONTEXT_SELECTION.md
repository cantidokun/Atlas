# Atlas M13.2 — Deterministic Context Relevance

## Status

**M13.2 implemented on `m13-repository-intelligence`.** This milestone adds an explainable, deterministic relevance layer over the M13.1 repository index. It does not select a model, execute work, authorize actions, or change M11.

## Scoring model

A development task is represented by explicit structured signals:

- requested repository paths
- requested symbols
- task text
- task classes
- explicitly associated tests
- explicitly associated contracts
- explicitly recent files

Each indexed file receives additive contributions from bounded signals:

1. exact path
2. exact symbol
3. direct dependency
4. reverse dependency
5. test association
6. contract association
7. recent change
8. lexical match
9. same-directory relationship

The default weights intentionally make structural relationships dominate lexical similarity. The weights are immutable configuration and are part of the future benchmark surface; they must not be learned from model output in the production path.

## Determinism

For the same repository index, query, and weights, ranking is deterministic. Ties are resolved by stable path/reason ordering. Results include an explanation for every selected file, allowing later context compilation and benchmarking to show why a file was included.

No embeddings, network calls, model judgments, filesystem reads, or provider calls occur during scoring.

## Authority boundary

M13.2 is development-only analysis tooling. It MUST NOT:

- authorize or submit production actions
- mutate Blender or Unreal state
- issue receipts
- schedule or recover production work
- replace objective evidence
- modify M11 risk, routing, escalation, or evidence rules

A relevance score is a retrieval hint, not proof that a file is safe, correct, current, or authoritative.

## Next step

M13.3 will compile ranked repository information into a minimum-sufficient context package while preserving Atlas's existing stable/dynamic model-request boundary. The compiler should be able to report both included and excluded material so token reduction can be measured rather than assumed.
