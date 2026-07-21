# AI-01 Day 1 definition-of-done evidence

| Requirement | Evidence |
|---|---|
| Validate Gemini, Groq, and GitHub Models free routes | `scripts/provider_spike.py`; `artifacts/provider_spike_results.json` after live execution |
| Structured ResearchBrief, DraftPost, CriticResult | `src/content_agent/ai/models.py`; valid/invalid fixtures and schema tests |
| Research uses policy context | `ResearchAgent`; prompt assertions in `tests/test_agents.py` |
| Copywriter uses policy and ResearchBrief | `CopywriterAgent`; traceability test and live Day 1 demo |
| Callable interfaces handed to Tín | `docs/ai/day1_handoff.md` and `run_research_copywriter()` |
| Provider/model/prompt/usage metadata | `GenerationMetadata` on every public AI output |
| Copywriter/Critic provider separation | frozen route registry and registry test |
| Actionable safe failures | `ProviderError`, normalization tests, no-secret scan |
| Free-tier controls documented | `docs/ai/provider_matrix.md`; no automatic fallback calls |

## Gate result — GREEN for Trọng's AI-01 scope

- 20/20 offline unit and security tests passed.
- Gemini Research, Groq Copywriter, and GitHub Models Critic probe passed live.
- The live Gemini-to-Groq vertical slice produced a linked, schema-valid
  `ResearchBrief` and `DraftPost`.
- Runtime artifacts contain no detected provider secret.

The remaining shared G1 proof—persistence under Tín's `run_id`/SQLite and
consumption of Tài's real Markdown `AccountPolicy`—belongs to the cross-owner
integration gate and cannot be completed from this overlay because those
modules are not present in the branch yet. The callable handoff and fixtures
needed for that merge are complete.
