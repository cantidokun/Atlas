from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutionFailure, UnrealPlanExecutionResult, UnrealPlanExecutor
from planning.unreal_recovery_sequence import (
    assess_reassessment_sequence, 
    build_reassessment_plan, 
    build_replacement_plan,
    execute_recovery_sequence,
    issue_replacement_authorization
)
from planning.unreal_task_planner import UnrealTaskPlan
from planning.unreal_transport_contract import UnrealTransportRequest, UnrealTransportResponse


ENTITY_IDS = ("FIELD_SURFACE",)


def _plan():
    return UnrealTaskPlan("sequencer-recovery", (
        UnrealOperation(
            UnrealCapability.SEQUENCER,
            UnrealOperationKind.WRITE,
            "set_sequencer_playback_range",
            {"entity_ids": ENTITY_IDS, "start_frame": 10, "end_frame": 110},
            ENTITY_IDS,
        ),
        UnrealOperation(
            UnrealCapability.SEQUENCER,
            UnrealOperationKind.VERIFY,
            "verify_sequencer_playback_range",
            {"entity_ids": ENTITY_IDS, "expected_start_frame": 10, "expected_end_frame": 110},
            ENTITY_IDS,
        ),
        UnrealOperation(
            UnrealCapability.MATERIAL,
            UnrealOperationKind.WRITE,
            "apply_material_variant",
            {"entity_ids": ENTITY_IDS, "material_variant": {"name": "liquid_surface"}},
            ENTITY_IDS,
        ),
    ))


def _failure():
    return UnrealPlanExecutionFailure(
        "sequencer-recovery",
        2,
        "apply_material_variant",
        (),
        "material mutation failed",
        ENTITY_IDS,
        {"entity_ids": ENTITY_IDS, "material_variant": {"name": "liquid_surface"}},
        (),
    )


def _sequencer_evidence(start_frame, end_frame):
    return UnrealEvidence(
        "inspect_sequencer_state",
        ENTITY_IDS,
        {"FIELD_SURFACE": {"entity_id": "FIELD_SURFACE", "sequencer": {"start_frame": start_frame, "end_frame": end_frame}}},
        "unreal-editor-atlas-transport",
    )


def _material_evidence(name):
    return UnrealEvidence(
        "inspect_material_state",
        ENTITY_IDS,
        {"FIELD_SURFACE": {"entity_id": "FIELD_SURFACE", "material": {"variant": {"name": name}}}},
        "unreal-editor-atlas-transport",
    )


def test_reassessment_plan_includes_sequencer_read():
    reassessment = build_reassessment_plan(_plan(), _failure())
    assert [operation.name for operation in reassessment.operations] == ["inspect_sequencer_state", "inspect_material_state"]
    assert all(operation.kind is UnrealOperationKind.READ for operation in reassessment.operations)


def test_sequencer_recovery_marks_matching_range_already_applied():
    result = UnrealPlanExecutionResult(
        "sequencer-recovery:reassess-sequence",
        (_sequencer_evidence(10, 110), _material_evidence("wet_surface")),
        True,
    )
    assessment = assess_reassessment_sequence(_plan(), _failure(), result)
    by_name = {step.operation_name: step for step in assessment.steps}
    assert by_name["set_sequencer_playback_range"].disposition == "already_applied"
    assert by_name["set_sequencer_playback_range"].reason == "fresh Unreal state matches the requested state"


def test_sequencer_recovery_rebuilds_only_mismatched_range():
    result = UnrealPlanExecutionResult(
        "sequencer-recovery:reassess-sequence",
        (_sequencer_evidence(0, 100), _material_evidence("liquid_surface")),
        True,
    )
    assessment = assess_reassessment_sequence(_plan(), _failure(), result)
    assert assessment.disposition == "replacement_required"
    replacement = build_replacement_plan(_plan(), assessment)
    assert [operation.name for operation in replacement.operations] == [
        "set_sequencer_playback_range",
        "verify_sequencer_playback_range",
    ]
    assert replacement.operations[0].arguments["start_frame"] == 10
    assert replacement.operations[0].arguments["end_frame"] == 110
    assert replacement.operations[1].arguments["expected_start_frame"] == 10
    assert replacement.operations[1].arguments["expected_end_frame"] == 110


