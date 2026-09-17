"""MRQ Slice D contract: monitoring state is job-scoped in the start callback.

The Movie Render Pipeline executor renders every job already present in the queue
and broadcasts ``OnIndividualJobStarted`` once per started job, so the transport's
start lambda must apply ``Status``/``StatusMessage``/``Progress`` only for the
exact executor job this Atlas submission allocated - the same identity rule Slice 1
applied to artifacts (``OnIndividualJobWorkFinished``).

The transport is C++ with no deterministic harness in this repository, so the
engine-side guard is pinned by SOURCE-LEVEL assertions here (the convention this
repo already uses for modules that cannot be imported) and is proven live by
``tests/test_unreal_mrq_started_identity_real_integration.py``. This module is
separate from ``tests/test_unreal_mrq_attribution_contract.py`` so that the Slice 1
+ Slice 2 tests stay byte-identical while Slice D adds its own cover.
"""

import pathlib
import re

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

# The render-job state member set is frozen: Slice D reuses the identity the
# transport already stores and must not invent another one.
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

START_CALLBACK = "Executor->OnIndividualJobStarted().AddLambda("
FINISH_CALLBACK = "Executor->OnIndividualJobWorkFinished().AddLambda("

# Tokens that would mean a second identity source or a non-identity heuristic.
FORBIDDEN_IDENTITY_TOKENS = (
    "GetJobs()",
    "Queue->",
    "QueueSerialNumber",
    "CurrentPipelineIndex",
    "FDateTime",
    "mtime",
    "FilePaths",
    "OutputDirectory",
    "GetName()",
    "GetPathName()",
    "GetFullName()",
    "JobId=InJob",
)

STATUS_WRITES = (
    '(*Found)->Status=TEXT("rendering");',
    '(*Found)->StatusMessage=TEXT("Render job started");',
    "(*Found)->Progress=0.0;",
)

TERMINAL_FLAGS = ("bFinished", "bSuccess", "bFailed")


def _transport_source():
    return TRANSPORT_SOURCE.read_text(encoding="utf-8", errors="replace")


def _lambda_body(source, marker):
    """Return the exact body of one ``<marker> ... AddLambda( ... );`` block."""
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


def _start_region(from_index):
    """The region between a marker and the first monitoring write."""
    body = _lambda_body(_transport_source(), START_CALLBACK)
    return body[from_index : body.index(STATUS_WRITES[0])]


# --------------------------------------------------------------------------
# 1. matching start callback updates the registered job
# --------------------------------------------------------------------------


def test_start_callback_updates_the_registered_job():
    body = _lambda_body(_transport_source(), START_CALLBACK)

    assert "InJob" in body, "the started callback does not receive the job identity"
    assert "(*Found)->Job.Get()" in body, "the registered Atlas job is not read"
    assert "InJob!=RegisteredJob" in body.replace(" ", ""), (
        "the started callback does not compare the payload job against the registered job"
    )

    guard = body.index("InJob!=RegisteredJob")

    for write in STATUS_WRITES:
        assert write in body, f"missing monitoring write: {write}"
        assert guard < body.index(write), (
            f"monitoring write {write!r} is not gated by the identity guard"
        )


# --------------------------------------------------------------------------
# 2. foreign start callback cannot update the registered job
# --------------------------------------------------------------------------


def test_foreign_start_callback_cannot_update_the_registered_job():
    body = _lambda_body(_transport_source(), START_CALLBACK)
    registered = body.index("UMoviePipelineExecutorJob* RegisteredJob=")
    first_write = body.index(STATUS_WRITES[0])

    guard_region = body[registered:first_write]

    assert re.search(r"\breturn;", guard_region), (
        "a foreign start payload does not return before writing monitoring state"
    )
    # The guard region must contain no monitoring or terminal write at all.
    for token in STATUS_WRITES:
        assert token not in guard_region
    for token in TERMINAL_FLAGS:
        assert token not in guard_region
        assert token not in body, (
            f"the started callback must not write terminal flag {token!r}; "
            "acceptance state belongs to the finish callbacks only"
        )


# --------------------------------------------------------------------------
# 3. unresolved/expired registered job fails closed
# --------------------------------------------------------------------------


def test_unresolved_registered_job_fails_closed():
    body = _lambda_body(_transport_source(), START_CALLBACK)
    lookup = body.index("RenderJobRegistry.Find(JobId)")
    first_write = body.index(STATUS_WRITES[0])

    early = body[lookup:first_write]

    assert re.search(r"if\(!Found \|\| !Found->IsValid\(\)\)", early), (
        "the registry miss path is not an explicit fail-closed early return"
    )
    assert re.search(r"\breturn;", early)
    for token in STATUS_WRITES:
        assert token not in early


def test_expired_registered_job_pointer_fails_closed():
    """A job pointer that has been collected must not match either."""
    body = _lambda_body(_transport_source(), START_CALLBACK)

    assert re.search(r"if\(!RegisteredJob \|\| InJob!=RegisteredJob\)", body), (
        "a null/invalid registered job must fail closed, not fall through"
    )


# --------------------------------------------------------------------------
# 4. no second identity source is introduced
# --------------------------------------------------------------------------


def test_no_second_identity_source_is_introduced():
    header = TRANSPORT_HEADER.read_text(encoding="utf-8", errors="replace")
    start = header.index("struct FRenderJobState")
    state = header[start : header.index("};", start)]
    members = tuple(
        line.strip()
        for line in state.splitlines()
        if line.strip().endswith(";") and "(" not in line.strip()
    )

    assert members == FROZEN_RENDER_JOB_STATE_MEMBERS, (
        "FRenderJobState members changed; Slice D must reuse the stored job pointer"
    )

    source = _transport_source()

    assert source.count("FGuid::NewGuid()") == 1, (
        "more than one render-job identity mint exists"
    )

    region = _start_region(0)
    for token in FORBIDDEN_IDENTITY_TOKENS:
        assert token not in region, (
            f"the start guard appears to use a non-identity source: {token!r}"
        )


# --------------------------------------------------------------------------
# 5. Slice 1's artifact guard remains intact and unchanged in shape
# --------------------------------------------------------------------------


def test_slice_1_artifact_guard_remains_intact():
    body = _lambda_body(_transport_source(), FINISH_CALLBACK)

    assert "InOutputData.Job.Get()" in body
    assert "(*Found)->Job.Get()" in body
    assert "PayloadJob!=RegisteredJob" in body.replace(" ", "")
    assert "OutputFiles.AddUnique" in body
    assert body.count("OutputFiles.AddUnique") == 1
    assert body.index("PayloadJob!=RegisteredJob") < body.index("OutputFiles.AddUnique")


def test_start_guard_uses_the_same_identity_expression_as_the_artifact_guard():
    source = _transport_source()
    started = _lambda_body(source, START_CALLBACK)
    finished = _lambda_body(source, FINISH_CALLBACK)

    assert "(*Found)->Job.Get()" in started
    assert "(*Found)->Job.Get()" in finished
