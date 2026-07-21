"""Provider-independent contracts and agents for the Day 1 AI vertical slice."""

from .agents import CopywriterAgent, ResearchAgent, run_research_copywriter
from .base import ChatMessage, ProviderResponse, StructuredProvider
from .config import DEFAULT_ROUTES, ModelRoute, Role
from .models import (
    CriticResult,
    Decision,
    DraftPost,
    GenerationMetadata,
    PolicyContext,
    ResearchBrief,
    TokenUsage,
)

__all__ = [
    "ChatMessage",
    "CopywriterAgent",
    "CriticResult",
    "DEFAULT_ROUTES",
    "Decision",
    "DraftPost",
    "GenerationMetadata",
    "ModelRoute",
    "PolicyContext",
    "ProviderResponse",
    "ResearchAgent",
    "ResearchBrief",
    "Role",
    "StructuredProvider",
    "TokenUsage",
    "run_research_copywriter",
]
