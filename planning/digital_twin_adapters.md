# Digital Twin Adapter Boundary

Atlas owns the canonical Digital Twin. Production tools are representations of an Atlas revision, not alternative sources of truth.

## Flow

```text
Photogrammetry
      ↓
Atlas intake
      ↓
Canonical Digital Twin revision
      ↓
Representation contract
   ↙          ↘
Blender      Unreal
adapter      adapter
   ↘          ↙
observations / changes
      ↓
Atlas verification
```

## Adapter responsibilities

An adapter may:

- locate or create the tool-side representation for an Atlas revision;
- convert Atlas coordinates and assets into tool-native forms;
- execute authorized production operations;
- collect independent evidence about the resulting tool state;
- report tool-side identifiers and state back to Atlas.

An adapter must not:

- redefine the canonical Digital Twin identity;
- silently promote a tool state to canonical;
- treat a Blender object or Unreal Actor name as an Atlas entity identity;
- overwrite canonical state without an explicit Atlas revision/update path.

## Photogrammetry boundary

Photogrammetry is an upstream reconstruction source. Its output enters Atlas through an intake record and may require analysis, cleanup, correction, identity evaluation, and validation before becoming a canonical revision.

## Future engine adapters

Blender and Unreal should implement the same conceptual contract while remaining free to use their native APIs and scene structures. Engine-specific coordinate conversion, asset handles, scene traversal, and execution details belong inside the adapter rather than inside the Digital Twin model.
