"""M11.2 provider execution layer for the adaptive development router.

Development-tooling only; never Atlas production authority. This package
defines the provider adapter boundary + invocation contract. Router logic never
depends directly on a vendor SDK; provider/model/pricing are configuration.
"""

from planning.m11_router.provider.providers_config import (
    ProviderConfig,
    ProviderConfigError,
    ProviderUsage,
    load_provider_configs,
)
from planning.m11_router.provider.invocation import (
    InvocationErrorKind,
    ModelResult,
    ProviderAdapter,
    ProviderInvocation,
    invoke_model,
)
from planning.m11_router.provider.openrouter_adapter import OpenRouterAdapter
from planning.m11_router.provider.secure_config import (
    SecureConfigResolver,
    SecureConfigUnavailableError,
)

from planning.m11_router.provider.shadow import ShadowAdvisor

__all__ = [
    "ProviderConfig",
    "ProviderConfigError",
    "ProviderUsage",
    "load_provider_configs",
    "InvocationErrorKind",
    "ModelResult",
    "ProviderAdapter",
    "ProviderInvocation",
    "invoke_model",
    "ShadowAdvisor",
    "OpenRouterAdapter",
    "SecureConfigResolver",
    "SecureConfigUnavailableError",
]

OpenRouterAdapter = OpenRouterAdapter
SecureConfigResolver = SecureConfigResolver
SecureConfigUnavailableError = SecureConfigUnavailableError
