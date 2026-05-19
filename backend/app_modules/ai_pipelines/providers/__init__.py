# app_modules/ai_pipelines/providers/__init__.py
"""
Provider factory and public re-exports.

This is the single entry point pipelines use to obtain an LLMProvider
instance. The factory reads config.ACTIVE_PROVIDER, instantiates the
matching provider class lazily, and caches the result as a
module-level singleton.

Why singleton:
  Provider instances hold SDK client objects (OpenAI, Anthropic)
  which carry httpx connection pools. Recreating them per call would
  re-establish TCP+TLS handshakes every time. The singleton keeps
  the pool warm for the life of the Django process.

Why lazy:
  Eager instantiation at module import would force every Django
  process — management commands, test runner, collectstatic, ... —
  to load the LLM SDK clients even when no LLM call will be made.
  With lazy init, the SDK client is instantiated only on the first
  call to get_active_provider().

  Side effect: a missing or invalid API key surfaces at the first
  user-facing extraction request rather than at server startup. The
  trade-off is acceptable because:
    * config.py sanity-checks ACTIVE_PROVIDER vs PROVIDER_CONFIG
      keys at module load (catches typos in the config).
    * Neither OpenAI nor Anthropic SDK 1.x performs a synchronous
      credential check at instantiation — both defer auth to the
      first request. So even eager instantiation would not actually
      validate the key earlier.

Thread safety:
  The lazy init is NOT thread-safe. A race between two concurrent
  first-call threads can produce two provider instances, with the
  later write overwriting the earlier. This is acceptable for the
  MVP — no data corruption, just a transient double instantiation.
  A threading.Lock could be added if the cost ever becomes visible.

Resetting the cache:
  reset_provider_cache() clears the singleton — intended for tests
  that swap providers mid-run. Concurrent requests during a reset
  would see partial state, so it is NOT safe to call in production.
"""

from .. import config

from .base import (
    LLMAuthError,
    LLMCallResult,
    LLMProvider,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from .openai_provider import OpenAIProvider
from .claude_provider import ClaudeProvider


# =============================================================================
# PROVIDER REGISTRY
# =============================================================================

# Maps config.ACTIVE_PROVIDER values to their concrete provider class.
# Keys MUST match the keys of config.PROVIDER_CONFIG (both are
# cross-checked: config.py raises ImportError at load if
# ACTIVE_PROVIDER points outside PROVIDER_CONFIG; this factory raises
# KeyError at first call if it points outside _PROVIDER_REGISTRY).
#
# Adding a new provider:
#   1. Create a new module under providers/ implementing LLMProvider.
#   2. Add an entry here mapping its config key to the class.
#   3. Add a matching entry to config.PROVIDER_CONFIG with model,
#      timeout, and max_tokens defaults.
_PROVIDER_REGISTRY = {
    'openai': OpenAIProvider,
    'claude': ClaudeProvider,
}


# =============================================================================
# SINGLETON CACHE
# =============================================================================

_active_provider_instance: LLMProvider | None = None


# =============================================================================
# FACTORY
# =============================================================================

def get_active_provider() -> LLMProvider:
    """
    Return the singleton LLMProvider instance matching
    config.ACTIVE_PROVIDER.

    Lazy: instantiates on first call, caches for subsequent calls.
    The SDK client and its connection pool live for the life of the
    Django process.

    Returns:
        Concrete provider instance (OpenAIProvider, ClaudeProvider,
        ...). Pipelines call .call(...) on the returned object —
        they never branch on the concrete type.

    Raises:
        KeyError when config.ACTIVE_PROVIDER points to an
            unregistered key. Under normal circumstances this is
            caught by config.py's load-time sanity check first; the
            re-check here covers runtime config changes (rare).

        Exceptions from the provider's __init__ propagate as-is.
        Neither OpenAI nor Anthropic SDK 1.x raises at construction
        for missing credentials — auth errors surface from .call()
        as LLMAuthError instead.
    """
    global _active_provider_instance

    if _active_provider_instance is None:
        provider_class = _PROVIDER_REGISTRY.get(config.ACTIVE_PROVIDER)
        if provider_class is None:
            raise KeyError(
                f"config.ACTIVE_PROVIDER='{config.ACTIVE_PROVIDER}' "
                f"is not registered in providers/__init__.py. "
                f"Registered: {sorted(_PROVIDER_REGISTRY.keys())}."
            )
        _active_provider_instance = provider_class()

    return _active_provider_instance


def reset_provider_cache() -> None:
    """
    Clear the singleton provider cache.

    Intended for test setups that need to swap providers between
    test cases. NOT safe in production — concurrent requests during
    a reset would observe partial state.
    """
    global _active_provider_instance
    _active_provider_instance = None


# =============================================================================
# PUBLIC API
# =============================================================================

__all__ = [
    # Factory
    'get_active_provider',
    'reset_provider_cache',
    # Abstract base + return type
    'LLMProvider',
    'LLMCallResult',
    # Exception hierarchy
    'LLMProviderError',
    'LLMTimeoutError',
    'LLMRateLimitError',
    'LLMAuthError',
    # Concrete providers — rarely needed directly; pipelines
    # should go through get_active_provider().
    'OpenAIProvider',
    'ClaudeProvider',
]