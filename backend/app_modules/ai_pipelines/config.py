# app_modules/ai_pipelines/config.py
"""
Central configuration for the AI Pipelines module.

Single point of switch for the active LLM provider, model selection,
per-call timeouts, and input bounds. Every value can be overridden in
Django settings using the `AI_PIPELINES_*` namespace — see each block
for the exact setting key.

API keys are read from environment variables by the provider SDKs
themselves (OPENAI_API_KEY for OpenAI, ANTHROPIC_API_KEY for
Anthropic) and are NOT exposed here.

Note on TEMPERATURE
-------------------
Pipeline temperatures are centralized in constants.PIPELINE_TEMPERATURES.
Each pipeline class reads its value from that dict via its AIPipelineType key.
"""

from django.conf import settings

from .constants import DEAL_HEALTH_MAX_TOKENS, DEAL_HEALTH_TIMEOUT_S


# =============================================================================
# PROVIDER SELECTION — single point of switch
# =============================================================================

# Active LLM provider key. Must match a key in PROVIDER_CONFIG below
# AND a registered provider class in providers/__init__.py.
#
# Override at the Django settings level:
#     AI_PIPELINES_ACTIVE_PROVIDER = 'claude'
#
# Default: 'openai' — chosen for MVP because the SDK was already
# pinned in requirements.txt before this sprint, and the default model
# (gpt-4o-mini) hits a good cost / quality balance for structured
# signal extraction.
ACTIVE_PROVIDER = getattr(settings, 'AI_PIPELINES_ACTIVE_PROVIDER', 'openai')


# =============================================================================
# PROVIDER CONFIGURATION
# =============================================================================