def test_composite_recovery_replaces_only_the_mismatched_prior_write():
    plan = UnrealTaskPlan("mixed-recovery", (
        UnrealOperation(
            UnrealCapability.SEQUENCER,
            UnrealOperationKind.WRITE,
            "set_sequencer_playback_range",
            {"entity_ids": ENTITY_IDS, "start_frame": 20, "end_frame": 120},
            ENTITY_IDS,
        ),
        UnrealOperation(
            UnrealCapability.MODIFY_ACTOR,
            UnrealOperationKind.WRITE,
            "set_actor_location",
            {"entity_ids": ENTITY_IDS, "location": {"x": 100.0, "y": 200.0, "z": 300.0}},
            ENTITY_IDS,
        ),
        UnrealOperation(
            UnrealCapability.MODIFY_ACTOR,
            UnrealOperationKind.VERIFY,
            "verify_actor_location",
            {"entity_ids": ENTITY_IDS, "expected_location": {"x": 100.0, "y": 200.0, "z": 300.0}},
            ENTITY_IDS,
        ),
    ))
    failure = UnrealPlanExecutionFailure(
        "mixed-recovery",
        2,
        "verify_actor_location",
        (),
        "simulated post-write failure",
        ENTITY_IDS,
        {"entity_ids": ENTITY_IDS, "expected_location": {"x": 100.0, "y": 200.0, "z": 300.0}},
        (),
    )
    result = UnrealPlanExecutionResult(
        "mixed-recovery:reassess-sequence",
        (
            UnrealEvidence(
                "inspect_sequencer_state",
                ENTITY_IDS,
                {"FIELD_SURFACE": {"entity_id": "FIELD_SURFACE", "sequencer": {"start_frame": 20, "end_frame": 120}}},
                "unreal-editor-atlas-transport",
            ),
            UnrealEvidence(
                "inspect_target_actors",
                ENTITY_IDS,
                {"FIELD_SURFACE": {"entity_id": "FIELD_SURFACE", "location": {"x": 0.0, "y": 0.0, "z": 0.0}}},
                "unreal-editor-atlas-transport",
            ),
        ),
        True,
    )

    assessment = assess_reassessment_sequence(plan, failure, result)
    assert [step.disposition for step in assessment.steps] == ["already_applied", "replacement_required"]

    replacement = build_replacement_plan(plan, assessment)
    assert [operation.name for operation in replacement.operations] == [
        "set_actor_location",
        "verify_actor_location",
    ]
    assert replacement.operations[0].arguments["location"] == {"x": 100.0, "y": 200.0, "z": 300.0}


class _TestUnrealTransport:
    """Transport déterministe pour les tests de récupération."""
    
    def __init__(self):
        self._responses = {}
    
    def set_response(self, plan_intent_id, result):
        """Configure la réponse pour un plan donné."""
        self._responses[plan_intent_id] = result
    
    def send_request(self, request):
        """Simule l'envoi d'une requête avec des réponses prédéfinies."""
        if not isinstance(request, UnrealTransportRequest):
            raise TypeError("request must be an UnrealTransportRequest instance")
        
        result = self._responses.get(request.plan.intent_id, UnrealPlanExecutionResult(request.plan.intent_id, (), False))
        return UnrealTransportResponse(request.plan.intent_id, result.evidence_ledger, result.success, None)


def _create_test_executor():
    """Crée un executor compatible UnrealPlanExecutor pour les tests."""
    transport = _TestUnrealTransport()
    return UnrealPlanExecutor(transport)


def test_replacement_required_without_authorization_fails_closed():
    """Une récupération Sequencer nécessitant un remplacement SANS autorisation doit échouer fermé."""
    plan = _plan()
    failure = _failure()
    executor = _create_test_executor()
    
    # Configure la réponse de réévaluation montrant un état non concordant
    reassessment_result = UnrealPlanExecutionResult(
        "sequencer-recovery:reassess-sequence",
        (_sequencer_evidence(0, 100), _material_evidence("wet_surface")),
        True,
    )
    executor.transport.set_response("sequencer-recovery:reassess-sequence", reassessment_result)
    
    reassessment_authorization = UnrealPlanAuthorization.issue(
        build_reassessment_plan(plan, failure), 
        "test-reassess-auth"
    )
    
    # Doit lever une exception car aucune autorisation de remplacement n'est fournie
    try:
        execute_recovery_sequence(executor, plan, failure, reassessment_authorization)
        assert False, "Expected ValueError for missing replacement authorization"
    except ValueError as e:
        assert "replacement_required recovery requires a separate replacement authorization" in str(e)


