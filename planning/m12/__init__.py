"""Atlas M12 — Unreal Semantic Soccer Production Layer.

M12.1 implements the foundational semantic task contract and the
normalization/compile boundary. M12 is a semantic description+planning layer
ABOVE the existing M4-M10 Unreal execution/recovery/evidence machinery. It never
authorizes execution, never mints receipts/recovery authority/protected flags,
and never introduces a second scheduler/retry/persistence authority.

Package layout:
- task_classes: constrained, canonical Unreal soccer-production task taxonomy.
- target_state: reusable, data-only target-state descriptor.
- semantic_task: immutable UnrealProductionTaskDefinition + normalization +
    compile boundary onto the existing AtlasTaskDefinition runtime.
"""

from planning.m12.catalog import (
    DEFAULT_UNREAL_CATALOG,
    InvalidCatalogParametersError,
    UnrealCatalogEntrySpec,
    UnrealCatalogError,
    UnrealSoccerProductionCatalog,
    UnknownCatalogTaskError,
    UnsupportedCatalogVersionError,
)
from planning.m12.composition import (
    FragmentCompositionError,
    UnrealComposedTaskPlan,
    compose_fragments,
)
from planning.m12.execution_plan import (
    UnrealExecutionPlan,
    UnrealExecutionPlanError,
    UnrealExecutionPlanStep,
    generate_execution_plan,
)
from planning.m12.fragments import UnrealProductionFragment
from planning.m12.fragments_registry import (
    CANONICAL_UNREAL_FRAGMENTS,
    canonical_fragment,
)
from planning.m12.semantic_task import (
    UnauthorizedSemanticFieldError,
    UnrealProductionTaskDefinition,
    UnrealSemanticTaskError,
    UnsupportedCompileMappingError,
    compile_unreal_semantic_task,
    normalize_unreal_semantic_request,
)
from planning.m12.task_classes import (
    UNREAL_RENDER_TASK_CLASSES,
    UNREAL_TASK_CLASSES,
    is_render_task_class,
    is_supported_task_class,
    validate_task_class,
)
from planning.m12.target_state import (
    UnrealTargetStateSpec,
    target_state_metadata,
    target_state_spec,
)

__all__ = [
    # M12.1
    "UnrealProductionTaskDefinition",
    "UnrealTargetStateSpec",
    "UnrealSemanticTaskError",
    "UnsupportedCompileMappingError",
    "UnauthorizedSemanticFieldError",
    "normalize_unreal_semantic_request",
    "compile_unreal_semantic_task",
    "target_state_spec",
    "target_state_metadata",
    "validate_task_class",
    "is_supported_task_class",
    "is_render_task_class",
    "UNREAL_TASK_CLASSES",
    "UNREAL_RENDER_TASK_CLASSES",
    # M12.2
    "UnrealProductionFragment",
    "CANONICAL_UNREAL_FRAGMENTS",
    "canonical_fragment",
    "FragmentCompositionError",
    "UnrealComposedTaskPlan",
    "compose_fragments",
    "UnrealCatalogError",
    "UnknownCatalogTaskError",
    "UnsupportedCatalogVersionError",
    "InvalidCatalogParametersError",
    "UnrealCatalogEntrySpec",
    "UnrealSoccerProductionCatalog",
    "DEFAULT_UNREAL_CATALOG",
    # M12.3
    "UnrealExecutionPlanError",
    "UnrealExecutionPlanStep",
    "UnrealExecutionPlan",
    "generate_execution_plan",
]