# Per-provider runtime configuration.
#
# Keys match the values accepted by ACTIVE_PROVIDER. Each entry
# declares:
#
#   model       Default model identifier the provider class will
#                pass to its SDK. Pipelines MAY override on a per-
#                pipeline basis when a specific use case warrants a
#                heavier / lighter model.
#
#   timeout_s   Per-call timeout in seconds. Exceeding this raises
#                LLMTimeoutError in the provider abstraction, which
#                the orchestrator maps to AIPipelineStatus.TIMEOUT.
#
#   max_tokens  Ceiling on response tokens. Set generously enough
#                for structured JSON responses on long transcripts
#                but bounded to keep cost / latency predictable.
#
#   provider    OPTIONAL (TD-279 P1) -- the provider class key in
#                providers/__init__.py when the entry key is not a
#                provider name itself (several entries can share one
#                provider). Default: the entry key.
#
#   reasoning_effort  OPTIONAL (TD-279 P1) -- reasoning-model mode
#                ('low' / 'medium' / 'high'): sent as reasoning_effort,
#                temperature NOT sent, max_tokens sent as
#                max_completion_tokens (providers, P0). This option -- never
#                the model name -- decides the mode. On Claude (5b) it is
#                sent as output_config.effort.
#
# Override the whole dict in Django settings:
#     AI_PIPELINES_PROVIDER_CONFIG = {...}
PROVIDER_CONFIG = getattr(settings, 'AI_PIPELINES_PROVIDER_CONFIG', {
    'openai': {
        'model':       'gpt-4o-mini',
        'timeout_s':   30,
        'max_tokens':  4096,
    },
    'claude': {
        'model':       'claude-haiku-4-5-20251001',
        'timeout_s':   30,
        'max_tokens':  4096,
    },
    # TD-279 P1 -- People stage on a reasoning model. TD-279 M (PO, after the
    # --n 20 "model alone" measure on prompt v7): gpt-5.6-terra (quality over
    # cost; no pinned snapshot listed, so the model may change under the same
    # name -- the eval is the guard); gpt-5.4-mini becomes the challenger.
    # timeout_s 90: the extraction runs its stages sequentially inside one
    # request whose client falls back to polling for ~180 s
    # (core/timeout_conventions.py POLLING_MAX_ATTEMPTS x
    # POLLING_INTERVAL_SECONDS); rule R2 asks that window to cover the sum of
    # the calls. Estimating the 7 other stages at ~5-10 s each (~60 s, not
    # measured), 90 s is the share left to People -- about 1.5x the time to
    # emit the full 8192-token budget at ~100 tokens/s, reasoning included.
    # Kept until the eval measures the real durations (mean / max duration_ms).
    'openai_people': {
        'provider':          'openai',
        'model':             'gpt-5.6-terra',
        'reasoning_effort':  'medium',
        'timeout_s':         90,
        'max_tokens':        8192,
    },
    # Challenger, DECLARED for the eval only (--model) -- not wired in
    # STAGE_PROVIDER. Pinned snapshot (2 calls in error out of 20 in the
    # "model alone" measure).
    'openai_people_challenger': {
        'provider':          'openai',
        'model':             'gpt-5.4-mini-2026-03-17',
        'reasoning_effort':  'medium',
        'timeout_s':         90,
        'max_tokens':        8192,
    },
    # Sprint Next steps 3.1 -- the NextStepsPipeline's own entry
    # (NEXT_STEPS_PROVIDER below): gpt-5.6-terra + Structured Outputs, prompt
    # v1 unchanged, measured by evals/next_steps against the gpt-4o-mini
    # baseline. Same limits as the People entry, for the same reasons
    # (reasoning tokens count in max_tokens). timeout_s 90 is NOT yet inside
    # the R2 budget: the view runs this pipeline AFTER the qualification one
    # in the same request (~150 s budgeted), within the ~180 s polling window
    # -- kept until the eval measures the real durations (mean / max
    # duration_ms).
    'openai_next_steps': {
        'provider':          'openai',
        'model':             'gpt-5.6-terra',
        'reasoning_effort':  'medium',
        'timeout_s':         90,
        'max_tokens':        8192,
    },
    # Sprint « Deal health v2 », step 5 -- the deal health's own entries
    # (DEAL_HEALTH_LLM_PROVIDER below picks one), the NEXT_STEPS pattern
    # above: Structured Outputs, a model chosen for quality (configurable:
    # AI_PIPELINES_DEAL_HEALTH_MODEL; final choice at step 7), its own timeout.
    'openai_deal_health': {
        'provider':          'openai',
        'model':             getattr(settings, 'AI_PIPELINES_DEAL_HEALTH_MODEL', 'gpt-5.6-terra'),
        'reasoning_effort':  'medium',
        'timeout_s':         DEAL_HEALTH_TIMEOUT_S,
        'max_tokens':        DEAL_HEALTH_MAX_TOKENS,
    },
    # Step 7 -- the CHALLENGER of the deal health's model, DECLARED for the
    # evaluation only (evals/deal_health: model Y of the format x model
    # matrix) -- never wired: DEAL_HEALTH_LLM_PROVIDER picks openai or claude.
    # gpt-5.4: the full model of the 5.4 line (gpt-5.4-mini is declared
    # above), quality tier; same options as openai_deal_health.
    'openai_deal_health_challenger': {
        'provider':          'openai',
        'model':             'gpt-5.4',
        'reasoning_effort':  'medium',
        'timeout_s':         DEAL_HEALTH_TIMEOUT_S,
        'max_tokens':        DEAL_HEALTH_MAX_TOKENS,
    },
    # Sub-step 5b -- the deal health on Claude (DEAL_HEALTH_LLM_PROVIDER below
    # = 'claude', ANTHROPIC_API_KEY set): a quality-tier model (configurable:
    # AI_PIPELINES_DEAL_HEALTH_CLAUDE_MODEL), Structured Outputs through
    # output_config.format, the effort sent as output_config.effort, no
    # temperature; the same timeout and token budget as openai_deal_health.
    'claude_deal_health': {
        'provider':          'claude',
        'model':             getattr(settings, 'AI_PIPELINES_DEAL_HEALTH_CLAUDE_MODEL', 'claude-opus-5-5'),
        'reasoning_effort':  'medium',
        'timeout_s':         DEAL_HEALTH_TIMEOUT_S,
        'max_tokens':        DEAL_HEALTH_MAX_TOKENS,
    },
    # Sprint 2 Game Plan, G2 -- the prep call's OWN entries (the deal health's
    # pattern; PREP_CALL_LLM_PROVIDER below picks one). openai_prep_call keeps
    # exactly what the prep call ran on until now (the active 'openai' entry),
    # so this sub-step changes nothing in production; claude_prep_call mirrors
    # claude_deal_health's model (configurable:
    # AI_PIPELINES_PREP_CALL_CLAUDE_MODEL). Models, timeouts and budgets are
    # settled by the Game Plan evaluation (G13).
    'openai_prep_call': {
        'provider':    'openai',
        'model':       'gpt-4o-mini',
        'timeout_s':   30,
        'max_tokens':  4096,
    },
    # Sprint 2 Game Plan, G13 -- model X of the Game Plan evaluation: the
    # deal health's model with its options, DECLARED for the evaluation only
    # (evals/game_plan) -- never wired: PREP_CALL_LLM_PROVIDER picks openai
    # (openai_prep_call, model Y) or claude.
    'openai_prep_call_terra': {
        'provider':          'openai',
        'model':             'gpt-5.6-terra',
        'reasoning_effort':  'medium',
        'timeout_s':         DEAL_HEALTH_TIMEOUT_S,
        'max_tokens':        DEAL_HEALTH_MAX_TOKENS,
    },
    'claude_prep_call': {
        'provider':          'claude',
        'model':             getattr(settings, 'AI_PIPELINES_PREP_CALL_CLAUDE_MODEL', 'claude-opus-5-5'),
        'reasoning_effort':  'medium',
        'timeout_s':         90,
        'max_tokens':        8192,
    },
})


