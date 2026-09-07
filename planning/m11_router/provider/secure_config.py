"""Secure deployment configuration resolution for M11.3 provider endpoints.

Credentials and endpoint configuration are NEVER kept in the repository, source
files, fixtures, telemetry, benchmark output, PR bodies, or logs. They are
resolved at runtime from an environment variable or an OS keyring/secure config
reference outside the repo.

The only thing stored in-repo is an *identifier* (``endpoint_config_ref``) such
as ``"openrouter"``; the concrete endpoint URL and API key are fetched at call
time. Fail-closed: if the credential or endpoint config is unavailable, the
adapter raises (never silently falls back to another provider/model).
"""

from __future__ import annotations

import os
from typing import Optional


class SecureConfigUnavailableError(RuntimeError):
    """Raised when a required credential/endpoint configuration is unavailable."""


class SecureConfigResolver:
    """Resolves deployment config references to concrete endpoint + key.

    Resolution order (each step fails closed):
    1. Exact env var ``ATLAS_M11_<REF_UPPER>_API_KEY``.
    2. A generic ``ATLAS_M11_API_KEY`` when a single provider is configured.
    3. A secure ``endpoint`` provided from a deployment injector (not stored).
    """

    def __init__(self, env: Optional[dict] = None) -> None:
        self._env = env if env is not None else os.environ

    def get_api_key(self, endpoint_config_ref: Optional[str]) -> str:
        if endpoint_config_ref:
            env_name = "ATLAS_M11_" + str(endpoint_config_ref).upper().replace("-", "_") + "_API_KEY"
            if env_name in self._env and self._env[env_name]:
                return str(self._env[env_name])
        if "ATLAS_M11_API_KEY" in self._env and self._env["ATLAS_M11_API_KEY"]:
            return str(self._env["ATLAS_M11_API_KEY"])
        raise SecureConfigUnavailableError(
            f"no API key configured for endpoint_config_ref={endpoint_config_ref!r} "
            "(credentials must come from secure env/keyring, never the repo)"
        )

    def resolve_endpoint(self, endpoint_config_ref: Optional[str], endpoint_hint: Optional[str]) -> str:
        """Return the provider endpoint URL for a config ref.

        Prefers an explicitly injected ``endpoint`` (deployment), then the env
        ``ATLAS_M11_<REF>_ENDPOINT``, then the public OpenRouter base as a last
        resort. This is a non-secret URL; the API key is never part of it.
        """
        if endpoint_hint:
            return str(endpoint_hint)
        if endpoint_config_ref:
            env_name = "ATLAS_M11_" + str(endpoint_config_ref).upper().replace("-", "_") + "_ENDPOINT"
            if env_name in self._env and self._env[env_name]:
                return str(self._env[env_name])
        raise SecureConfigUnavailableError(
            f"no endpoint configured for endpoint_config_ref={endpoint_config_ref!r}"
        )


# Default public non-secret base for OpenRouter (used only when a deployment
# injector provided no explicit endpoint and the ref resolves to "openrouter").
OPENROUTER_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"