def test_replacement_required_with_wrong_authorization_fails_closed():
    """Une récupération Sequencer avec une autorisation pour un plan DIFFÉRENT doit échouer fermé."""
    plan = _plan()
    failure = _failure()
    executor = _create_test_executor()
    
    # Configure la réponse de réévaluation montrant un état non concordant
    reassessment_result = UnrealPlanExecutionResult(
        "sequencer-recovery:reassess-sequence",
        (_sequencer_evidence(0, 100), _material_evidence("wet_surface")),
        True,
    )
    executor.transport.set_response("sequencer-recovery:reassess-sequence", reassessment_result)
    
    reassessment_authorization = UnrealPlanAuthorization.issue(
        build_reassessment_plan(plan, failure), 
        "test-reassess-auth"
    )
    
    # Crée une autorisation pour un plan différent
    wrong_plan = UnrealTaskPlan("wrong-plan", (
        UnrealOperation(
            UnrealCapability.SEQUENCER,
            UnrealOperationKind.WRITE,
            "set_sequencer_playback_range",
            {"entity_ids": ENTITY_IDS, "start_frame": 999, "end_frame": 1999},  # Valeurs différentes
            ENTITY_IDS,
        ),
    ))
    wrong_authorization = UnrealPlanAuthorization.issue(wrong_plan, "wrong-auth")
    
    # Doit lever une exception car l'autorisation ne correspond pas au plan de remplacement
    try:
        execute_recovery_sequence(executor, plan, failure, reassessment_authorization, wrong_authorization)
        assert False, "Expected ValueError for mismatched replacement authorization"
    except ValueError as e:
        assert "authorization does not match the plan operations" in str(e)


def test_matching_replacement_authorization_allows_execution():
    """Une autorisation de remplacement correctement liée au plan doit permettre l'exécution Sequencer."""
    plan = _plan()
    failure = _failure()
    executor = _create_test_executor()
    
    # Configure la réponse de réévaluation montrant un état non concordant
    reassessment_result = UnrealPlanExecutionResult(
        "sequencer-recovery:reassess-sequence",
        (_sequencer_evidence(0, 100), _material_evidence("wet_surface")),
        True,
    )
    executor.transport.set_response("sequencer-recovery:reassess-sequence", reassessment_result)
    
    # Construit le plan de remplacement et son autorisation
    assessment = assess_reassessment_sequence(plan, failure, reassessment_result)
    replacement_plan = build_replacement_plan(plan, assessment)
    
    # Configure la réponse de remplacement réussie
    replacement_result = UnrealPlanExecutionResult(
        replacement_plan.intent_id,
        (
            _sequencer_evidence(10, 110),  # État final correct
            UnrealEvidence(
                "verify_sequencer_playback_range",
                ENTITY_IDS,
                {"FIELD_SURFACE": {"entity_id": "FIELD_SURFACE", "sequencer": {"start_frame": 10, "end_frame": 110}}},
                "unreal-editor-atlas-transport",
            ),
            _material_evidence("liquid_surface"),
            UnrealEvidence(
                "verify_material_variant",
                ENTITY_IDS,
                {"FIELD_SURFACE": {"entity_id": "FIELD_SURFACE", "material": {"variant": {"name": "liquid_surface"}}}},
                "unreal-editor-atlas-transport",
            ),
        ),
        True,
    )
    executor.transport.set_response(replacement_plan.intent_id, replacement_result)
    
    reassessment_authorization = UnrealPlanAuthorization.issue(
        build_reassessment_plan(plan, failure), 
        "test-reassess-auth"
    )
    replacement_authorization = issue_replacement_authorization(replacement_plan, "test-replace-auth")
    
    # Doit s'exécuter avec succès
    result = execute_recovery_sequence(
        executor, plan, failure, reassessment_authorization, replacement_authorization
    )
    
    assert result.replacement_plan is not None
    assert result.replacement_result is not None
    assert result.replacement_result.success


