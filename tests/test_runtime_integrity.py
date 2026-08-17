import pytest

from planning.runtime_context import RuntimeContext
from planning.runtime_integrity import authorize_continuation, require_continuation_integrity


def _authorization():
    context = RuntimeContext("ATLAS RULES", {"current_index": 2})
    return context, authorize_continuation(context, plan_digest="plan-1", state_digest="state-1")


def test_matching_runtime_identities_allow_continuation():
    context, auth = _authorization()
    require_continuation_integrity(auth, context, plan_digest="plan-1", state_digest="state-1")


def test_changed_stable_context_fails_closed():
    _, auth = _authorization()
    changed = RuntimeContext("ATLAS RULES v2", {"current_index": 2})
    with pytest.raises(RuntimeError):
        require_continuation_integrity(auth, changed, plan_digest="plan-1", state_digest="state-1")


def test_changed_dynamic_context_fails_closed():
    _, auth = _authorization()
    changed = RuntimeContext("ATLAS RULES", {"current_index": 3})
    with pytest.raises(RuntimeError):
        require_continuation_integrity(auth, changed, plan_digest="plan-1", state_digest="state-1")


def test_changed_plan_fails_closed():
    context, auth = _authorization()
    with pytest.raises(RuntimeError):
        require_continuation_integrity(auth, context, plan_digest="plan-2", state_digest="state-1")


def test_changed_persisted_state_fails_closed():
    context, auth = _authorization()
    with pytest.raises(RuntimeError):
        require_continuation_integrity(auth, context, plan_digest="plan-1", state_digest="state-2")


def test_missing_authoritative_digests_cannot_be_authorized():
    context = RuntimeContext("ATLAS RULES", {})
    with pytest.raises(ValueError):
        authorize_continuation(context, plan_digest="", state_digest="state-1")
