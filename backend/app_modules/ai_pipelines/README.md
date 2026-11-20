# AI pipelines — choosing the deal health's LLM provider

The deal health runs on **OpenAI** by default. It can run on **Claude**
(Anthropic) instead: one secret key and one value of this module's
configuration.

## To test Claude

1. Set `ANTHROPIC_API_KEY` (an Anthropic API key) in
   `backend/salescommands/.env` — the file `settings.py` reads (or in the
   hosting environment). See `backend/.env.example`: the `.env` holds the
   secret keys only.
2. In `app_modules/ai_pipelines/config.py`, set `DEAL_HEALTH_LLM_PROVIDER`
   to `'claude'`.
3. Restart the backend.

To go back to OpenAI, set `DEAL_HEALTH_LLM_PROVIDER` back to `'openai'` in
`config.py` and restart.

If `DEAL_HEALTH_LLM_PROVIDER = 'claude'` and `ANTHROPIC_API_KEY` is missing,
the backend refuses to start with a message naming the missing variable
(`pipelines/deal_health.check_deal_health_provider`).

## What runs where

| `config.DEAL_HEALTH_LLM_PROVIDER` | Entry (`config.py` `PROVIDER_CONFIG`) | Model (override) |
|---|---|---|
| `'openai'` (default) | `openai_deal_health` | `gpt-5.6-terra` (`AI_PIPELINES_DEAL_HEALTH_MODEL`) |
| `'claude'` | `claude_deal_health` | `claude-opus-5-5` (`AI_PIPELINES_DEAL_HEALTH_CLAUDE_MODEL`) |

Both send the same strict response schema (Structured Outputs), the same
effort, timeout and token budget. Only the deal health reads this value;
the other pipelines keep their own provider configuration.
