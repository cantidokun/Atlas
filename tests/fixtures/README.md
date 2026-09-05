# Atlas Live: Synthetic Tracking Telemetry Contract Fixture
Provenance: Synthetic contract fixture created specifically for Atlas Live integration testing.
Dataset source: None (authored in-tree as an engine test fixture).
Frame count: 5
Frame rate: 50 Hz (20 ms nominal inter-frame interval)
Source ID: cam-field-01
Session ID: session-live-01
Timestamp domain: monotonic_source
Coordinate frame: atlas-field (meters, Z-up, field-centered)

Schema per line:
- `source_id`: Physical camera / sensor origin identifier
- `session_id`: Unique tracking connection or run epoch identifier
- `sequence_number`: Monotonically increasing packet sequence
- `timestamp_ns`: Relative source nanoseconds
- `timestamp_domain`: Declared clock domain (`monotonic_source`)
- `entities`: Array of track observations
  - `track_id`: Provider-local ephemeral tracking ID
  - `x`, `y`, `z`: Position in meters
  - `confidence`: Provider detection confidence [0.0, 1.0]
  - `frame_id`: Coordinate frame identity (`atlas-field`)
  - `track_status`: Detection vs tracking status (`detected` or `predicted`)
