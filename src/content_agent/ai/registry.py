"""Provider factory for primary and explicitly requested fallback models."""

from __future__ import annotations

import os
from typing import Mapping

from .base import StructuredProvider
from .config import DEFAULT_ROUTES, Role
from .providers import GeminiProvider, GitHubModelsProvider, GroqProvider


def create_role_provider(
    role: Role | str,
    *,
    fallback_index: int | None = None,
    env: Mapping[str, str] | None = None,
) -> StructuredProvider:
    normalized_role = role if isinstance(role, Role) else Role(role)
    route = DEFAULT_ROUTES[normalized_role]
    source = os.environ if env is None else env

    if fallback_index is None:
        model = source.get(route.model_env, route.primary_model)
    else:
        try:
            model = route.fallback_models[fallback_index]
        except IndexError as exc:
            raise ValueError(f"No fallback {fallback_index} for role {normalized_role.value}") from exc

    api_key = source.get(route.credential_env)
    if route.provider == "gemini":
        return GeminiProvider(api_key=api_key, model=model)
    if route.provider == "groq":
        return GroqProvider(api_key=api_key, model=model)
    if route.provider == "github_models":
        return GitHubModelsProvider(api_key=api_key, model=model)
    raise ValueError(f"Unsupported provider: {route.provider}")
