    good = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[pair],
    )
    bad = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[pair],
        claimed_observation_digest="0" * 64,
    )
    assert good.observation_identity is not None
    assert bad.failure_codes == ("IDENTITY_MISMATCH",)
    assert bad.semantic_state == "NOT_ESTABLISHED"
    assert bad.overall_state == "NOT_ESTABLISHED"


def test_missing_session_identity_is_not_transport_rooted():
    task, plan = _task_and_plan()
    req, response = _observation_pair(session=False)
    result = verify_semantic_target(
        source_task=task,
        plan=plan,
        observation_pairs=[(req, response)],