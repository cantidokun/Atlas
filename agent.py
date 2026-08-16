import requests
import json
import difflib
import re

from tools import TOOLS



OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:8b"

# ============================================================
# CURRENT TASK
# ============================================================
# Keep the task definition in one place. Controller recovery
# messages must reinforce this task, never replace it.
CURRENT_TASK = (
    "Inspect goalpost_test.blend.\n\n"
    "The explicit requirement is that the midpoint between "
    "Goal_Left_post and Goal_Right_Post must be exactly "
    "[0.0, 0.0, 0.0].\n\n"
    "You are explicitly authorized to modify the Blender file "
    "to satisfy this requirement.\n\n"
    "Before modifying the file:\n"
    "1. Inspect the current positions of both objects.\n"
    "2. Determine whether the requirement is satisfied.\n"
    "3. Calculate the exact modification required.\n\n"
    "If the requirement is not satisfied, you are authorized "
    "to execute the necessary Blender modification.\n\n"
    "After the modification:\n"
    "4. Re-inspect the objects using a read-only inspection tool.\n"
    "5. Verify that the midpoint is exactly [0.0, 0.0, 0.0].\n"
    "6. Report the before state, modification performed, and "
    "verified after state.\n\n"
    "Do not introduce soccer regulations, standard dimensions, "
    "or any other requirements not provided in this task.\n\n"
    "The explicit authorization in this task permits the write "
    "operation. Do not treat the modification as merely theoretical."
)



# ============================================================
# TOOL DEFINITIONS
# ============================================================

