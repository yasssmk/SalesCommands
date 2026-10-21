# evals/td279 — People / Blocker attribution measurement

Measurement script of the TD-279 sprint (not production code: nothing in
`app_modules/` imports it, it writes nothing to the database). It sends the
**production** prompts (system + context + request) of the
`transcript_signals` stages to the **real** LLM, with the production model of
each stage (`ai_pipelines/config.py` `STAGE_PROVIDER`) and the production
response schema (`STAGE_RESPONSE_SCHEMAS`), then scores the raw answers with
the production helpers (name link, People evidence check, department
resolver, quote-label removal).

## Cases

| Transcript | Variants | What is measured |
|---|---|---|
| `transcript_logistix.txt` (demo) | `people_V0`, `blocker_V0` | a cited third party never put on the registered contact, Claire's own role, seller never extracted |
| `transcript_logistix_witness.txt` (the registered contact speaks) | `people_WITNESS`, `blocker_WITNESS` | the registered contact linked with HER OWN quote |
| `transcript_atelier.txt` (business-case workshop) | `atelier_people`, `atelier_pain_impact`, `atelier_objective`, `atelier_techstack`, `atelier_blocker` | the 7 persons, management controller (job title + Finance), impacts, target date, tools, blockers |

## Commands (from `backend/`, with `OPENAI_API_KEY` in the environment)

```bash
# Default: every variant, 10 calls each, production model per stage
python evals/td279/run_attribution_eval.py

# A subset, 20 calls each (the minimum to read a rate -- see below)
python evals/td279/run_attribution_eval.py --n 20 --only people_V0 people_WITNESS atelier_people

# Force a model DECLARED in config.PROVIDER_CONFIG (e.g. the People challenger)
python evals/td279/run_attribution_eval.py --n 20 --model gpt-5.4-mini-2026-03-17 \
    --only people_V0 people_WITNESS atelier_people

# Recompute the summary of an existing run from its recorded raw answers
# (after a metric fix) -- NO API call
python evals/td279/run_attribution_eval.py --rescore evals/td279/out/<stamp>

# Plumbing check, no API call (fixed answers)
python evals/td279/run_attribution_eval.py --dry-run
```

## Outputs (`evals/td279/out/<stamp>/`, a non-empty folder is refused)

- `<variant>/call_NN.json` — the rendered system + user prompt, every raw
  answer, the parsed JSON, the call meta (model, duration, tokens), the error
  and its type, the metrics of the call.
- `summary.csv` — one row per call; `summary.md` — the recap: model and
  prompt versions per variant, durations (mean / max `duration_ms`, max
  `wall_ms`) and error types, People proofs rejected by the server (per cause,
  per person), then the People / Blocker / atelier tables.
- `--rescore` writes `summary_rescored.csv` / `summary_rescored.md` next to
  the originals (kept).

## ⚠️ Read the results with care

- **The models are not deterministic, even at temperature 0** (and reasoning
  models take no temperature at all): the same prompt gives different answers
  from one call to the next. A single call proves nothing.
- **Run at least 20 calls per variant** (20-30) before concluding, and compare
  rates (`x/20`), never one answer.
- A model without a pinned snapshot (e.g. `gpt-5.6-terra`) can change under
  the same name: rerun the eval regularly.