def test_successful_recovery_contains_replacement_plan_and_result():
    """Le résultat de récupération réussie doit contenir le plan de remplacement et le résultat réussi."""
    plan = _plan()
    failure = _failure()
    executor = _create_test_executor()
    
    # Configure la réponse de réévaluation montrant un état non concordant
    reassessment_result = UnrealPlanExecutionResult(
        "sequencer-recovery:reassess-sequence",
        (_sequencer_evidence(0, 100), _material_evidence("wet_surface")),
        True,
    )
    executor.transport.set_response("sequencer-recovery:reassess-sequence", reassessment_result)
    
    # Construit le plan de remplacement et son autorisation
    assessment = assess_reassessment_sequence(plan, failure, reassessment_result)
    replacement_plan = build_replacement_plan(plan, assessment)
    
    # Configure la réponse de remplacement réussie
    replacement_result = UnrealPlanExecutionResult(
        replacement_plan.intent_id,
        (
            _sequencer_evidence(10, 110),
            UnrealEvidence(
                "verify_sequencer_playback_range",
                ENTITY_IDS,
                {"FIELD_SURFACE": {"entity_id": "FIELD_SURFACE", "sequencer": {"start_frame": 10, "end_frame": 110}}},
                "unreal-editor-atlas-transport",
            ),
            _material_evidence("liquid_surface"),
            UnrealEvidence(
                "verify_material_variant",
                ENTITY_IDS,
                {"FIELD_SURFACE": {"entity_id": "FIELD_SURFACE", "material": {"variant": {"name": "liquid_surface"}}}},
                "unreal-editor-atlas-transport",
            ),
        ),
        True,
    )
    executor.transport.set_response(replacement_plan.intent_id, replacement_result)
    
    reassessment_authorization = UnrealPlanAuthorization.issue(
        build_reassessment_plan(plan, failure), 
        "test-reassess-auth"
    )
    replacement_authorization = issue_replacement_authorization(replacement_plan, "test-replace-auth")
    
    result = execute_recovery_sequence(
        executor, plan, failure, reassessment_authorization, replacement_authorization
    )
    
    # Vérifie que le résultat contient le plan et le résultat de remplacement
    assert result.replacement_plan is replacement_plan
    assert result.replacement_result is replacement_result
    assert result.replacement_result.success
    assert result.assessment.disposition == "replacement_required"


