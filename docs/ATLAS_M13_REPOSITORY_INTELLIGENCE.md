# Atlas M13.1 — Deterministic Repository Intelligence

## Status

**M13.1 implemented on `m13-repository-intelligence`.** This milestone establishes the structural repository-information layer needed before context compilation. It does not unfreeze or modify M11 routing authority.

## Purpose

Atlas development models should receive the minimum repository information required for a task rather than a broad repository dump. M13.1 creates the deterministic information source for that later context compiler.

The index records:

- repository-relative file metadata
- SHA-256 content identity
- file kind/language and test classification
- Python classes, functions, async functions, and qualified methods
- Python import relationships and best-effort repository-local resolution
- optional current Git revision and recent commit identities
- a deterministic index fingerprint

Malformed Python remains represented in the file index with `parse_status=error`; the index never fabricates symbols or imports.

## Authority boundary

M13.1 is development tooling only. It MUST NOT:

- authorize or submit production actions
- mutate Blender or Unreal state
- issue receipts
- control recovery or retries
- act as scheduler authority
- replace objective evidence verification
- accept model claims as repository truth
- modify M11 risk, routing, escalation, or evidence rules

The repository index is descriptive input to future context selection, not an execution authority.

## Determinism

Given the same repository tree and the same Git metadata, the index is deterministic:

1. paths are normalized to repository-relative POSIX paths;
2. ignored directories are excluded using a fixed default set;
3. files, symbols, and imports are sorted by stable keys;
4. content identity uses SHA-256;
5. serialization uses sorted JSON keys and compact separators;
6. the fingerprint is computed from the canonical index payload.

Git metadata can be disabled for hermetic tests with `include_git_history=False`. When Git is unavailable, history is represented honestly as empty metadata rather than inferred.

## Next milestones

- **M13.2:** deterministic relevance scoring over this index.
- **M13.3:** minimum-sufficient context compiler preserving the existing stable/dynamic request boundary.
- **M13.4:** advisory/shadow integration with frozen M11 routing.

No live provider, action-runner, Blender, or Unreal execution is required for M13.1.
