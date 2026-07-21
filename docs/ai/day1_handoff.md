# AI-01 Day 1 handoff

## Ownership boundary

This branch owns provider adapters, AI contracts, versioned prompts, Research,
Copywriter, the Critic schema/probe, provider evidence, and AI-specific tests.
It deliberately does not own `run.py`, SQLite, orchestration state, the Markdown
policy parser, CI, or publishing.

Tài remains the owner of `AccountPolicy`. The AI layer accepts Tài's Pydantic
object directly through `PolicyContext.from_policy()`. The minimum consumed
fields are `account_id` (or `slug`/`name`), `goal`, `constraints`, `examples`,
`rubric`, and `threshold`; audience, platform, tone, language, banned terms,
required hashtags, and maximum length are supported when present.

## Interfaces for Tín

```python
from content_agent.ai import CopywriterAgent, ResearchAgent
from content_agent.ai.config import Role
from content_agent.ai.registry import create_role_provider

research_agent = ResearchAgent(create_role_provider(Role.RESEARCH))
copywriter_agent = CopywriterAgent(create_role_provider(Role.COPYWRITER))

brief = research_agent.run(topic=topic, policy=account_policy)
draft = copywriter_agent.run(research=brief, policy=account_policy)
```

Or use the atomic handoff helper:

```python
from content_agent.ai import run_research_copywriter
from content_agent.ai.config import Role
from content_agent.ai.registry import create_role_provider

result = run_research_copywriter(
    topic=topic,
    policy=account_policy,
    research_provider=create_role_provider(Role.RESEARCH),
    copywriter_provider=create_role_provider(Role.COPYWRITER),
)
```

`result.research` and `result.draft` are strict Pydantic models. Persist them
with `model_dump(mode="json")`. Each contains provider, model, role, prompt
version, SDK version, request ID when available, latency, and token usage.

## Fixtures and expected consumer tests

Valid and invalid fixtures live in `tests/fixtures/` for:

- `PolicyContext` compatibility input;
- `ResearchBrief`;
- `DraftPost`;
- `CriticResult`.

Tín's integration test should pass Tài's real `AccountPolicy` to
`ResearchAgent.run`, persist the returned `ResearchBrief`, pass that exact
object to `CopywriterAgent.run`, and assert that both records share the account
and that `DraftPost.brief_id == ResearchBrief.brief_id`.

## Error handoff

All provider failures become `ProviderError` with these stable fields:

```text
code, message, provider, model, retryable, status_code
```

Messages never contain request headers or credentials. Tín can store
`error.as_dict()` in `RunEvent` and apply retry/backoff only when `retryable` is
true. The normalized codes cover missing credentials, auth/permission, quota,
timeout, network, model availability, content filtering, malformed JSON,
schema failure, and generic provider failure.

## Commands

```powershell
python scripts/provider_spike.py --dry-run
python -m unittest discover -s tests -v
python scripts/provider_spike.py --provider all
python scripts/ai_day1_demo.py
```

The first two commands consume no provider quota. The provider spike consumes
one request on each primary route. The Day 1 demo consumes one Gemini request
and one Groq request.