def test_replacement_result_contains_sequencer_write_then_verify():
    """Le résultat de remplacement doit contenir l'écriture Sequencer suivie immédiatement par verify_sequencer_playback_range."""
    plan = _plan()
    failure = _failure()
    executor = _create_test_executor()
    
    # Configure la réponse de réévaluation montrant un état non concordant
    reassessment_result = UnrealPlanExecutionResult(
        "sequencer-recovery:reassess-sequence",
        (_sequencer_evidence(0, 100), _material_evidence("wet_surface")),
        True,
    )
    executor.transport.set_response("sequencer-recovery:reassess-sequence", reassessment_result)
    
    # Construit le plan de remplacement et son autorisation
    assessment = assess_reassessment_sequence(plan, failure, reassessment_result)
    replacement_plan = build_replacement_plan(plan, assessment)
    
    # Vérifie que le plan de remplacement contient les opérations Sequencer dans l'ordre correct
    sequencer_ops = [op for op in replacement_plan.operations if op.capability == UnrealCapability.SEQUENCER]
    assert len(sequencer_ops) == 2
    assert sequencer_ops[0].name == "set_sequencer_playback_range"
    assert sequencer_ops[0].kind is UnrealOperationKind.WRITE
    assert sequencer_ops[1].name == "verify_sequencer_playback_range"
    assert sequencer_ops[1].kind is UnrealOperationKind.VERIFY
    
    # Vérifie que les opérations Sequencer sont consécutives dans le plan
    sequencer_indices = [i for i, op in enumerate(replacement_plan.operations) if op.capability == UnrealCapability.SEQUENCER]
    assert sequencer_indices[1] == sequencer_indices[0] + 1, "Sequencer WRITE and VERIFY must be consecutive"
    
    # Configure la réponse de remplacement avec toutes les opérations nécessaires
    replacement_result = UnrealPlanExecutionResult(
        replacement_plan.intent_id,
        (
            UnrealEvidence(
                "set_sequencer_playback_range",
                ENTITY_IDS,
                {"FIELD_SURFACE": {"entity_id": "FIELD_SURFACE", "sequencer": {"start_frame": 10, "end_frame": 110}}},
                "unreal-editor-atlas-transport",
            ),
            UnrealEvidence(
                "verify_sequencer_playback_range",
                ENTITY_IDS,
                {"FIELD_SURFACE": {"entity_id": "FIELD_SURFACE", "sequencer": {"start_frame": 10, "end_frame": 110}}},
                "unreal-editor-atlas-transport",
            ),
            UnrealEvidence(
                "apply_material_variant",
                ENTITY_IDS,
                {"FIELD_SURFACE": {"entity_id": "FIELD_SURFACE", "material": {"variant": {"name": "liquid_surface"}}}},
                "unreal-editor-atlas-transport",
            ),
            UnrealEvidence(
                "verify_material_variant",
                ENTITY_IDS,
                {"FIELD_SURFACE": {"entity_id": "FIELD_SURFACE", "material": {"variant": {"name": "liquid_surface"}}}},
                "unreal-editor-atlas-transport",
            ),
        ),
        True,
    )
    executor.transport.set_response(replacement_plan.intent_id, replacement_result)
    
    reassessment_authorization = UnrealPlanAuthorization.issue(
        build_reassessment_plan(plan, failure), 
        "test-reassess-auth"
    )
    replacement_authorization = issue_replacement_authorization(replacement_plan, "test-replace-auth")
    
    result = execute_recovery_sequence(
        executor, plan, failure, reassessment_authorization, replacement_authorization
    )
    
    # Vérifie que le résultat de remplacement contient les opérations Sequencer dans l'ordre
    sequencer_evidence = [ev for ev in result.replacement_result.evidence_ledger if "sequencer" in ev.operation_name]
    assert len(sequencer_evidence) == 2
    assert sequencer_evidence[0].operation_name == "set_sequencer_playback_range"
    assert sequencer_evidence[1].operation_name == "verify_sequencer_playback_range"
    
    # Vérifie les paramètres corrects
    write_evidence = sequencer_evidence[0]
    verify_evidence = sequencer_evidence[1]
    
    assert write_evidence.observed_state["FIELD_SURFACE"]["sequencer"]["start_frame"] == 10
    assert write_evidence.observed_state["FIELD_SURFACE"]["sequencer"]["end_frame"] == 110
    assert verify_evidence.observed_state["FIELD_SURFACE"]["sequencer"]["start_frame"] == 10
    assert verify_evidence.observed_state["FIELD_SURFACE"]["sequencer"]["end_frame"] == 110


def test_actor_scale_recovery_replacement_preserves_scale_operation_capability():
    plan = UnrealTaskPlan("scale-recovery", (
        UnrealOperation(
            UnrealCapability.MODIFY_ACTOR,
            UnrealOperationKind.WRITE,
            "set_actor_scale",
            {"entity_ids": ENTITY_IDS, "scale": {"x": 2.0, "y": 3.0, "z": 4.0}},
            ENTITY_IDS,
        ),
    ))
    failure = UnrealPlanExecutionFailure(
        "scale-recovery",
        0,  # Corrigé: index 0 pour la première (et seule) opération
        "set_actor_scale",
        (),
        "simulated post-write failure",
        ENTITY_IDS,
        {"entity_ids": ENTITY_IDS, "scale": {"x": 2.0, "y": 3.0, "z": 4.0}},
        (),
    )
    result = UnrealPlanExecutionResult(
        "scale-recovery:reassess-sequence",
        (
            UnrealEvidence(
                "inspect_target_actors",
                ENTITY_IDS,
                {"FIELD_SURFACE": {"entity_id": ENTITY_IDS[0], "scale": {"x": 1.0, "y": 1.0, "z": 1.0}}},
                "unreal-editor-atlas-transport",
            ),
        ),
        True,
    )

    assessment = assess_reassessment_sequence(plan, failure, result)
    assert assessment.disposition == "replacement_required"
    replacement = build_replacement_plan(plan, assessment)
    assert [operation.name for operation in replacement.operations] == [
        "set_actor_scale",
        "verify_actor_scale",
    ]
    assert replacement.operations[0].capability is UnrealCapability.MODIFY_ACTOR
    assert replacement.operations[1].capability is UnrealCapability.MODIFY_ACTOR
    assert replacement.operations[0].arguments["scale"] == {"x": 2.0, "y": 3.0, "z": 4.0}
    assert replacement.operations[1].arguments["expected_scale"] == {"x": 2.0, "y": 3.0, "z": 4.0}