tool_definitions = [

    {
        "type": "function",
        "function": {
            "name": "inspect_scene",
            "description": (
                "Inspect a Blender project inside the Atlas "
                "directory. Returns objects, types, locations "
                "and dimensions. Read-only."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {"type": "string"}
                },
                "required": ["file_name"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "inspect_mesh",
            "description": (
                "Inspect a specific mesh inside a Blender "
                "project. Returns vertices, edges, polygons, "
                "materials and modifiers. Read-only."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {"type": "string"},
                    "object_name": {"type": "string"}
                },
                "required": ["file_name", "object_name"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "inspect_scene_health",
            "description": (
                "Assess the overall complexity of a Blender "
                "project using geometry, object, material "
                "and modifier statistics. Read-only."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {"type": "string"}
                },
                "required": ["file_name"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "inspect_scene_settings",
            "description": (
                "Inspect Blender scene configuration including "
                "unit system, unit scale, render engine, render "
                "resolution, frame rate, frame range, active "
                "camera, collections and world settings. "
                "Read-only."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {"type": "string"}
                },
                "required": ["file_name"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "inspect_object_relationship",
            "description": (
                "Measure the spatial relationship between two "
                "Blender objects. Returns locations, dimensions, "
                "coordinate deltas, distance, midpoint, whether "
                "dimensions match, and axis alignment. Read-only. "
                "Use this tool for spatial relationship measurements "
                "instead of calculating them from raw coordinates."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {"type": "string"},
                    "object1_name": {"type": "string"},
                    "object2_name": {"type": "string"}
                },
                "required": [
                    "file_name",
                    "object1_name",
                    "object2_name"
                ]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "inspect_soccer_components",
            "description": (
                "Inspect a Blender project and identify conservative "
                "soccer-field component candidates using object-name "
                "keyword evidence. Returns candidate classifications, "
                "the exact object names, object types, locations, "
                "dimensions, and the matched name terms. This is "
                "read-only. Candidate classifications are not proof "
                "of the object's intended function."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {"type": "string"}
                },
                "required": ["file_name"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "create_collection",
            "description": (
                "Create the collection named Atlas_Test in a "
                "Blender project. This is a narrowly scoped "
                "write operation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {"type": "string"},
                    "collection_name": {
                        "type": "string",
                        "enum": ["Atlas_Test"]
                    }
                },
                "required": ["file_name", "collection_name"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "create_empty_marker",
            "description": (
                "Create the single permitted Atlas test marker "
                "object named Atlas_Marker inside the existing "
                "Atlas_Test collection. This tool cannot create "
                "any other object or use any other collection."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {"type": "string"},
                    "collection_name": {
                        "type": "string",
                        "enum": ["Atlas_Test"]
                    },
                    "object_name": {
                        "type": "string",
                        "enum": ["Atlas_Marker"]
                    }
                },
                "required": [
                    "file_name",
                    "collection_name",
                    "object_name"
                ]
            }
        }
    }
,

    {
        "type": "function",
        "function": {
            "name": "move_object",
            "description": (
                "Move one of the two explicitly authorized goalpost "
                "objects to an exact world-space location and save the "
                "Blender file. This is a write operation. Only "
                "Goal_Left_post and Goal_Right_Post may be moved by this "
                "tool."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {"type": "string"},
                    "object_name": {
                        "type": "string",
                        "enum": ["Goal_Left_post", "Goal_Right_Post"]
                    },
                    "location": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 3,
                        "maxItems": 3
                    }
                },
                "required": ["file_name", "object_name", "location"]
            }
        }
    }

]


# ============================================================
# SYSTEM INSTRUCTIONS
# ============================================================

messages = [
    {
        "role": "system",
        "content": (
            "You are Atlas, an environment acquisition agent.\n\n"
            "FACTUALITY RULES:\n"
"GENERAL EVIDENCE PLANNER PROTOCOL:\n"
"When you identify a specific evidence gap that must be resolved before finalizing,\n"
"you may request evidence using this exact structured block:\n"
"ATLAS_EVIDENCE_REQUESTS:\n"
"[\n"
"  {\n"
"    \"tool\": \"EXACT_TOOL_NAME\",\n"
"    \"arguments\": {\n"
"      \"exact_parameter\": \"value\"\n"
"    }\n"
"  }\n"
"]\n"
"Use only tools from the provided tool definitions and exact parameter names.\n"
"Do not request evidence already established in the evidence ledger.\n"
"If no additional evidence is required, do not emit this block.\n"


"1. Only state facts supported by tool results "
"or user instructions.\n"

"2. Never invent measurements, object types, "
"scores, settings, or capabilities.\n"

"3. Clearly distinguish measured facts from "
"recommendations.\n"

"4. If information is unavailable, say so.\n"

"5. Prefer tools over guessing. If a required fact "
"can be verified by an available tool, use that tool "
"before reaching a conclusion. To determine whether "
"a Blender collection exists, use inspect_scene_settings. "
"The inspect_scene tool does not return collection "
"information.\n"

"6. After a modification, verify it with a "
"separate inspection step.\n"

"7. Never claim that nothing else changed unless "
"a tool actually provides evidence for that claim.\n"

"8. When evaluating an asset, distinguish between "
"what the tools measured and what you infer.\n"

"9. Do not recommend optimization merely because "
"an asset has geometry.\n"

"10. When the available data is insufficient, "
"say what additional information is needed.\n"

"11. Never recommend a change merely because it is "
"a common 3D workflow practice. Tie it to evidence "
"or an explicit user requirement.\n"

"12. Do not describe a material, modifier, object, "
"or geometry characteristic unless a tool provides it.\n"

"13. Do not assume more geometry, materials, or "
"modifiers are inherently better.\n"

"14. When no problem is demonstrated, say so.\n"

"15. Never use the word 'assume', 'assumed', or "
"equivalent language to fill missing tool information. "
"If a fact was not measured or provided by the user, "
"state that it was not verified.\n"

"16. Do not claim an object was not modified unless "
"the relevant tool execution or verification provides "
"evidence for that claim.\n"

"17. Never treat missing tool output as evidence that "
"an object, property, component, or feature is absent. "
"If the available tools can verify the missing "
"information, use the appropriate tool before reaching "
"a conclusion.\n"

"18. If a conclusion depends on information that has "
"not been verified and no available tool can verify it, "
"explicitly state that the conclusion cannot be "
"established from the available evidence.\n"

"19. Do not infer that a Blender asset is incomplete "
"merely because expected soccer-field components are "
"not present in the inspection results. The intended "
"scope or completeness of the asset must first be "
"established by the user or by available tool evidence.\n"

"20. Do not convert general domain knowledge into a "
"measured claim. General knowledge may be used to "
"explain or interpret verified observations, but it "
"must not be used to establish that an object, "
"component, or feature exists, is missing, or is "
"incorrect unless the available evidence supports "
"that conclusion.\n"

"21. If a tool reports that a requested Blender object "
"cannot be found, do not conclude that the object does "
"not exist. Use inspect_scene to obtain the authoritative "
"object names before reporting the object as absent, "
"when inspect_scene is available.\n"

"22. Blender object names are case-sensitive. Preserve "
"object names exactly as returned by tool results and "
"do not alter capitalization, underscores, or spelling "
"when passing an object name to another tool.\n"

"23. When a relationship tool provides an explicit "
"boolean or classification, use that result as "
"authoritative. Do not contradict a tool-reported "
"classification with an inference from the raw "
"coordinates.\n"

"24. Do not describe two objects as symmetric unless "
"the relationship tool explicitly reports "
"symmetric_about_origin as true. A midpoint near the "
"origin does not establish exact symmetry.\n"

"25. Do not describe an axis as vertical, horizontal, "
"forward, up, down, or another semantic direction unless "
"the available tool data explicitly establishes the "
"scene's coordinate convention. Report the coordinate "
"axis itself when that is what the evidence establishes.\n"

"26. When an objective geometric classification is "
"available, report the classification directly and do "
"not replace it with softer or contradictory language. "
"For example, if symmetric_about_origin is false, state "
"that the objects are not symmetric about the world "
"origin. Do not describe them as 'symmetrical', "
"'near-symmetrical', 'approximately symmetric', or "
"equivalent unless the tool explicitly provides such "
"a classification.\n"

"27. If the user asks about the spatial relationship "
"between two named Blender objects, you MUST use "
"inspect_object_relationship before answering. Do not "
"answer the relationship question from inspect_scene "
"data alone.\n"

"28. If inspect_object_relationship is available and "
"the question asks about distance, midpoint, alignment, "
"symmetry, relative position, dimensional equality, or "
"spatial coherence between two objects, the relationship "
"tool is mandatory. Do not state that this information "
"is unavailable until the relationship tool has been "
"executed.\n"

"29. Do not state that a tool does not provide a "
"measurement unless that tool has actually been executed "
"and its returned result does not contain the requested "
"measurement.\n"

"30. Use the exact parameter names shown in the tool "
"definition. For inspect_object_relationship, the "
"required parameters are file_name, object1_name, and "
"object2_name. Do not invent alternate parameter names.\n"

"31. If a required tool is available and necessary to "
"answer the user's question, do not provide a final "
"answer until that tool has been successfully executed "
"and its result has been considered.\n"

"32. When inspect_object_relationship returns an "
"'Object not found' error, do not end the task and do "
"not ask the user to verify the name immediately. First "
"call inspect_scene to obtain the authoritative list of "
"object names. Compare the requested name with the "
"returned names, then retry inspect_object_relationship "
"using the exact name returned by inspect_scene if the "
"intended object can be identified. Only report that the "
"object cannot be found after this recovery procedure "
"has been attempted.\n"

"33. Do not infer functional intent from geometric similarity "
"alone. Identical dimensions, alignment, proximity, or symmetry "
"may establish a geometric relationship but do not establish "
"what the objects are intended to do.\n"

"34. Do not describe an object relationship as functional, "
"intentional, appropriate, correct, valid, or coherent unless "
"that conclusion is supported by explicit user requirements "
"or tool-provided evidence. When only geometric evidence is "
"available, describe the geometric relationship without "
"assigning functional meaning.\n"

"35. When a tool provides both an objective measurement and an "
"objective classification, report both without adding an "
"unsupported causal explanation. For example, if "
"symmetric_about_origin is false and midpoint_offset_from_origin "
"is 0.138, report those facts without attributing the offset "
"to rounding, intentional placement, error, or design choice "
"unless evidence supports that explanation.\n"

"36. Do not translate coordinate values into semantic spatial "
"directions such as 'above', 'below', 'vertical', 'horizontal', "
"'left', or 'right' unless the available tool data explicitly "
"establishes the relevant coordinate convention. When that "
"information is unavailable, report the coordinate values "
"directly.\n"

"37. When reporting a spatial relationship, use the coordinate "
"axis names returned by the tool (X, Y, Z) rather than "
"semantic directional terms such as horizontal, vertical, "
"above, below, left, or right unless the coordinate convention "
"has been explicitly verified. When describing the significance "
"of a relationship, distinguish geometric consistency from "
"functional or semantic intent.\n"

"38. When reporting that components were not identified, "
"distinguish between 'no candidates were identified' and "
"'no components exist.' If some candidates were identified, "
"state 'no additional candidates were identified' rather than "
"saying that no components were identified.\n"

"39. Do not claim that a file was unmodified unless a relevant "
"verification provides evidence of the file state. If only "
"read-only tools were executed, state that no write operation "
"was executed rather than claiming that the file was unchanged.\n"

"40. When an assessment cannot establish a requested property, "
"identify the specific missing evidence and, when an available "
"tool can obtain that evidence, identify the appropriate next "
"inspection. Do not treat the missing evidence itself as proof "
"that the property is absent or incorrect.\n"
"41. Do not recommend repeating a tool solely to obtain evidence "
"that the same tool has already returned during the current "
"assessment, unless the scene may have changed or the user "
"explicitly requests a repeat inspection. A repeated inspection "
"must have a stated evidence-based reason.\n"
"42. When recommending a next inspection, select it based on "
"the documented capabilities of the available tool. Do not "
"recommend a tool for information that its demonstrated output "
"cannot establish. Do not introduce new categories of objects "
"or properties as inspection targets unless an available tool "
"supports identifying or measuring them.\n"
"43. Before recommending a next inspection, compare the "
"unestablished information against the evidence already obtained "
"and the capabilities of the available tools. If no available "
"tool can resolve the evidence gap, explicitly state that the "
"gap requires a new capability rather than recommending an "
"existing tool that cannot resolve it.\n"
"44. Successful tool results are recorded in the Atlas evidence "
"ledger. Treat information contained in the ledger as established "
"evidence for the current assessment. Do not later describe "
"ledger-supported information as unestablished.\n"
"45. Before recommending or executing another inspection, check "
"the Atlas evidence ledger. Do not repeat an inspection solely "
"to obtain information already present in the ledger unless the "
"scene may have changed or the user explicitly requests a repeat "
"inspection.\n"
"46. Do not introduce real-world standards, specifications, "
"recommended dimensions, tolerances, or threshold values into "
"an asset assessment unless they are explicitly provided by the "
"user, returned by a tool, or obtained from an explicitly "
"requested external source. Do not use general domain knowledge "
"to create an acceptance criterion.\n"


            "RELATIONSHIP MEASUREMENT RULE: When a question concerns "
            "distance, midpoint, coordinate deltas, dimensional "
            "equality, axis alignment, symmetry, or another spatial "
            "relationship between objects, use "
            "inspect_object_relationship rather than calculating the "
            "measurement yourself. Treat the tool's measurements "
            "and classifications as the authoritative geometric "
            "evidence. Do not describe objects as symmetric about "
            "the world origin unless the tool reports "
            "symmetric_about_origin as true. Treat terms such as "
            "'coherent pair' or 'functional relationship' as "
            "interpretations, not measured properties.\n\n"
            "SOCCER COMPONENT CLASSIFICATION RULE:\n"
            "When using inspect_soccer_components, treat every "
            "classification as a candidate based on the tool's "
            "reported name evidence, not as proof of intended "
            "function. Report the exact candidate classification "
            "and matched terms. Do not upgrade a candidate into a "
            "confirmed soccer component without additional evidence.\n\n"
            "TOOL EXECUTION RULE:\n"
            "When you request a tool, wait for its result before "
            "deciding what to do next. Only one tool call is "
            "executed per reasoning cycle. After a write, use "
            "a separate reasoning cycle to verify the result.\n"
            "TASK-DRIVEN INSPECTION RULE:\n"
            "Do not execute a tool merely because it is available or "
            "because an earlier assessment used it. Select tools based "
            "on the current user task and the evidence needed to answer "
            "that task. inspect_soccer_components is not globally "
            "mandatory; use it only when the current task requires "
            "soccer-component candidate identification.\n"
            "AUTHORIZED MODIFICATION RULE:\n"
            "When the task explicitly authorizes a modification and "
            "the evidence shows the requested state is not satisfied, "
            "you MUST use the specific write tool capable of making that "
            "modification. For the current midpoint task, that tool is "
            "move_object. Do not substitute create_collection, "
            "create_empty_marker, or an unrelated inspection. Move both "
            "authorized goalpost objects to their required target "
            "locations, then perform a separate read-only verification.\n"            "NO-ACTION RULE:\n"
            "When the user explicitly says not to modify the file "
            "under a stated condition, obey that condition. If "
            "the condition for a modification is not met, do not "
            "call any write tool."
        )
    },
    {
        "role": "user",
        "content": CURRENT_TASK
    }
]
# ============================================================
# ATLAS EVIDENCE LEDGER
# ============================================================

evidence_ledger = []

# ============================================================
# FINAL-ANSWER EVIDENCE VALIDATOR
# ============================================================

def validate_final_answer(content, evidence_ledger):
    """
    Check the proposed final answer for a small set of direct
    contradictions with authoritative tool evidence and explicit
    current-task constraints.

    This validator does not attempt to judge writing quality or
    infer arbitrary factual errors. It only rejects claims that
    can be directly checked against the evidence ledger.
    """

    violations = []
    lower = content.lower()

    relationship_result = None
    soccer_result = None

    for item in evidence_ledger:
        if item["tool"] == "inspect_object_relationship":
            relationship_result = item["result"]
        elif item["tool"] == "inspect_soccer_components":
            soccer_result = item["result"]

    # --------------------------------------------------------
    # Relationship evidence checks
    # --------------------------------------------------------

    if isinstance(relationship_result, dict):

        symmetric = relationship_result.get(
            "symmetric_about_origin"
        )

        if symmetric is False:
            # Reject claims that specifically assert symmetry about
            # the world origin. Do not reject neutral geometric
            # descriptions such as "aligned along the Y-axis" or
            # "symmetrically named" when they do not assert origin
            # symmetry.
            positive_symmetry_patterns = [
                r"\bsymmetric around the origin\b",
                r"\bsymmetric about the origin\b",
                r"\bsymmetrical around the origin\b",
                r"\bsymmetrical about the origin\b",
                r"\bsymmetric relative to the origin\b",
                r"\bsymmetrical relative to the origin\b",
                r"\bpositions? (?:are|is) symmetric\b",
                r"\bpositions? (?:are|is) symmetrical\b",
                r"\bthey (?:are|form) symmetric\b",
                r"\bthey (?:are|form) symmetrical\b",
                r"^\s*symmetry\s*:\s*(?:yes|true|confirmed|present)\b",
            ]

            # Explicit negative formulations are allowed. Remove
            # those sentences before checking broad positive forms.
            sentences = re.split(r"(?<=[.!?])\s+", lower)
            positive_symmetry_text = " ".join(
                sentence
                for sentence in sentences
                if not re.search(
                    r"\b(?:not|no|false|without|lack(?:s|ing)?|isn't|aren't)\b"
                    r".*\bsymmetr(?:y|ic|ical)\b",
                    sentence
                )
            )

            for pattern in positive_symmetry_patterns:
                if re.search(
                    pattern,
                    positive_symmetry_text,
                    re.MULTILINE
                ):
                    violations.append(
                        "The relationship tool reports "
                        "symmetric_about_origin=false, but the final "
                        "answer makes a positive symmetry claim."
                    )
                    break

    # --------------------------------------------------------
    # Candidate-only checks
    # --------------------------------------------------------

    if isinstance(soccer_result, dict):
        classification_status = soccer_result.get(
            "classification_status"
        )

        if classification_status == "candidate_only":
            # Reject positive confirmation claims, but allow the model
            # to explicitly say that confirmation is absent, e.g.
            # "not confirmed" or "does not confirm".
            candidate_confirmation_patterns = [
                r"\b(?:the|these|those)\s+(?:objects?|candidates?)\s+"
                r"\bare\s+(?:confirmed|verified)\s+(?:functional\s+)?"
                r"(?:goalposts?|soccer(?:-field)?\s+components?)\b",
                r"\bconfirmed\s+(?:functional\s+)?"
                r"(?:goalposts?|soccer(?:-field)?\s+components?)\b",
                r"\b(?:goalposts?|soccer(?:-field)?\s+components?)\b"
                r"\s+(?:are|were)\s+confirmed\b",
                r"\b(?:goalposts?|soccer(?:-field)?\s+components?)\b"
                r"\s+(?:are|were)\s+verified\b",
            ]

            # Evaluate sentence-by-sentence so phrases such as
            # "not confirmed as functional soccer components" are
            # explicitly permitted.
            sentences = re.split(r"(?<=[.!?])\s+", lower)

            for sentence in sentences:
                if re.search(
                    r"\b(?:not|never|no|without|does not|do not|isn't|aren't)\b"
                    r".*\bconfirm(?:ed|s|ing)?\b",
                    sentence
                ):
                    continue

                for pattern in candidate_confirmation_patterns:
                    if re.search(pattern, sentence, re.MULTILINE):
                        violations.append(
                            "The soccer-component tool reports "
                            "classification_status=candidate_only. The "
                            "answer must not present the candidates as "
                            "confirmed functional soccer components."
                        )
                        break

                if violations:
                    break

    # --------------------------------------------------------
    # Unsupported current-task domain claims
    # --------------------------------------------------------

    unsupported_configuration_patterns = [
        r"\bvalid soccer[- ]field configuration\b",
        r"\bvalid soccer configuration\b",
        r"\bcommon setup for opposing goalposts\b",
        r"\bstandard soccer\b",
        r"\bstandard goal\b",
    ]

    for pattern in unsupported_configuration_patterns:
        if re.search(pattern, lower, re.MULTILINE):
            violations.append(
                "The answer introduces a soccer-domain standard or "
                "validity claim that is not established by the "
                "available tool evidence or user requirements."
            )
            break

    return violations



# ============================================================
# GENERAL EVIDENCE PLANNER — V1
# ============================================================


def _successful_relationship_results(evidence_ledger):
    """Return successful relationship inspections in chronological ledger order."""
    results = []

    for item in evidence_ledger:
        if item.get("tool") != "inspect_object_relationship":
            continue

        result = item.get("result")

        if isinstance(result, dict) and "error" not in result:
            results.append(result)

    return results


def _successful_move_count(tool_execution_history):
    """Return the number of successful move_object writes executed so far."""
    return sum(
        1
        for item in tool_execution_history
        if (
            item.get("tool") == REQUIRED_MODIFICATION_TOOL
            and item.get("successful") is True
            and isinstance(item.get("result"), dict)
            and item["result"].get("status") == "moved"
        )
    )


def validate_midpoint_task(content, evidence_ledger):
    """
    Validate the explicit midpoint task using state-aware relationship evidence.

    Modification tasks have three distinct states:

        BEFORE  ->  measured state before any write
        TARGET  ->  calculated state required by the task
        AFTER   ->  independently verified state after the write

    The first successful relationship inspection is treated as BEFORE.
    When a successful move_object write exists, the latest relationship
    inspection after that write is treated as AFTER.

    This deliberately avoids hard-coding the goalpost coordinates. Target
    values are calculated from the measured BEFORE state and the task's
    explicit convention of translating both objects by -midpoint.
    """
    relationship_results = _successful_relationship_results(evidence_ledger)

    if not relationship_results:
        return []

    before_result = relationship_results[0]
    after_result = None

    # A relationship result after a successful write is the AFTER snapshot.
    # The evidence ledger preserves chronological acquisition order.
    successful_moves = _successful_move_count(tool_execution_history)

    if successful_moves > 0 and len(relationship_results) >= 2:
        after_result = relationship_results[-1]

    midpoint_before = before_result.get("midpoint")
    object_a_before = before_result.get("object_a", {})
    object_b_before = before_result.get("object_b", {})
    pos_a_before = object_a_before.get("location")
    pos_b_before = object_b_before.get("location")

    if not (
        isinstance(midpoint_before, list)
        and len(midpoint_before) == 3
        and isinstance(pos_a_before, list)
        and len(pos_a_before) == 3
        and isinstance(pos_b_before, list)
        and len(pos_b_before) == 3
    ):
        return []

    lower = (content or "").lower()
    errors = []

    # --------------------------------------------------------
    # BEFORE STATE
    # --------------------------------------------------------

    # Report the measured BEFORE midpoint and both measured BEFORE positions.
    before_midpoint_text = [f"{value:.3f}" for value in midpoint_before]
    before_a_text = [f"{value:.3f}" for value in pos_a_before]
    before_b_text = [f"{value:.3f}" for value in pos_b_before]

    # Validate coordinates numerically rather than by substring matching.
    # This accepts equivalent representations such as 0.0, 0.00, and 0.000.
    def _contains_coordinate_triplet(values, text, tolerance=1e-9):
        pattern = r"[-+]?\d+(?:\.\d+)?"
        numbers = [float(match) for match in re.findall(pattern, text)]
        for start in range(max(0, len(numbers) - 2)):
            candidate = numbers[start:start + 3]
            if len(candidate) == 3 and all(
                abs(candidate[i] - float(values[i])) <= tolerance
                for i in range(3)
            ):
                return True
        return False

    for values in (midpoint_before, pos_a_before, pos_b_before):
        if not _contains_coordinate_triplet(values, lower):
            errors.append(
                "The final answer must report the measured BEFORE state, "
                "including the initial midpoint and both initial object positions."
            )
            break

    # --------------------------------------------------------
    # TARGET STATE
    # --------------------------------------------------------

    # Explicit task convention: translate both objects by -BEFORE midpoint.
    target_a = [
        pos_a_before[i] - midpoint_before[i]
        for i in range(3)
    ]
    target_b = [
        pos_b_before[i] - midpoint_before[i]
        for i in range(3)
    ]
    adjustment = [
        -midpoint_before[i]
        for i in range(3)
    ]

    if midpoint_before != [0.0, 0.0, 0.0]:
        if (
            not _contains_coordinate_triplet(target_a, lower)
            or not _contains_coordinate_triplet(target_b, lower)
            or not _contains_coordinate_triplet(adjustment, lower)
        ):
            errors.append(
                "The final answer must include the calculated TARGET positions "
                f"({target_a} and {target_b}) and positional adjustment "
                f"({adjustment})."
            )

        if not any(
            phrase in lower
            for phrase in [
                "target position",
                "target positions",
                "target state",
                "positional adjustment",
                "adjustment",
            ]
        ):
            errors.append(
                "The final answer must explicitly report the TARGET positions "
                "and the positional adjustment."
            )

    # --------------------------------------------------------
    # AFTER / FINAL VERIFIED STATE
    # --------------------------------------------------------

    if successful_moves > 0:
        if after_result is None:
            errors.append(
                "A successful move_object write exists, but no subsequent "
                "inspect_object_relationship result establishes the FINAL "
                "VERIFIED state. Perform an independent relationship "
                "inspection after the write before finalizing."
            )
            return errors

        midpoint_after = after_result.get("midpoint")
        object_a_after = after_result.get("object_a", {})
        object_b_after = after_result.get("object_b", {})
        pos_a_after = object_a_after.get("location")
        pos_b_after = object_b_after.get("location")

        if not (
            isinstance(midpoint_after, list)
            and len(midpoint_after) == 3
            and isinstance(pos_a_after, list)
            and len(pos_a_after) == 3
            and isinstance(pos_b_after, list)
            and len(pos_b_after) == 3
        ):
            errors.append(
                "The post-modification relationship inspection did not return "
                "a complete FINAL VERIFIED state."
            )
            return errors

        if midpoint_after != [0.0, 0.0, 0.0]:
            errors.append(
                "The FINAL VERIFIED midpoint is not [0.0, 0.0, 0.0]. "
                "The task cannot be reported as successfully completed."
            )

        # Require the answer to distinguish AFTER from BEFORE.
        if not any(
            phrase in lower
            for phrase in [
                "after state",
                "final verified state",
                "verified after",
                "post-modification",
                "final state",
            ]
        ):
            errors.append(
                "The final answer must explicitly report the FINAL VERIFIED "
                "state after the modification."
            )

        # Require the verified final midpoint to be reported numerically.
        if not _contains_coordinate_triplet([0.0, 0.0, 0.0], lower):
            errors.append(
                "The final answer must report the FINAL VERIFIED midpoint "
                "[0.0, 0.0, 0.0]."
            )

    return errors


def extract_evidence_requests(content):
    """Extract explicit evidence-planner requests from Qwen output."""
    if not content:
        return []

    match = re.search(
        r"ATLAS_EVIDENCE_REQUESTS\s*:\s*(\[[\s\S]*?\])",
        content,
        re.IGNORECASE
    )

    if not match:
        return []

    try:
        parsed = json.loads(match.group(1))
    except Exception:
        return []

    if not isinstance(parsed, list):
        return []

    requests_found = []

    for request in parsed:
        if not isinstance(request, dict):
            continue

        tool_name = request.get("tool")
        arguments = request.get("arguments", {})

        if (
            isinstance(tool_name, str)
            and tool_name in TOOLS
            and isinstance(arguments, dict)
        ):
            requests_found.append(
                {
                    "tool": tool_name,
                    "arguments": arguments
                }
            )

    return requests_found


def evidence_request_already_acquired(
    request,
    evidence_ledger
):
    for item in evidence_ledger:
        if (
            item.get("tool") == request["tool"]
            and item.get("arguments") == request["arguments"]
        ):
            return True

    return False


def execute_evidence_request(
    request,
    evidence_ledger,
    messages
):
    tool_name = request["tool"]
    arguments = request["arguments"]

    print(
        f"\n>>> Executing PLANNED evidence tool: {tool_name}"
    )
    print(json.dumps(arguments, indent=2))

    try:
        tool_result = TOOLS[tool_name](**arguments)
    except Exception as error:
        tool_result = {"error": str(error)}

    print("\n>>> Planned tool result:")
    print(json.dumps(tool_result, indent=2))

    messages.append(
        {
            "role": "tool",
            "content": json.dumps(tool_result)
        }
    )

    if (
        isinstance(tool_result, dict)
        and "error" not in tool_result
    ):
        evidence_ledger.append(
            {
                "tool": tool_name,
                "arguments": arguments,
                "result": tool_result
            }
        )

        messages.append(
            {
                "role": "system",
                "content": (
                    "ATLAS EVIDENCE PLANNER UPDATE:\n"
                    "The requested evidence tool was successfully "
                    "executed by the orchestrator. Treat its result "
                    "as established evidence in the ledger.\n\n"
                    + json.dumps(tool_result, indent=2)
                )
            }
        )

        return True

    messages.append(
        {
            "role": "user",
            "content": (
                "The requested evidence tool failed. Do not invent "
                "its result. Continue using only evidence available "
                "in the ledger."
            )
        }
    )

    return False



# ============================================================
# REASONING / TOOL LOOP GUARDS
# ============================================================
#
# Controller-level protections. Python, not Qwen, decides when
# repeated reasoning/tool activity must stop.
# ============================================================

MAX_REASONING_STEPS = 8
MAX_REPEATED_REASONING = 3
MAX_REASONING_SIMILARITY = 0.92
MAX_IDENTICAL_TOOL_CALLS = 2

previous_reasoning_text = ""
repeated_reasoning_count = 0
tool_call_counts = {}

# ============================================================
# ACTION AUTHORIZATION / EXECUTION / VERIFICATION STATE
# ============================================================
# Fail-closed controller state for explicitly authorized Blender writes.
# A final answer is not accepted for an authorized modification task
# until a real write tool has executed and a separate read-only
# verification has occurred afterward.
#
# The current tool registry includes move_object as the narrowly scoped
# write capability for the authorized goalpost midpoint task.

WRITE_TOOL_NAMES = {
    "create_collection",
    "create_empty_marker",
    "move_object",
}

REQUIRED_MODIFICATION_TOOL = "move_object"

READ_ONLY_TOOL_NAMES = {
    "inspect_scene",
    "inspect_mesh",
    "inspect_scene_health",
    "inspect_scene_settings",
    "inspect_object_relationship",
    "inspect_soccer_components",
}

tool_execution_history = []


def task_explicitly_authorizes_modification(messages):
    """Detect explicit authorization in the current user task."""
    user_text = "\n".join(
        message.get("content", "")
        for message in messages
        if message.get("role") == "user"
    ).lower()

    authorization_phrases = [
        "explicitly authorized to modify",
        "explicit authorization",
        "authorized to modify",
        "authorized to execute",
        "permits the write operation",
    ]

    return any(phrase in user_text for phrase in authorization_phrases)


def modification_required_from_evidence(evidence_ledger):
    """Detect whether the current midpoint requirement is unsatisfied."""
    relationship_result = None

    for item in evidence_ledger:
        if item.get("tool") == "inspect_object_relationship":
            relationship_result = item.get("result")

    if not isinstance(relationship_result, dict):
        return False

    midpoint = relationship_result.get("midpoint")

    return (
        isinstance(midpoint, list)
        and len(midpoint) == 3
        and midpoint != [0.0, 0.0, 0.0]
    )


def write_tool_executed():
    """Return True only after a real move_object write succeeds."""
    return any(
        item.get("tool") == REQUIRED_MODIFICATION_TOOL
        and item.get("successful") is True
        and isinstance(item.get("result"), dict)
        and item["result"].get("status") == "moved"
        for item in tool_execution_history
    )

def verification_after_write_exists():
    """Require a read-only inspection after the latest real move."""
    last_move_index = None
    for index, item in enumerate(tool_execution_history):
        if (
            item.get("tool") == REQUIRED_MODIFICATION_TOOL
            and item.get("successful") is True
            and isinstance(item.get("result"), dict)
            and item["result"].get("status") == "moved"
        ):
            last_move_index = index

    if last_move_index is None:
        return False

    return any(
        item.get("successful") is True
        and item.get("tool") == "inspect_object_relationship"
        for item in tool_execution_history[last_move_index + 1:]
    )

def validate_action_completion(messages, evidence_ledger, content):
    """Fail closed for an authorized task that still requires a write."""
    if not task_explicitly_authorizes_modification(messages):
        return []

    if not modification_required_from_evidence(evidence_ledger):
        return []

    errors = []

    if not write_tool_executed():
        available_write_tools = sorted(
            name for name in WRITE_TOOL_NAMES if name in TOOLS
        )

        errors.append(
            "The current task explicitly authorizes a modification and "
            "the evidence shows that a modification is required, but no "
            "successful write tool has executed. Available write tools are: "
            + (", ".join(available_write_tools) if available_write_tools else "none")
            + ". A suitable write tool must execute before a final answer "
            "can be accepted. Do not claim that the modification was executed."
        )
        return errors

    if not verification_after_write_exists():
        errors.append(
            "A write operation was executed, but no successful read-only "
            "verification occurred afterward. Perform an independent "
            "post-modification inspection before finalizing."
        )

    return errors


def normalized_reasoning(content):
    """Normalize model text for repetition detection."""
    return re.sub(
        r"\s+",
        " ",
        (content or "").strip().lower()
    )


def reasoning_is_repeated(content):
    """
    Detect exact or very-high-similarity repetition in consecutive
    no-tool reasoning. This is deliberately conservative.
    """
    global previous_reasoning_text
    global repeated_reasoning_count

    current = normalized_reasoning(content)

    if not current:
        return False

    if not previous_reasoning_text:
        previous_reasoning_text = current
        repeated_reasoning_count = 1
        return False

    similarity = difflib.SequenceMatcher(
        None,
        previous_reasoning_text,
        current
    ).ratio()

    if (
        current == previous_reasoning_text
        or similarity >= MAX_REASONING_SIMILARITY
    ):
        repeated_reasoning_count += 1
    else:
        repeated_reasoning_count = 1

    previous_reasoning_text = current

    return (
        repeated_reasoning_count
        >= MAX_REPEATED_REASONING
    )


def tool_call_signature(function_name, arguments):
    return (
        function_name,
        json.dumps(
            arguments,
            sort_keys=True
        )
    )


def successful_evidence_exists(
    function_name,
    arguments,
    evidence_ledger
):
    """Avoid duplicate calls, except a read-only post-write verification."""
    if function_name in READ_ONLY_TOOL_NAMES:
        if any(
            item.get("tool") == REQUIRED_MODIFICATION_TOOL
            and item.get("successful") is True
            and isinstance(item.get("result"), dict)
            and item["result"].get("status") == "moved"
            for item in tool_execution_history
        ):
            return False

    for item in evidence_ledger:
        if item.get("tool") == function_name and item.get("arguments") == arguments:
            return True
    return False


# ============================================================
# AGENT LOOP
# ============================================================

for step in range(MAX_REASONING_STEPS):

    print(f"\n========== ATLAS STEP {step + 1} ==========\n")

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "messages": messages,
            "tools": tool_definitions,
            "stream": False
        }
    )

    response.raise_for_status()

    result = response.json()
    assistant_message = result["message"]

    print(json.dumps(assistant_message, indent=2))

    # ============================================================
    # NO TOOL CALL: determine whether Atlas may finalize
    # ============================================================

    if "tool_calls" not in assistant_message:

        content = assistant_message.get("content", "")

        # --------------------------------------------------------
        # DETERMINISTIC REASONING REPETITION GUARD
        # --------------------------------------------------------

        if content.strip():

            if reasoning_is_repeated(content):

                print(
                    "\n>>> Atlas reasoning loop guard triggered."
                )
                print(
                    "The model repeated substantially similar "
                    "reasoning without acquiring new evidence."
                )
                print(
                    "Stopping this assessment instead of "
                    "continuing unbounded inference."
                )

                print(
                    "\n========== ATLAS LOOP-GUARD RESPONSE ==========\n"
                )
                print(
                    "Atlas stopped because the reasoning model "
                    "repeated the same reasoning pattern "
                    f"{repeated_reasoning_count} times without "
                    "acquiring new evidence."
                )
                break

        if not content.strip():

            print(
                "\n>>> Atlas returned an empty response. "
                "Requesting a new reasoning step."
            )

            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Your previous response was empty and no tool "
                        "was executed. Continue the task. If a tool is "
                        "required, call the appropriate tool using the "
                        "exact parameter names from its definition. "
                        "Do not return an empty response."
                    )
                }
            )

            continue

        # --------------------------------------------------------
        # GENERAL EVIDENCE PLANNER
        # --------------------------------------------------------

        evidence_requests = extract_evidence_requests(content)

        planner_executed = False

        for evidence_request in evidence_requests:

            if evidence_request_already_acquired(
                evidence_request,
                evidence_ledger
            ):
                continue

            execute_evidence_request(
                evidence_request,
                evidence_ledger,
                messages
            )

            planner_executed = True

            # One planned acquisition per reasoning cycle keeps
            # execution deterministic and lets Qwen consume the
            # newly acquired evidence on the next step.
            break

        if planner_executed:
            continue

        # --------------------------------------------------------
        # TASK-DRIVEN EVIDENCE ACQUISITION
        # --------------------------------------------------------
        #
        # Evidence acquisition is driven by the current user task,
        # available tools, and the evidence ledger. There is no
        # globally mandatory soccer-component inspection.
        #
        # --------------------------------------------------------
        # FINAL-ANSWER EVIDENCE VALIDATION

        # --------------------------------------------------------

        validation_errors = validate_final_answer(
            content,
            evidence_ledger
        )

        validation_errors.extend(
            validate_midpoint_task(
                content,
                evidence_ledger
            )
        )

        validation_errors.extend(
            validate_action_completion(
                messages,
                evidence_ledger,
                content
            )
        )

        # --------------------------------------------------------
        # DETERMINISTIC NO-ACTION COMPLETION
        # --------------------------------------------------------
        # If the first authoritative relationship inspection already
        # satisfies the explicit midpoint requirement, the task is
        # complete. Do not send Atlas back around for another identical
        # inspection or require a write that the task says is conditional.
        successful_relationships = _successful_relationship_results(
            evidence_ledger
        )

        if (
            not validation_errors
            and successful_relationships
            and successful_relationships[0].get("midpoint") == [0.0, 0.0, 0.0]
            and not write_tool_executed()
        ):
            print(
                "\n========== ATLAS FINAL RESPONSE ==========\n"
            )
            print(content)
            break

        if validation_errors:

            print(
                "\n>>> Final answer rejected by evidence validator:"
            )

            for validation_error in validation_errors:
                print(f"- {validation_error}")

            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Your proposed final answer was rejected by "
                        "the evidence validator. Correct the following "
                        "violations using the authoritative evidence "
                        "ledger, then provide a revised final answer. "
                        "Do not invent missing information.\n\n"
                        + "\n".join(
                            "- " + error
                            for error in validation_errors
                        )
                        + "\n\nFor this authorized midpoint task, do not substitute unrelated "
                        "writes or unrelated inspections. If movement is still "
                        "required, call move_object. After the required movement, "
                        "perform a separate inspect_object_relationship verification."
                    )
                }
            )

            continue

        print(
            "\n========== ATLAS FINAL RESPONSE ==========\n"
        )
        print(content)
        break

    # ============================================================
    # TOOL CALL: execute the tool requested by Atlas
    # ============================================================

    messages.append(assistant_message)

    tool_call = assistant_message["tool_calls"][0]

    function_name = tool_call["function"]["name"]
    arguments = tool_call["function"]["arguments"]

    # New tool activity changes the evidence state, so consecutive
    # reasoning repetition starts fresh after a tool call.
    previous_reasoning_text = ""
    repeated_reasoning_count = 0

    current_tool_signature = tool_call_signature(
        function_name,
        arguments
    )

    tool_call_counts[current_tool_signature] = (
        tool_call_counts.get(
            current_tool_signature,
            0
        ) + 1
    )

    if (
        tool_call_counts[current_tool_signature]
        > MAX_IDENTICAL_TOOL_CALLS
        or successful_evidence_exists(
            function_name,
            arguments,
            evidence_ledger
        )
    ):

        print(
            "\n>>> Atlas tool-loop guard triggered."
        )
        print(
            "This exact successful tool request is already "
            "represented in the evidence ledger or exceeded "
            "the identical-call limit."
        )

        messages.append(
            {
                "role": "user",
                "content": (
                    "Continue CURRENT_TASK exactly as originally provided. "
                    "Do not replace, reinterpret, or reset the task. "
                    "The duplicate tool request was blocked by the controller. "
                    "Use the existing evidence ledger and choose the next "
                    "task-relevant action. If the authorized midpoint "
                    "modification is still required, call move_object."
                )
            }
        )
        continue

    # Prevent unrelated writes from satisfying an authorized modification task.
    if (
        task_explicitly_authorizes_modification(messages)
        and modification_required_from_evidence(evidence_ledger)
        and not write_tool_executed()
        and function_name in WRITE_TOOL_NAMES
        and function_name != REQUIRED_MODIFICATION_TOOL
    ):
        print(
            "\n>>> Atlas action gate rejected unrelated write tool: "
            + function_name
        )
        messages.append({
            "role": "user",
            "content": (
                "Do not call " + function_name + ". The current task requires "
                "the authorized object movement. Call move_object for "
                "Goal_Left_post or Goal_Right_Post using the exact target "
                "location required by the task. Do not substitute another "
                "write tool or an unrelated inspection."
            )
        })
        continue

    print(
        f"\n>>> Executing ONE tool: {function_name}"
    )
    print(
        json.dumps(
            arguments,
            indent=2
        )
    )

    if function_name not in TOOLS:

        tool_result = {
            "error": f"Unknown tool: {function_name}"
        }

    else:

        try:
            tool_result = TOOLS[function_name](**arguments)

        except Exception as error:
            tool_result = {
                "error": str(error)
            }

    print("\n>>> Tool result:")
    print(
        json.dumps(
            tool_result,
            indent=2
        )
    )

    tool_execution_history.append(
        {
            "tool": function_name,
            "arguments": arguments,
            "result": tool_result,
            "successful": (
                isinstance(tool_result, dict)
                and "error" not in tool_result
            ),
        }
    )

    # Store successful tool results in the evidence ledger.
    if (
        isinstance(tool_result, dict)
        and "error" not in tool_result
    ):

        evidence_ledger.append(
            {
                "tool": function_name,
                "arguments": arguments,
                "result": tool_result
            }
        )

    messages.append(
        {
            "role": "tool",
            "content": json.dumps(tool_result)
        }
    )

    # Give Atlas the complete authoritative evidence state.
    messages.append(
        {
            "role": "system",
            "content": (
                "ATLAS CURRENT TASK:\n"
                + CURRENT_TASK
                + "\n\n"
                + "ATLAS EVIDENCE LEDGER:\n"
                + "The following tool results have been successfully "
                "acquired during the current assessment.\n\n"
                "Treat the ledger as the authoritative record of "
                "verified evidence. If your reasoning or prior text "
                "conflicts with a value or classification in the ledger, "
                "the ledger takes precedence.\n\n"
                "Do not describe information contained in the ledger "
                "as unestablished. Do not repeat an inspection solely "
                "to obtain information already present in the ledger.\n\n"
                "Do not reinterpret, soften, or contradict explicit "
                "tool classifications. For example, if the ledger says "
                "symmetric_about_origin is false, report it as false.\n\n"
                + json.dumps(
                    evidence_ledger,
                    indent=2
                )
            )
        }
    )

else:

    print(
        "\nAtlas reached the maximum number "
        "of reasoning/tool steps."
    )