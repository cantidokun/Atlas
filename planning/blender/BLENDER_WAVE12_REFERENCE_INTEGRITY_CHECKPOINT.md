# Wave 12 — Reference-Integrity Checkpoint

Wave 12 follows directly from the existing hierarchy contract.

The canonical scene-health kernel already distinguishes hierarchy invalidity caused by unknown parents and cycles. Wave 4 provides a bounded repair for the unknown-parent case and explicitly excludes cycles. Wave 12 therefore isolates the next missing hierarchy correction as `REPAIR_PARENT_CYCLE` rather than broadening the existing executor implicitly.

The proposed mutation is one edge only: detach one explicitly selected object from its current parent by setting `parent_object_id` to `None` after fresh cycle verification and exact authorization binding.

This checkpoint does not add implementation. It records the intended boundary so the next implementation can be reviewed against a fixed contract.