# THE switch of the deal health's LLM provider (amendment A11 — ONE value in
# the module's configuration, never an environment variable: the .env holds
# the secrets only). 'openai' -> PROVIDER_CONFIG['openai_deal_health'],
# 'claude' -> PROVIDER_CONFIG['claude_deal_health'] (constants
# DEAL_HEALTH_PROVIDER_KEYS). 'claude' needs ANTHROPIC_API_KEY, checked at load
# (pipelines/deal_health.check_deal_health_provider). Only the deal health
# reads it. See README.md.
DEAL_HEALTH_LLM_PROVIDER = 'openai'


# THE switch of the prep call / Game Plan's LLM provider (sprint 2 Game Plan,
# G2 — the deal health's exact pattern, TD-319 extended: ONE value in the
# module's configuration, never an environment variable). 'openai' ->
# PROVIDER_CONFIG['openai_prep_call'], 'claude' -> PROVIDER_CONFIG
# ['claude_prep_call'] (constants PREP_CALL_PROVIDER_KEYS). 'claude' needs
# ANTHROPIC_API_KEY, checked at load (pipelines/prep_call.
# check_prep_call_provider). Only the prep call reads it.
PREP_CALL_LLM_PROVIDER = 'openai'


# =============================================================================
# MODEL PER STAGE (TD-279 P1)
# =============================================================================

# Stage name -> PROVIDER_CONFIG key. A stage absent from the map uses the
# active provider (ACTIVE_PROVIDER) exactly as before. Stage names are the
# transcript_signals stages (checked at load in that module).
#
# Override in Django settings:
#     AI_PIPELINES_STAGE_PROVIDER = {'people': 'openai_people'}
STAGE_PROVIDER = getattr(settings, 'AI_PIPELINES_STAGE_PROVIDER', {
    'people': 'openai_people',
})


# =============================================================================
# MODEL OF THE NEXT STEPS PIPELINE (Sprint Next steps 3.1)
# =============================================================================

