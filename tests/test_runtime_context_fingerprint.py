from planning.runtime_context import RuntimeContext, build_runtime_context


def test_same_stable_instructions_have_same_fingerprint():
    a = RuntimeContext("ATLAS RULES", {})
    b = RuntimeContext("ATLAS RULES", {"current_step": 1})
    assert a.stable_fingerprint() == b.stable_fingerprint()


def test_changed_stable_instructions_invalidate_fingerprint():
    old = RuntimeContext("ATLAS RULES v1", {})
    new = RuntimeContext("ATLAS RULES v2", {})
    assert old.stable_fingerprint() != new.stable_fingerprint()
    assert new.matches_stable_fingerprint(old.stable_fingerprint()) is False


def test_fingerprint_is_exposed_without_dynamic_state():
    ctx = build_runtime_context(
        "ATLAS RULES",
        observation={"live": True},
        runtime_state={"cursor": 7},
    )
    rendered = ctx.render()
    assert rendered["stable_fingerprint"] == ctx.stable_fingerprint()
    assert "live" not in rendered["stable_fingerprint"]
    assert "cursor" not in rendered["stable_fingerprint"]


def test_matching_fingerprint_accepts_only_exact_current_prefix():
    ctx = RuntimeContext("ATLAS RULES", {})
    assert ctx.matches_stable_fingerprint(ctx.stable_fingerprint()) is True
    assert ctx.matches_stable_fingerprint("") is False
    assert ctx.matches_stable_fingerprint("not-the-fingerprint") is False
