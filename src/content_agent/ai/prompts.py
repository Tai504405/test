"""Versioned prompts. Prompts ask only for facts supplied by the caller."""

from __future__ import annotations

import json

from .base import ChatMessage
from .models import DraftPost, PolicyContext, ResearchBrief

RESEARCH_PROMPT_VERSION = "research-v1.0.0"
COPYWRITER_PROMPT_VERSION = "copywriter-v1.0.0"
CRITIC_PROBE_PROMPT_VERSION = "critic-probe-v1.0.0"


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def build_research_messages(topic: str, policy: PolicyContext) -> list[ChatMessage]:
    return [
        ChatMessage(
            role="system",
            content=(
                "You are the Research Agent for a social-content pipeline. "
                "Return one JSON object only. Do not claim web browsing or invent citations. "
                "Use source_notes to state that the brief is based on supplied context and general model knowledge."
            ),
        ),
        ChatMessage(
            role="user",
            content=(
                f"Research topic: {topic}\n"
                f"Account policy:\n{_json(policy.model_dump(mode='json'))}\n"
                "Produce a concise research brief tailored to the policy. Cover useful facts, audience insights, "
                "content angles, risks, and honest source notes."
            ),
        ),
    ]


def build_copywriter_messages(brief: ResearchBrief, policy: PolicyContext) -> list[ChatMessage]:
    return [
        ChatMessage(
            role="system",
            content=(
                "You are the Copywriter Agent for a social-content pipeline. Return one JSON object only. "
                "Follow every supplied policy constraint. Never include a banned term. Do not add factual claims "
                "that are absent from the research brief."
            ),
        ),
        ChatMessage(
            role="user",
            content=(
                f"Account policy:\n{_json(policy.model_dump(mode='json'))}\n"
                f"Research brief:\n{_json(brief.model_dump(mode='json'))}\n"
                "Write one platform-ready post. List the constraints you applied. Put hashtags in the hashtags "
                "array rather than duplicating them in content."
            ),
        ),
    ]


def build_critic_probe_messages(draft: DraftPost, policy: PolicyContext) -> list[ChatMessage]:
    return [
        ChatMessage(
            role="system",
            content=(
                "You are a strict structured-output critic. Return one JSON object only. "
                "Use decision=pass only when the draft meets the policy threshold and has no material violation."
            ),
        ),
        ChatMessage(
            role="user",
            content=(
                f"Policy:\n{_json(policy.model_dump(mode='json'))}\n"
                f"Draft:\n{_json(draft.model_dump(mode='json'))}\n"
                "Score the draft from 0 to 100 and return rule_passed, score, violations, suggestions, and decision."
            ),
        ),
    ]