# PROVIDER_CONFIG key of the single-stage NextStepsPipeline (its run row,
# its call). Checked at load, with its response schema, by the pipeline
# itself (pipelines/next_steps.py check_next_steps_provider).
#
# Override in Django settings:
#     AI_PIPELINES_NEXT_STEPS_PROVIDER = 'openai'   # back to gpt-4o-mini
NEXT_STEPS_PROVIDER = getattr(
    settings, 'AI_PIPELINES_NEXT_STEPS_PROVIDER', 'openai_next_steps',
)


# =============================================================================
# TRANSCRIPT INPUT BOUNDS
# =============================================================================

# Minimum transcript length in characters accepted by the
# TranscriptSignalsExtractInputSerializer. Filters out trivial inputs
# ("ok", "test", "x") that would consume LLM quota for no value. The
# unit is characters — a coarse heuristic that doesn't need tokeniser
# accuracy at the input layer.
#
# Override:
#     AI_PIPELINES_MIN_TRANSCRIPT_LENGTH = 100
MIN_TRANSCRIPT_LENGTH = getattr(
    settings, 'AI_PIPELINES_MIN_TRANSCRIPT_LENGTH', 50,
)

# Maximum transcript length in characters. Caps inputs to avoid
# runaway cost / latency on very long transcripts. 50,000 characters
# ≈ 12,500 English tokens — generous for a 1-hour sales call.
# Raise this when customers legitimately need multi-hour content.
#
# Override:
#     AI_PIPELINES_MAX_TRANSCRIPT_LENGTH = 100_000
MAX_TRANSCRIPT_LENGTH = getattr(
    settings, 'AI_PIPELINES_MAX_TRANSCRIPT_LENGTH', 50_000,
)


# =============================================================================
# HELPERS
# =============================================================================

def get_active_provider_config():
    """
    Return the config dict for the currently active provider.

    Raises:
        KeyError when ACTIVE_PROVIDER points to an unregistered
        provider. Raised at call time (in addition to the module-load
        sanity check below) for runtime robustness in case the active
        provider is changed after first import.
    """
    if ACTIVE_PROVIDER not in PROVIDER_CONFIG:
        raise KeyError(
            f"AI_PIPELINES_ACTIVE_PROVIDER='{ACTIVE_PROVIDER}' is not "
            f"in PROVIDER_CONFIG. Registered keys: "
            f"{sorted(PROVIDER_CONFIG.keys())}."
        )
    return PROVIDER_CONFIG[ACTIVE_PROVIDER]


# =============================================================================
# SANITY CHECK — fail fast at module load
# =============================================================================
#
# A misconfigured ACTIVE_PROVIDER should fail at Django startup, not
# at the first user-facing extraction request. Importing this module
# (which happens when app_modules.ai_pipelines is ready) will raise
# below before any view can run.
if ACTIVE_PROVIDER not in PROVIDER_CONFIG:
    raise ImportError(
        f"AI Pipelines configuration error: "
        f"AI_PIPELINES_ACTIVE_PROVIDER='{ACTIVE_PROVIDER}' is not in "
        f"PROVIDER_CONFIG. Available keys: "
        f"{sorted(PROVIDER_CONFIG.keys())}. "
        f"Fix AI_PIPELINES_ACTIVE_PROVIDER or AI_PIPELINES_PROVIDER_CONFIG "
        f"in your Django settings."
    )


def check_stage_provider(stage_provider, provider_config):
    """
    TD-279 P1 sanity check (same rule as ACTIVE_PROVIDER): every stage must
    point to a PROVIDER_CONFIG key. Raises ImportError so a misconfiguration
    fails at Django startup.
    """
    unknown = {stage: key for stage, key in stage_provider.items() if key not in provider_config}
    if unknown:
        raise ImportError(
            f"AI Pipelines configuration error: AI_PIPELINES_STAGE_PROVIDER "
            f"{unknown} -- key(s) not in PROVIDER_CONFIG. Available keys: "
            f"{sorted(provider_config.keys())}."
        )


check_stage_provider(STAGE_PROVIDER, PROVIDER_CONFIG)
