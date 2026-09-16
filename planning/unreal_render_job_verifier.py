from pathlib import Path
from typing import Mapping


_ACTIVE_STATUSES = {
    "submitted",
    "queued",
    "rendering",
}


def verify_render_job_completion(
    evidence,
    *,
    require_artifacts=True,
    expected_job_id=None,
):
    """Verify one render-job observation against the authorized expectation.

    ``expected_job_id`` is the authorization-bound job identity: the
    ``verify_render_job`` operation's own ``job_id`` argument after the existing
    ``$previous.submit_render.job_id`` resolution, or the plan's own authorized
    ``job_id`` for a job-addressed ``inspect_render_job`` read. Comparison is an
    exact string comparison after a defensive strip. When it is supplied the
    observation must carry exactly that identity; the executor always supplies
    it on the authorized execution path. ``None`` preserves the legacy call
    shape (no identity binding) for direct verifier callers.
    """
    state = evidence.observed_state

    if not isinstance(state, Mapping):
        raise ValueError(
            "render job evidence observed_state must be a mapping"
        )

    # Production adapters may return the render-job object directly, while
    # transport fixtures can preserve the standard entity envelope:
    # {entity_id: {"render_job": {...}}}.
    if "job_id" not in state:
        render_job = None

        if len(state) == 1:
            entity_state = next(iter(state.values()))
            if isinstance(entity_state, Mapping):
                candidate = entity_state.get("render_job")
                if isinstance(candidate, Mapping):
                    render_job = candidate

        if render_job is None:
            raise ValueError(
                "render job evidence must contain a render_job object"
            )

        state = render_job

    job_id = state.get("job_id")
    if not isinstance(job_id, str) or not job_id.strip():
        raise ValueError(
            "render job evidence must contain a non-empty job_id"
        )

    if expected_job_id is not None:
        if not isinstance(expected_job_id, str) or not expected_job_id.strip():
            raise ValueError(
                "render job verification requires a non-empty expected job_id"
            )

        expected = expected_job_id.strip()

        if job_id.strip() != expected:
            raise ValueError(
                "render job identity mismatch: "
                f"expected job_id={expected!r}, "
                f"observed job_id={job_id.strip()!r}"
            )

    status = state.get("status")

    if state.get("failed") is True:
        raise ValueError(
            f"render job reports failed=True: status={status!r}"
        )

    # Submission verification is intentionally asynchronous. A newly
    # submitted job is valid evidence even though rendering is not finished.
    if not state.get("finished"):
        if status not in _ACTIVE_STATUSES:
            raise ValueError(
                f"render job is neither finished nor in a valid active state: "
                f"status={status!r}"
            )
        return evidence

    if state.get("success") is not True:
        raise ValueError(
            f"finished render job did not report success: status={status!r}"
        )

    output_files = state.get("output_files", [])

    if not isinstance(output_files, (list, tuple)):
        raise TypeError(
            "render job output_files must be a list"
        )

    if require_artifacts and not output_files:
        raise ValueError(
            "render job completed successfully but produced no output_files"
        )

    missing = []
    empty = []

    for value in output_files:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                "render job output_files must contain non-empty strings"
            )

        candidate = Path(value)

        if candidate.is_absolute():
            if not candidate.exists() or not candidate.is_file():
                missing.append(str(candidate))
            elif candidate.stat().st_size <= 0:
                empty.append(str(candidate))

    if missing:
        raise ValueError(
            "render job declared output files that do not exist: "
            + ", ".join(missing)
        )

    if empty:
        raise ValueError(
            "render job declared output files that are empty: "
            + ", ".join(empty)
        )

    return evidence
