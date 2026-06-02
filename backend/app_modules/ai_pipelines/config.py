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
Temperature is intentionally NOT a config-level value. Each pipeline
class declares its own TEMPERATURE constant (e.g.
TranscriptSignalsPipeline.TEMPERATURE = 0.0 for deterministic
extraction). Pipelines with different determinism requirements
(creative generation vs. structured extraction) should not share a
single global temperature — keep it inside the pipeline.
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
})


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
# DEPRECATION — old endpoint sunset
# =============================================================================

# ISO-8601 date after which /transcript-signals/extract/ may be removed.
# 6 months from Sprint B5 merge (June 2026). Referenced by the Deprecation
# + Sunset headers added to the old view (see TD-10 in TECH_DEBT.md).
TRANSCRIPT_SIGNALS_SUNSET_DATE = '2026-12-01'


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