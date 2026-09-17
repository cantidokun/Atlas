"""MRQ artifact-attribution contract: engine identity guard + PNG containment.

Two slices are pinned here.

**Slice 1 (transport).** The Movie Render Pipeline executor renders every job
already present in the editor's queue and broadcasts the per-job callback once
per rendered job, so the transport's ``OnIndividualJobWorkFinished`` lambda must
record artifacts only for the exact executor job this Atlas submission
allocated. The transport is C++ with no deterministic harness in this
repository, so the engine-side guard is pinned by SOURCE-LEVEL assertions here -
the same convention this repo already uses for modules that cannot be imported -
and is proven live by ``tests/test_unreal_mrq_attribution_real_integration.py``.

**Slice 2 (evidence boundary).** An observed PNG artifact may only be attributed
to the job when it lives inside the AUTHORIZED output directory, so an artifact
list that carries the right frame numbers from the wrong job still fails closed.
"""

import pathlib
import re

import pytest

from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_shot_continuity import (
    UnrealShotContinuity,
    canonicalize_artifact_path,
    is_inside_directory,
    verify_shot_continuity_completeness,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
TRANSPORT_SOURCE = (
    REPO_ROOT
    / "unreal"
    / "AtlasUnrealHarness"
    / "Source"
    / "AtlasUnrealTransport"
    / "Private"
    / "AtlasTransportServer.cpp"
)
TRANSPORT_HEADER = (
    REPO_ROOT
    / "unreal"
    / "AtlasUnrealHarness"
    / "Source"
    / "AtlasUnrealTransport"
    / "Public"
    / "AtlasTransportServer.h"
)

TARGET = "FIELD_SURFACE"
SEQUENCE = "/Game/AtlasTest/AtlasSequencerFixtureSequence"
JOB_ID = "job-4D92AB93"
START_FRAME = 1
END_FRAME = 2

# The render-job state member set frozen by the attribution milestone: the guard
# must use the identity the transport already stores, and no new identity field
# may be invented.
FROZEN_RENDER_JOB_STATE_MEMBERS = (
    "FString JobId;",
    "FString OperationName;",
    "FString SequenceAssetPath;",
    "FString Status;",
    "FString StatusMessage;",
    "double Progress;",
    "FString OutputDirectory;",
    "FString OutputFormat;",
    "int32 StartFrame;",
    "int32 EndFrame;",
    "int32 EndFrameExclusive;",
    "TArray<FString> OutputFiles;",
    "bool bSuccess;",
    "bool bFinished;",
    "bool bFailed;",
    "TWeakObjectPtr<UMoviePipelineExecutorBase> Executor;",
    "TWeakObjectPtr<UMoviePipelineExecutorJob> Job;",
)


def _transport_source():
    return TRANSPORT_SOURCE.read_text(encoding="utf-8", errors="replace")


def _lambda_body(source, marker):
    """Return the exact body of one ``<marker>().AddLambda( ... );`` block."""
    start = source.index(marker)
    open_index = source.index("{", start)
    depth = 0

    for index in range(open_index, len(source)):
        character = source[index]
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return source[open_index : index + 1]

    raise AssertionError(f"unterminated lambda body for {marker}")


@pytest.fixture()
def attribution_lambda():
    return _lambda_body(
        _transport_source(),
        "Executor->OnIndividualJobWorkFinished().AddLambda(",
    )


# --------------------------------------------------------------------------
# Slice 1 - engine-side attribution guard (source-level contract)
# --------------------------------------------------------------------------


def test_attribution_guard_compares_the_payload_job_with_the_registered_job(
    attribution_lambda,
):
    """Ownership is decided by job identity, never by queue order."""
    body = attribution_lambda

    assert "InOutputData.Job.Get()" in body, "payload job identity is not read"
    assert "(*Found)->Job.Get()" in body, "registered Atlas job identity is not read"
    assert "PayloadJob!=RegisteredJob" in body.replace(" ", ""), (
        "the payload job is not compared against the registered Atlas job"
    )

    guard = body.index("PayloadJob!=RegisteredJob")
    recorded = body.index("OutputFiles.AddUnique")

    assert guard < recorded, "artifact recording is not gated by the identity guard"


def test_attribution_guard_returns_before_any_artifact_is_recorded(
    attribution_lambda,
):
    """A foreign payload returns before any state or artifact is written."""
    body = attribution_lambda
    registered = body.index("UMoviePipelineExecutorJob* RegisteredJob=")
    first_status_write = body.index('(*Found)->Status=TEXT("finished")')

    guard_region = body[registered:first_status_write]

    assert re.search(r"\breturn;", guard_region), (
        "the foreign-payload path does not return before writing job state"
    )
    assert guard_region.index("return;") < body.index("OutputFiles.AddUnique")


def test_attribution_guard_fails_closed_when_the_registry_entry_is_unresolvable(
    attribution_lambda,
):
    """A missing or invalid registry entry records nothing at all."""
    body = attribution_lambda
    lookup = body.index("RenderJobRegistry.Find(JobId)")

    early = body[lookup : body.index("UMoviePipelineExecutorJob* RegisteredJob=")]

    assert re.search(r"if\(!Found \|\| !Found->IsValid\(\)\)", early), (
        "the registry miss path is not an explicit fail-closed early return"
    )
    assert re.search(r"\breturn;", early)
    assert "AddUnique" not in early


def test_attribution_guard_does_not_infer_ownership_from_paths_or_timing(
    attribution_lambda,
):
    """No path, file name, frame number, ordering or timing heuristic is used."""
    body = attribution_lambda
    guard_region = body[
        body.index("UMoviePipelineExecutorJob* RegisteredJob=") :
        body.index('(*Found)->Status=TEXT("finished")')
    ]

    for forbidden in (
        "OutputDirectory",
        "FilePaths",
        "mtime",
        "FDateTime",
        "GetJobs()",
        "Queue",
        "Index",
    ):
        assert forbidden not in guard_region, (
            f"ownership appears to be inferred from {forbidden!r}"
        )


def test_transport_introduces_no_second_job_identity_source():
    """The guard reuses the stored job pointer; no new identity field exists."""
    header = TRANSPORT_HEADER.read_text(encoding="utf-8", errors="replace")
    state = header[header.index("struct FRenderJobState") : header.index("};", header.index("struct FRenderJobState"))]

    members = tuple(
        line.strip()
        for line in state.splitlines()
        if line.strip().endswith(";") and "(" not in line.strip()
    )

    assert members == FROZEN_RENDER_JOB_STATE_MEMBERS, (
        "FRenderJobState members changed; a new job identity must not be invented"
    )

    source = _transport_source()

    assert source.count("FGuid::NewGuid()") == 1, (
        "more than one render-job identity mint exists"
    )


# --------------------------------------------------------------------------
# Slice 2 - PNG artifact containment against the authorized directory
# --------------------------------------------------------------------------


def _continuity(output_directory, *, start_frame=START_FRAME, end_frame=END_FRAME):
    return UnrealShotContinuity(
        sequence_asset_path=SEQUENCE,
        start_frame=start_frame,
        end_frame=end_frame,
        output_directory=output_directory,
        output_format="png",
    )


def _artifact(directory, frame):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"frame_{frame:04d}.png"
    path.write_bytes(b"png")
    return str(path.resolve())


def _evidence(output_files, *, output_directory, start_frame=START_FRAME, end_frame=END_FRAME):
    return UnrealEvidence(
        operation_name="inspect_render_job",
        entity_ids=(TARGET,),
        observed_state={
            "job_id": JOB_ID,
            "status": "finished",
            "finished": True,
            "success": True,
            "failed": False,
            "sequence_asset_path": SEQUENCE,
            "start_frame": start_frame,
            "end_frame": end_frame,
            "end_frame_exclusive": end_frame + 1,
            "output_directory": output_directory,
            "output_format": "png",
            "output_files": list(output_files),
        },
        source="mrq-attribution-contract",
        verified=True,
    )


def test_artifacts_inside_the_authorized_directory_pass(tmp_path):
    directory = tmp_path / "AtlasShotContinuityOutput"
    files = [_artifact(directory, frame) for frame in (1, 2)]
    expected = _continuity(str(directory))
    evidence = _evidence(files, output_directory=str(directory))

    assert verify_shot_continuity_completeness(evidence, expected) is evidence


def test_correct_frame_set_in_a_foreign_directory_fails(tmp_path):
    """The frame set is right; the provenance is not. Must fail closed."""
    authorized = tmp_path / "AtlasShotContinuityOutput"
    foreign = tmp_path / "SomeEarlierJobOutput"
    files = [_artifact(foreign, frame) for frame in (1, 2)]
    expected = _continuity(str(authorized))
    evidence = _evidence(files, output_directory=str(authorized))

    with pytest.raises(ValueError, match="outside the authorized output directory"):
        verify_shot_continuity_completeness(evidence, expected)


def test_foreign_job_artifacts_with_identical_frame_numbers_cannot_pass(tmp_path):
    """The same-range case the frame-set-only rule previously accepted."""
    authorized = tmp_path / "AtlasShotContinuityOutput"
    other_job = tmp_path / "AtlasShotContinuityOutputSecondJob"
    files = [_artifact(other_job, frame) for frame in (1, 2)]
    expected = _continuity(str(authorized))
    evidence = _evidence(files, output_directory=str(authorized))

    assert {int(re.search(r"(\d+)(?=\.png$)", value).group(1)) for value in files} == {1, 2}

    with pytest.raises(ValueError, match="outside the authorized output directory"):
        verify_shot_continuity_completeness(evidence, expected)


def test_sibling_directory_prefix_collision_fails(tmp_path):
    """Containment is path-segment based, not a naive string prefix."""
    authorized = tmp_path / "AtlasShotContinuityOutput"
    sibling = tmp_path / "AtlasShotContinuityOutput2"
    files = [_artifact(sibling, frame) for frame in (1, 2)]
    expected = _continuity(str(authorized))
    evidence = _evidence(files, output_directory=str(authorized))

    assert str(sibling.resolve()).startswith(str(authorized.resolve()))

    with pytest.raises(ValueError, match="outside the authorized output directory"):
        verify_shot_continuity_completeness(evidence, expected)


def test_measured_pollution_shape_fails_closed(tmp_path):
    """The measured 24-artifact cross-job shape must not be attributable."""
    authorized = tmp_path / "AtlasShotContinuityOutput"
    earlier_job = tmp_path / "AtlasShotContinuityOutputEarlierJob"
    files = [_artifact(earlier_job, frame) for frame in range(1, 25)]
    expected = _continuity(str(authorized))
    evidence = _evidence(files, output_directory=str(authorized))

    with pytest.raises(ValueError):
        verify_shot_continuity_completeness(evidence, expected)


def test_canonicalization_is_deterministic_across_equivalent_spellings(tmp_path):
    """Absolute, redundant and relative spellings agree on one canonical path."""
    directory = tmp_path / "AtlasShotContinuityOutput"
    files = [_artifact(directory, frame) for frame in (1, 2)]

    canonical = canonicalize_artifact_path(files[0])

    assert canonical == canonicalize_artifact_path(str(directory / "frame_0001.png"))
    assert canonical == canonicalize_artifact_path(
        str(directory / "." / "frame_0001.png")
    )
    assert canonical == canonicalize_artifact_path(canonical)
    assert is_inside_directory(canonical, canonicalize_artifact_path(str(directory)))

    # An absolute declared directory and an absolute artifact resolve consistently.
    expected = _continuity(str(directory))
    evidence = _evidence(files, output_directory=str(directory))

    assert verify_shot_continuity_completeness(evidence, expected) is evidence


def test_relative_artifact_paths_resolve_against_the_project_root():
    """Relative engine paths canonicalize against the Unreal project root."""
    from planning.unreal_render_contract import UNREAL_PROJECT_ROOT

    artifact = canonicalize_artifact_path(
        "Saved/AtlasShotContinuityOutput/AtlasRender_0001.png"
    )
    directory = canonicalize_artifact_path("Saved/AtlasShotContinuityOutput")

    assert artifact.startswith(str(UNREAL_PROJECT_ROOT.resolve()).replace("\\", "/"))
    assert is_inside_directory(artifact, directory)


def test_non_png_formats_keep_the_existing_behavior(tmp_path):
    """Containment is PNG-scoped; other formats keep existence validation only."""
    authorized = tmp_path / "AtlasShotContinuityOutput"
    foreign = tmp_path / "SomeEarlierJobOutput"
    files = [_artifact(foreign, frame) for frame in (1, 2)]
    expected = UnrealShotContinuity(
        sequence_asset_path=SEQUENCE,
        start_frame=START_FRAME,
        end_frame=END_FRAME,
        output_directory=str(authorized),
        output_format="exr",
    )
    evidence = _evidence(files, output_directory=str(authorized))
    evidence = UnrealEvidence(
        operation_name=evidence.operation_name,
        entity_ids=evidence.entity_ids,
        observed_state={**dict(evidence.observed_state), "output_format": "exr"},
        source=evidence.source,
        verified=True,
    )

    assert verify_shot_continuity_completeness(evidence, expected) is evidence


def test_frame_semantics_still_fail_inside_the_authorized_directory(tmp_path):
    """Containment must not replace the exact frame-set rule."""
    directory = tmp_path / "AtlasShotContinuityOutput"
    expected = _continuity(str(directory))

    short = _evidence([_artifact(directory, 1)], output_directory=str(directory))
    with pytest.raises(ValueError, match="PNG frame coverage mismatch"):
        verify_shot_continuity_completeness(short, expected)

    extra = _evidence(
        [_artifact(directory, frame) for frame in (1, 2, 3)],
        output_directory=str(directory),
    )
    with pytest.raises(ValueError, match="PNG frame coverage mismatch"):
        verify_shot_continuity_completeness(extra, expected)

    wrong_frames = _evidence(
        [_artifact(directory, 1), _artifact(directory, 6)],
        output_directory=str(directory),
    )
    with pytest.raises(ValueError, match="frame set mismatch"):
        verify_shot_continuity_completeness(wrong_frames, expected)
