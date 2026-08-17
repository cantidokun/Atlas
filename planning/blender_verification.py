"""Fail-closed verification gate for normalized Blender execution results."""

from planning.blender_result_contract import BlenderExecutionResult


class BlenderVerificationError(RuntimeError):
    """Raised when a Blender execution result cannot be accepted as successful."""


def verify_blender_execution(
    result: BlenderExecutionResult,
    expected_tool: str,
) -> BlenderExecutionResult:
    """Accept only a result that belongs to the expected tool and reports success."""
    if not isinstance(result, BlenderExecutionResult):
        raise TypeError("verification requires a BlenderExecutionResult")
    if not isinstance(expected_tool, str) or not expected_tool.strip():
        raise ValueError("expected tool must be a non-empty string")
    if result.tool != expected_tool:
        raise BlenderVerificationError("Blender result tool does not match requested tool")
    if not result.ok:
        raise BlenderVerificationError(
            f"Blender execution did not succeed: state={result.state}"
        )
    return result
