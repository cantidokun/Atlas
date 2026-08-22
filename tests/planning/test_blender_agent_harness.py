from planning.blender_agent_harness import BlenderAgentHarness


def test_harness_records_evidence_actions_and_outcomes():
    harness = BlenderAgentHarness()

    evidence = harness.observe("inspect_scene", object_count=42, healthy=True)
    harness.record_action("inspect_scene_health", {"file_name": "scene.blend"})
    harness.record_outcome(
        tool="inspect_scene_health",
        verified=True,
        complete=False,
        details={"warnings": ["unapplied_transform"]},
    )

    assert evidence.facts["object_count"] == 42
    assert harness.latest_evidence() == evidence
    assert harness.actions[0]["tool"] == "inspect_scene_health"
    assert harness.outcomes[0]["verified"] is True
    assert harness.outcomes[0]["complete"] is False


def test_harness_reset_is_deterministic():
    harness = BlenderAgentHarness()
    harness.observe("scene", healthy=True)
    harness.record_action("inspect_scene", {"file_name": "scene.blend"})
    harness.record_outcome(tool="inspect_scene", verified=True, complete=True)

    harness.reset()

    assert harness.evidence == []
    assert harness.actions == []
    assert harness.outcomes == []
