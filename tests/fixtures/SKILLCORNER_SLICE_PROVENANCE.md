# SkillCorner Open Data Tracking Slice Provenance Metadata

- **Source Repository:** https://github.com/SkillCorner/opendata
- **License:** MIT License (Copyright 2020 SkillCorner)
- **Match ID:** 2017461
- **Match Details:** Melbourne Victory FC vs Auckland FC (A-League Men 2024/2025, 2025-05-17)
- **Pitch Dimensions:** 105 m x 68 m
- **Raw File:** `data/matches/2017461/2017461_tracking_extrapolated.jsonl`
- **Reference Events File:** `data/matches/2017461/2017461_dynamic_events.csv`
- **Acquisition Date:** 2026-09-05
- **Frame Range:** Frame 2510 to 3009 (exactly 500 frames, 10 fps, representing elapsed match time 00:00:00.00 to 00:00:49.90 of the first half)
- **Raw File Stored Locally At:** `tests/fixtures/skillcorner_2017461_raw_slice.jsonl`
- **Reference Events Stored Locally At:** `tests/fixtures/skillcorner_2017461_reference_events.json`

## Real-World Characteristics Measured in this Slice:
- Total frames: 500 (10 Hz = 50.0 seconds of continuous play)
- Ball detections (`is_detected=True`): 322 frames (64.4%)
- Ball dropouts / extrapolations / occlusions: 178 frames (35.6%)
- Player detections: 4,302 detections
- Player extrapolations (`is_detected=False`): 4,014 observations
- Unique players tracked: 22 players
