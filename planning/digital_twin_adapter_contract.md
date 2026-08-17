# Atlas Digital Twin Adapter Contract

This boundary is intentionally engine-neutral.

## Canonical direction

```text
Atlas Digital Twin revision
          ↓
TwinRepresentation contract
          ↓
Blender adapter / Unreal adapter
```

## Required adapter behavior

1. Bind a tool representation to a specific Atlas twin and source revision.
2. Preserve Atlas entity identifiers when creating or updating tool objects.
3. Perform tool-native coordinate and asset conversion inside the adapter.
4. Return tool-side identifiers and observations to Atlas.
5. Never promote a tool-side result to canonical state implicitly.
6. Mark representations stale when their source revision is no longer current.

## Upstream reconstruction

Photogrammetry is treated as an intake source, not as a canonical owner. Its reconstruction must enter Atlas through the intake boundary before Blender analysis and cleanup.

## Future Unreal Agent

The Unreal Agent will operate through this boundary. It will not become the owner of the Digital Twin and will not require Atlas to understand Unreal scene internals. Those concerns remain behind the Unreal adapter.
