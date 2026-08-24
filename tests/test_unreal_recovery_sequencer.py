from planning.unreal_agent import UnrealCapability, UnrealOperation, UnrealOperationKind
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_plan_executor import UnrealPlanExecutionFailure, UnrealPlanExecutionResult, UnrealPlanExecutor, UnrealPlanExecutionError
from planning.unreal_recovery_sequence import (
    assess_reassessment_sequence, 
    build_reassessment_plan, 
    build_replacement_plan,
    execute_recovery_sequence,
    issue_replacement_authorization
)
from planning.unreal_task_planner import UnrealTaskPlan
from planning.unreal_transport_contract import UnrealTransportRequest, UnrealTransportResponse
from planning.unreal_adapter_production import UnrealAdapterProduction


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
        {"FIELD_SURFACE": {"entity_id": "FIELD_SURFACE", "sequencer": {"playback_range": {"start_frame": start_frame, "end_frame": end_frame}}}},
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
        self._auth_responses = {}
        self._current_authorization_id = None
    
    def set_response(self, plan_intent_id, result):
        """Configure la réponse pour un plan donné."""
        self._responses[plan_intent_id] = result
    
    def set_response_for_auth(self, authorization_id, result):
        """Configure la réponse pour un authorization_id spécifique."""
        self._auth_responses[authorization_id] = result
    
    def send(self, request):
        """Simule l'envoi d'une requête avec des réponses prédéfinies."""
        if not isinstance(request, UnrealTransportRequest):
            raise TypeError("request must be an UnrealTransportRequest instance")
        
        # Utilise l'authorization_id pour déterminer le contexte d'exécution
        self._current_authorization_id = request.authorization_id
        
        # D'abord, cherche une réponse configurée explicitement pour cet authorization_id
        result = None
        if request.authorization_id in self._auth_responses:
            auth_result = self._auth_responses[request.authorization_id]
            # Vérifie si cette réponse contient l'opération demandée
            for evidence in auth_result.evidence_ledger:
                if (evidence.operation_name == request.operation_name and 
                    tuple(evidence.entity_ids) == tuple(request.entity_ids)):
                    result = auth_result
                    break
        
        # Si pas de correspondance par authorization_id, utilise la logique plan_intent_id existante
        if result is None:
            for plan_id, stored_result in self._responses.items():
                for evidence in stored_result.evidence_ledger:
                    if (evidence.operation_name == request.operation_name and 
                        tuple(evidence.entity_ids) == tuple(request.entity_ids)):
                        result = stored_result
                        break
                if result:
                    break
        
        if result is None:
            # Retourne une réponse d'échec par défaut
            return UnrealTransportResponse(
                request_id=request.request_id,
                operation_name=request.operation_name,
                entity_ids=request.entity_ids,
                success=False,
                observed_state={},
                error="No configured response found",
                source="test-unreal-transport"
            )
        
        # Trouve l'evidence spécifique pour cette opération
        matching_evidence = None
        for evidence in result.evidence_ledger:
            if (evidence.operation_name == request.operation_name and 
                tuple(evidence.entity_ids) == tuple(request.entity_ids)):
                matching_evidence = evidence
                break
        
        if matching_evidence is None:
            # Utilise la première evidence comme fallback
            matching_evidence = result.evidence_ledger[0] if result.evidence_ledger else None
        
        return UnrealTransportResponse(
            request_id=request.request_id,
            operation_name=request.operation_name,
            entity_ids=request.entity_ids,
            success=result.success,
            observed_state=matching_evidence.observed_state if matching_evidence else {},
            error="",
            source="test-unreal-transport"
        )


def _create_test_executor():
    """Crée un executor compatible UnrealPlanExecutor pour les tests."""
    transport = _TestUnrealTransport()
    adapter = UnrealAdapterProduction(transport)
    executor = UnrealPlanExecutor(adapter)
    return executor, transport


def test_replacement_required_without_authorization_fails_closed():
    """Une récupération Sequencer nécessitant un remplacement SANS autorisation doit échouer fermé."""
    plan = _plan()
    failure = _failure()
    executor, transport = _create_test_executor()
    
    # Configure la réponse de réévaluation montrant un état non concordant
    reassessment_result = UnrealPlanExecutionResult(
        "sequencer-recovery:reassess-sequence",
        (_sequencer_evidence(0, 100), _material_evidence("wet_surface")),
        True,
    )
    transport.set_response("sequencer-recovery:reassess-sequence", reassessment_result)
    
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
    executor, transport = _create_test_executor()
    
    # Configure la réponse de réévaluation montrant un état non concordant
    reassessment_result = UnrealPlanExecutionResult(
        "sequencer-recovery:reassess-sequence",
        (_sequencer_evidence(0, 100), _material_evidence("wet_surface")),
        True,
    )
    transport.set_response("sequencer-recovery:reassess-sequence", reassessment_result)
    
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
        assert False, "Expected UnrealPlanExecutionError for mismatched replacement authorization"
    except UnrealPlanExecutionError as e:
        assert "authorization receipt does not match the exact Unreal task plan" in str(e)


