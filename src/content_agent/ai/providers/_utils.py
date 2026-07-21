"""Shared adapter metadata helpers."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Any, Literal

from ..models import GenerationMetadata, TokenUsage


def sdk_version(package: str) -> str:
    try:
        return f"{package}/{version(package)}"
    except PackageNotFoundError:
        return f"{package}/unknown"


def int_value(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def metadata(
    *,
    provider: Literal["gemini", "groq", "github_models"],
    model: str,
    role: Literal["research", "copywriter", "critic"],
    prompt_version: str,
    provider_sdk: str,
    latency_ms: int,
    input_tokens: Any = 0,
    output_tokens: Any = 0,
    total_tokens: Any = 0,
    request_id: Any = None,
) -> GenerationMetadata:
    return GenerationMetadata(
        provider=provider,
        model=model,
        role=role,
        prompt_version=prompt_version,
        provider_sdk=provider_sdk,
        latency_ms=max(0, latency_ms),
        usage=TokenUsage(
            input_tokens=int_value(input_tokens),
            output_tokens=int_value(output_tokens),
            total_tokens=int_value(total_tokens),
            # These routes are validated for free-tier use. We intentionally do
            # not invent a dollar estimate because account billing state is not
            # exposed consistently by provider responses.
            estimated_cost_usd=None,
        ),
        request_id=str(request_id) if request_id else None,
    )
