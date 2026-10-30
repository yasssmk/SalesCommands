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
#                the model name -- decides the mode.
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
})


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
