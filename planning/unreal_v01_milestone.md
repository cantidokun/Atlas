# Unreal Agent v0.1 / Adapter v0.1 Milestone

## Goal

Establish a complete engine-neutral contract from an Atlas production intent to an Unreal-domain operation and back to Atlas evidence, without requiring Unreal Engine to be installed.

## Complete boundary

```text
Atlas intent
  -> Unreal Agent planning
  -> capability validation
  -> Atlas authorization
  -> Unreal Adapter v0.1
  -> tool evidence
  -> Atlas verification
```

## Explicit non-goals

- no Unreal Engine SDK dependency;
- no direct filesystem/project mutation;
- no autonomous authorization;
- no canonical Twin mutation by the adapter;
- no implicit retry of writes;
- no promotion of tool state to canonical state.

## Exit criteria

- structured Unreal operations have explicit Atlas entity targets;
- capabilities declare permitted operation kinds;
- write operations require an authorization identifier;
- inspection and verification produce evidence records;
- invalid operation boundaries fail closed;
- production representations remain derived from Atlas revisions;
- the same contract can support Blender without changing Atlas ownership rules.

## Next major milestone

Implement the first real Unreal transport behind this boundary and validate it against a disposable Unreal test project. That work begins only after branch reconciliation with `main`.