def test_matching_replacement_authorization_allows_execution():
    """Une autorisation de remplacement correctement liée au plan doit permettre l'exécution Sequencer."""
    plan = _plan()
    failure = _failure()
    executor, transport = _create_test_executor()
    
    # Configure la réponse de réévaluation montrant un état non concordant
    reassessment_result = UnrealPlanExecutionResult(
        "sequencer-recovery:reassess-sequence",
        (_sequencer_evidence(0, 100), _material_evidence("wet_surface")),
        True,
    )
    transport.set_response("sequencer-recovery:reassess-sequence", reassessment_result)
    
    # Construit le plan de remplacement et son autorisation
    assessment = assess_reassessment_sequence(plan, failure, reassessment_result)
    replacement_plan = build_replacement_plan(plan, assessment)
    
    # Configure la réponse de remplacement réussie
    replacement_result = UnrealPlanExecutionResult(
        replacement_plan.intent_id,
        (
            UnrealEvidence(
                "set_sequencer_playback_range",
                ENTITY_IDS,
                {"FIELD_SURFACE": {"entity_id": "FIELD_SURFACE", "sequencer": {"playback_range": {"start_frame": 10, "end_frame": 110}}}},
                "unreal-editor-atlas-transport",
            ),
            UnrealEvidence(
                "verify_sequencer_playback_range",
                ENTITY_IDS,
                {"FIELD_SURFACE": {"entity_id": "FIELD_SURFACE", "sequencer": {"playback_range": {"start_frame": 10, "end_frame": 110}}}},
                "unreal-editor-atlas-transport",
            ),
            UnrealEvidence(
                "apply_material_variant",
                ENTITY_IDS,
                {"FIELD_SURFACE": {"entity_id": "FIELD_SURFACE", "material": {"variant": {"name": "liquid_surface"}}}},
                "unreal-editor-atlas-transport",
            ),
            UnrealEvidence(
                "inspect_material_state",
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
    transport.set_response(replacement_plan.intent_id, replacement_result)
    
    reassessment_authorization = UnrealPlanAuthorization.issue(
        build_reassessment_plan(plan, failure), 
        "test-reassess-auth"
    )
    replacement_authorization = issue_replacement_authorization(replacement_plan, "test-replace-auth")
    
    # Configure la réponse de remplacement pour l'authorization_id spécifique
    transport.set_response_for_auth("test-replace-auth", replacement_result)
    
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
    executor, transport = _create_test_executor()
    
    # Configure la réponse de réévaluation montrant un état non concordant
    reassessment_result = UnrealPlanExecutionResult(
        "sequencer-recovery:reassess-sequence",
        (_sequencer_evidence(0, 100), _material_evidence("wet_surface")),
        True,
    )
    transport.set_response("sequencer-recovery:reassess-sequence", reassessment_result)
    
    # Construit le plan de remplacement et son autorisation
    assessment = assess_reassessment_sequence(plan, failure, reassessment_result)
    replacement_plan = build_replacement_plan(plan, assessment)
    
    # Configure la réponse de remplacement réussie
    replacement_result = UnrealPlanExecutionResult(
        replacement_plan.intent_id,
        (
            UnrealEvidence(
                "set_sequencer_playback_range",
                ENTITY_IDS,
                {"FIELD_SURFACE": {"entity_id": "FIELD_SURFACE", "sequencer": {"playback_range": {"start_frame": 10, "end_frame": 110}}}},
                "unreal-editor-atlas-transport",
            ),
            UnrealEvidence(
                "verify_sequencer_playback_range",
                ENTITY_IDS,
                {"FIELD_SURFACE": {"entity_id": "FIELD_SURFACE", "sequencer": {"playback_range": {"start_frame": 10, "end_frame": 110}}}},
                "unreal-editor-atlas-transport",
            ),
            UnrealEvidence(
                "apply_material_variant",
                ENTITY_IDS,
                {"FIELD_SURFACE": {"entity_id": "FIELD_SURFACE", "material": {"variant": {"name": "liquid_surface"}}}},
                "unreal-editor-atlas-transport",
            ),
            UnrealEvidence(
                "inspect_material_state",
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
    transport.set_response(replacement_plan.intent_id, replacement_result)
    
    reassessment_authorization = UnrealPlanAuthorization.issue(
        build_reassessment_plan(plan, failure), 
        "test-reassess-auth"
    )
    replacement_authorization = issue_replacement_authorization(replacement_plan, "test-replace-auth")
    
    # Configure la réponse de remplacement pour l'authorization_id spécifique
    transport.set_response_for_auth("test-replace-auth", replacement_result)
    
    result = execute_recovery_sequence(
        executor, plan, failure, reassessment_authorization, replacement_authorization
    )
    
    # Vérifie que le résultat contient le plan et le résultat de remplacement
    assert result.replacement_plan == replacement_plan
    
    # Vérifie les propriétés du résultat de remplacement
    assert result.replacement_result is not None
    assert result.replacement_result.success
    assert result.replacement_result.intent_id == replacement_plan.intent_id
    
    # Vérifie que les opérations Sequencer ont été exécutées
    sequencer_evidence = [ev for ev in result.replacement_result.evidence_ledger if "sequencer" in ev.operation_name]
    assert len(sequencer_evidence) == 2
    assert sequencer_evidence[0].operation_name == "set_sequencer_playback_range"
    assert sequencer_evidence[1].operation_name == "verify_sequencer_playback_range"
    assert sequencer_evidence[1].verified is True
    
    # Vérifie que les opérations Material ont été exécutées
    material_evidence = [ev for ev in result.replacement_result.evidence_ledger if "material" in ev.operation_name]
    assert len(material_evidence) == 2
    assert material_evidence[0].operation_name == "apply_material_variant"
    assert material_evidence[1].operation_name == "verify_material_variant"
    assert material_evidence[1].verified is True
    
    # Vérifie que l'état final correspond aux valeurs attendues
    sequencer_state = sequencer_evidence[1].observed_state["FIELD_SURFACE"]["sequencer"]["playback_range"]
    assert sequencer_state["start_frame"] == 10
    assert sequencer_state["end_frame"] == 110
    
    material_state = material_evidence[1].observed_state["FIELD_SURFACE"]["material"]["variant"]
    assert material_state["name"] == "liquid_surface"
    
    assert result.assessment.disposition == "replacement_required"


def test_replacement_result_contains_sequencer_write_then_verify():
    """Le résultat de remplacement doit contenir l'écriture Sequencer suivie immédiatement par verify_sequencer_playback_range."""
    plan = _plan()
    failure = _failure()
    executor, transport = _create_test_executor()
    
    # Configure la réponse de réévaluation montrant un état non concordant
    reassessment_result = UnrealPlanExecutionResult(
        "sequencer-recovery:reassess-sequence",
        (_sequencer_evidence(0, 100), _material_evidence("wet_surface")),
        True,
    )
    transport.set_response("sequencer-recovery:reassess-sequence", reassessment_result)
    
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
                {"FIELD_SURFACE": {"entity_id": "FIELD_SURFACE", "sequencer": {"playback_range": {"start_frame": 10, "end_frame": 110}}}},
                "unreal-editor-atlas-transport",
            ),
            UnrealEvidence(
                "verify_sequencer_playback_range",
                ENTITY_IDS,
                {"FIELD_SURFACE": {"entity_id": "FIELD_SURFACE", "sequencer": {"playback_range": {"start_frame": 10, "end_frame": 110}}}},
                "unreal-editor-atlas-transport",
            ),
            UnrealEvidence(
                "apply_material_variant",
                ENTITY_IDS,
                {"FIELD_SURFACE": {"entity_id": "FIELD_SURFACE", "material": {"variant": {"name": "liquid_surface"}}}},
                "unreal-editor-atlas-transport",
            ),
            UnrealEvidence(
                "inspect_material_state",
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
    transport.set_response(replacement_plan.intent_id, replacement_result)
    
    reassessment_authorization = UnrealPlanAuthorization.issue(
        build_reassessment_plan(plan, failure), 
        "test-reassess-auth"
    )
    replacement_authorization = issue_replacement_authorization(replacement_plan, "test-replace-auth")
    
    # Configure la réponse de remplacement pour l'authorization_id spécifique
    transport.set_response_for_auth("test-replace-auth", replacement_result)
    
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
    
    assert write_evidence.observed_state["FIELD_SURFACE"]["sequencer"]["playback_range"]["start_frame"] == 10
    assert write_evidence.observed_state["FIELD_SURFACE"]["sequencer"]["playback_range"]["end_frame"] == 110
    assert verify_evidence.observed_state["FIELD_SURFACE"]["sequencer"]["playback_range"]["start_frame"] == 10
    assert verify_evidence.observed_state["FIELD_SURFACE"]["sequencer"]["playback_range"]["end_frame"] == 110


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
