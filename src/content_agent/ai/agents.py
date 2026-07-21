"""Callable Research and Copywriter interfaces for Tín's orchestrator."""

from __future__ import annotations

from typing import Any

from .base import StructuredProvider
from .models import (
    DraftPayload,
    DraftPost,
    PolicyContext,
    ResearchBrief,
    ResearchCopywriterResult,
    ResearchPayload,
)
from .prompts import (
    COPYWRITER_PROMPT_VERSION,
    RESEARCH_PROMPT_VERSION,
    build_copywriter_messages,
    build_research_messages,
)


class ResearchAgent:
    def __init__(self, provider: StructuredProvider) -> None:
        self.provider = provider

    def run(self, *, topic: str, policy: Any) -> ResearchBrief:
        normalized_topic = topic.strip()
        if not normalized_topic:
            raise ValueError("topic must not be empty")
        policy_context = PolicyContext.from_policy(policy)
        response = self.provider.generate(
            messages=build_research_messages(normalized_topic, policy_context),
            response_model=ResearchPayload,
            role="research",
            prompt_version=RESEARCH_PROMPT_VERSION,
        )
        return ResearchBrief(
            **response.output.model_dump(),
            topic=normalized_topic,
            account_id=policy_context.account_id,
            metadata=response.metadata,
        )


class CopywriterAgent:
    def __init__(self, provider: StructuredProvider) -> None:
        self.provider = provider

    def run(self, *, research: ResearchBrief, policy: Any) -> DraftPost:
        policy_context = PolicyContext.from_policy(policy)
        if policy_context.account_id != research.account_id:
            raise ValueError("policy account_id must match research account_id")
        response = self.provider.generate(
            messages=build_copywriter_messages(research, policy_context),
            response_model=DraftPayload,
            role="copywriter",
            prompt_version=COPYWRITER_PROMPT_VERSION,
        )
        return DraftPost(
            **response.output.model_dump(),
            brief_id=research.brief_id,
            topic=research.topic,
            account_id=policy_context.account_id,
            platform=policy_context.platform,
            metadata=response.metadata,
        )


def run_research_copywriter(
    *,
    topic: str,
    policy: Any,
    research_provider: StructuredProvider,
    copywriter_provider: StructuredProvider,
) -> ResearchCopywriterResult:
    """One-call vertical-slice interface for the shared orchestrator."""

    research = ResearchAgent(research_provider).run(topic=topic, policy=policy)
    draft = CopywriterAgent(copywriter_provider).run(research=research, policy=policy)
    return ResearchCopywriterResult(research=research, draft=draft)
