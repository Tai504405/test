# AI-01 Provider Spike — Day 1 (Trọng)

This folder is a merge-safe overlay for the `Content_Agent_System` repository.
It implements Trọng's Day 1 deliverable without taking over Tín's repository,
CLI, database, logging, or CI ownership.

## Day 1 goal

Prove that the three free-tier providers can return validated structured JSON,
freeze a provider adapter contract, propose the Research/Copywriter/Critic model
routes, and hand a stable error taxonomy to Tín.

## What is included

- Pydantic contracts for `ResearchBrief`, `DraftPost`, and `CriticResult`.
- A provider-independent adapter interface.
- Gemini, Groq, and GitHub Models SDK-backed adapters.
- Primary/fallback model registry.
- A live spike command that never logs API keys.
- Offline unit tests for schemas, error normalization, and fallback routing.
- The provider decision record and team handoff checklist.

## Merge order

1. Wait until Tín pushes the repository bootstrap to `main`.
2. Pull `main` and create Trọng's branch:

   ```powershell
   git switch main
   git pull origin main
   git switch -c feature/ai-01-provider-spike
   ```

3. Copy the contents of this overlay into the repository root. If Tín chose a
   package name other than `content_agent`, keep Tín's name and move the files
   under that package instead.
4. Add `pydantic>=2.8,<3` to Tín's `pyproject.toml`. Do not replace Tín's file
   with a second project configuration.

## Team setup and credential ownership

Every teammate must use their **own** free-tier credentials for live testing.
Do not copy Trọng's `.env`, reuse another member's token, or send a credential
through chat, email, screenshots, issues, pull requests, logs, or artifacts.
Offline tests do not require any credentials.

Create the credentials below before running the live checks:

| Role | Credential to create | Primary model | Required access |
|---|---|---|---|
| Research | [Gemini API key in Google AI Studio](https://aistudio.google.com/apikey) | `gemini-3.1-flash-lite` | Use a Gemini Developer API free-tier project |
| Copywriter | [Groq API key](https://console.groq.com/keys) | `llama-3.3-70b-versatile` | Use the Groq Free Plan and confirm the model on the account Limits page |
| Critic | [GitHub fine-grained PAT](https://github.com/settings/personal-access-tokens/new) | `openai/gpt-4o-mini` | Set **Account permissions → Models → Read-only**; repository permission is not required for direct inference |

Pinned fallbacks are `gemini-3.5-flash`, `qwen/qwen3.6-27b`, and
`openai/gpt-4.1-mini`. Do not test fallbacks during normal verification because
that consumes extra requests. The Groq primary is scheduled to shut down for
free/developer tiers on 16 August 2026, so the Qwen fallback is the planned
post-sprint replacement.

Use free-tier accounts/projects and do not select Groq Flex, paid Gemini
features, Gemini Search grounding, or paid GitHub Models usage for this Day 1
test. Provider billing settings are controlled in each teammate's account, not
by the API token itself.

## Local setup on Windows

Run these commands from the repository root.

PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-ai.txt
Copy-Item .env.ai.example .env
```

Command Prompt (`cmd.exe`):

```cmd
py -3.12 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements-ai.txt
copy .env.ai.example .env
```

Open `.env` locally and fill in the three credentials. Keep these exact model
IDs unless the provider matrix is deliberately updated:

```dotenv
GEMINI_API_KEY=<your-own-gemini-key>
GEMINI_MODEL=gemini-3.1-flash-lite

GROQ_API_KEY=<your-own-groq-key>
GROQ_MODEL=llama-3.3-70b-versatile

GITHUB_MODELS_TOKEN=<your-own-fine-grained-github-pat>
GITHUB_MODELS_MODEL=openai/gpt-4o-mini
```

Never commit `.env`. The repository tracks only `.env.ai.example`, whose
credential values are blank.

## Day 1 verification for Tín and Tài

Run the checks in this order from the activated virtual environment.

### `provider_spike.py` test command reference

Use this single script for every provider connectivity and structured-output
check:

| Test purpose | Command | API requests | Artifact |
|---|---|---:|---|
| Inspect configured routes only | `python scripts/provider_spike.py --dry-run` | 0 | `artifacts/provider_spike_results.json` |
| Quick GitHub connection/JSON smoke | `python scripts/provider_spike.py --provider github_models --smoke` | 1 GitHub | `artifacts/github_models_smoke.json` |
| Formal Gemini Research contract | `python scripts/provider_spike.py --provider gemini` | 1 Gemini | `artifacts/provider_spike_results.json` |
| Formal Groq Copywriter contract | `python scripts/provider_spike.py --provider groq` | 1 Groq | `artifacts/provider_spike_results.json` |
| Formal GitHub Critic contract | `python scripts/provider_spike.py --provider github_models` | 1 GitHub | `artifacts/provider_spike_results.json` |
| Full Day 1 provider evidence | `python scripts/provider_spike.py --provider all` | 3 total | `artifacts/provider_spike_results.json` |
| Primary and fallback validation | `python scripts/provider_spike.py --provider all --include-fallbacks` | 6 total | `artifacts/provider_spike_results.json` |

Use `--output <path>` when you need to preserve an earlier artifact, for
example:

```cmd
python scripts/provider_spike.py --provider gemini --output artifacts/gemini_check.json
```

Recommended order for normal review:

```cmd
python scripts/provider_spike.py --dry-run
python scripts/provider_spike.py --provider github_models --smoke
python scripts/provider_spike.py --provider all
```

The `--smoke` flag must be used with `--provider github_models`; it cannot be
combined with `--dry-run` or `--include-fallbacks`.

### 1. Inspect routes without spending quota

```cmd
python scripts/provider_spike.py --dry-run
```

Expected: Research, Copywriter, and Critic routes show `configured` with the
three primary model IDs above.

### 2. Run the offline contract and security suite

```cmd
python -m unittest discover -s tests -v
```

Expected final lines:

```text
Ran 20 tests
OK
```

These tests validate the ResearchBrief, DraftPost, CriticResult, valid/invalid
fixtures, policy conditioning, provider separation, usage metadata, safe error
normalization, malformed JSON handling, and the no-secret rule. They consume no
provider quota.

### 3. Validate all three live providers

```cmd
python scripts/provider_spike.py --provider all
```

Expected status table:

```text
research     gemini           primary      passed       gemini-3.1-flash-lite
copywriter   groq             primary      passed       llama-3.3-70b-versatile
critic       github_models    primary      passed       openai/gpt-4o-mini
```

This consumes one request per primary provider. It writes
`artifacts/provider_spike_results.json`; each response is counted as passed only
after local Pydantic validation.

Optional: when diagnosing only the GitHub Models credential/model, use the
lightweight smoke mode in the same `provider_spike.py` command instead of
spending quota on all three providers:

```cmd
python scripts/provider_spike.py --provider github_models --smoke
```

It checks that GitHub Models returns valid JSON with `caption`, `hashtags`, and
`cta`, then writes `artifacts/github_models_smoke.json`. This is a connection
diagnostic inside the formal provider-spike tool; the normal Critic contract is
still validated by `--provider all`.

### 4. Validate the integrated Research → Copywriter handoff

```cmd
python scripts/ai_day1_demo.py
```

Expected summary:

```text
Account: responsible-ai-lab
Research: gemini/gemini-3.1-flash-lite
Copywriter: groq/llama-3.3-70b-versatile
Draft: ...
```

This consumes one Gemini and one Groq request. It writes
`artifacts/ai_day1_demo.json` and proves that the Groq draft references the
exact Gemini research object through `brief_id`.

### 5. Owner-specific sign-off

- **Tín:** confirm `run_research_copywriter()` is callable by the orchestrator,
  `DraftPost.brief_id` matches `ResearchBrief.brief_id`, and
  `ProviderError.as_dict()` fits the planned `RunEvent` error fields.
- **Tài:** confirm `PolicyContext.from_policy()` accepts the real
  `AccountPolicy`, the generated draft reflects its goal/tone/constraints, and
  the shared `CriticResult` fields fit Policy Spec v0.1.
- **Both:** confirm no credential appears in `git status`, the PR diff, terminal
  output, or either runtime artifact.

Do not run the following command during routine verification; it consumes
additional free-tier requests and is only for an explicit fallback check:

```cmd
python scripts/provider_spike.py --provider all --include-fallbacks
```

Common failures:

- `missing_credential`: the matching key/token is absent from `.env`.
- `authentication`: the credential is invalid or expired.
- GitHub `permission_denied`: recreate/edit the fine-grained PAT with
  **Models: Read-only**.
- `unavailable_model`: verify the exact provider-prefixed model ID.
- `rate_limit`: wait for the free-tier limit to reset; do not switch to paid
  usage solely to pass this spike.

## Commit and open the PR

```powershell
git add src/content_agent/ai scripts/provider_spike.py scripts/ai_day1_demo.py `
  tests docs/ai requirements-ai.txt .env.ai.example .gitignore README.md
git commit -m "feat(ai): add provider spike and structured contracts"
git push -u origin feature/ai-01-provider-spike
```

PR title: `AI-01: Provider spike, structured contracts, and model routing`

Before requesting review, paste the actual pass/fail table from
`artifacts/provider_spike_results.json` into the PR description. Do not commit
that runtime artifact unless the team explicitly wants test evidence versioned.

## Definition of done

- Gemini, Groq, and GitHub Models each return schema-valid JSON at least once.
- The chosen primary/fallback routes are documented.
- Missing credentials, auth, quota, timeout, provider, model, content, and
  schema failures have normalized codes.
- Tín confirms the error fields fit `RunEvent`.
- Tài confirms the shared `CriticResult` fields fit Policy Spec v0.1.
- Offline tests pass and no secret is present in the diff.
