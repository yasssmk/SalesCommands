# app_modules/ai_pipelines/providers/base.py
"""
Abstract base for LLM providers.

Defines the single-call surface that all concrete providers must
implement, plus the exception hierarchy raised on common failure
modes. The orchestrator (pipelines/base.py) consumes both:

  - The return type (LLMCallResult) for happy-path data and audit
    metadata (token counts, duration, actual model used).
  - The exception hierarchy for terminal status mapping
    (LLMTimeoutError -> AIPipelineStatus.TIMEOUT, etc.).

Design intent
-------------
Single method (`call`) — no streaming, no function calling, no async
batches. The MVP use case is structured JSON extraction with a known
prompt -> response shape. Additional surface is deferred until a
concrete need arises.

All concrete providers must:

  * Map their SDK's specific exception types onto LLMTimeoutError /
    LLMRateLimitError / LLMAuthError / LLMProviderError before
    raising. The orchestrator must NEVER see provider-specific
    exception classes — that would couple the pipeline layer to a
    particular SDK and break the "single point of switch" guarantee
    in config.ACTIVE_PROVIDER.

  * Return an LLMCallResult populated with measured duration and
    token counts. Falsifying any of these breaks the audit trail;
    missing values are caught downstream by the orchestrator and
    surface as PROVIDER_ERROR.

  * Stay stateless. SDK clients are instantiated lazily inside
    `call` (or memoised per provider instance) — never carry per-
    request state on the provider object.
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass


# =============================================================================
# RETURN TYPE
# =============================================================================

@dataclass(frozen=True)
class LLMCallResult:
    """
    Standardised return type for every LLMProvider.call().

    Fields:
      content        Raw response text. Typically JSON to be parsed
                     by the pipeline — the provider does not attempt
                     to parse it.
      input_tokens   Tokens consumed by the prompt (system + user).
                     Reported by the SDK; never zero on a successful
                     call.
      output_tokens  Tokens generated in the response.
      model_used     Actual model identifier that produced the
                     response. May differ from the requested model
                     when the provider auto-routes (Anthropic does
                     this for some legacy aliases). Captured for
                     audit fidelity.
      duration_ms    Wall-clock duration of the SDK call, measured
                     by the provider wrapper via time.perf_counter().
                     Includes serialization + network + provider
                     processing — i.e. what the caller actually
                     waited for.

    Frozen dataclass: results are immutable once produced. Prevents
    accidental mutation by downstream consumers (orchestrator,
    audit logger).
    """
    content: str
    input_tokens: int
    output_tokens: int
    model_used: str
    duration_ms: int


# =============================================================================
# EXCEPTIONS
# =============================================================================

class LLMProviderError(Exception):
    """
    Generic provider error — catch-all for unexpected SDK exceptions.

    Concrete providers should map their SDK's specific exception
    types onto the specialised subclasses below where possible, and
    fall back to LLMProviderError for anything else (5xx, content
    filter trigger, transient connection errors that are not a clear
    timeout).

    The orchestrator maps any LLMProviderError onto
    AIPipelineStatus.LLM_ERROR — except for the three specialised
    subclasses which map onto more specific terminal states.
    """
    pass


class LLMTimeoutError(LLMProviderError):
    """
    SDK call exceeded the configured per-call timeout.

    Mapped by the orchestrator to AIPipelineStatus.TIMEOUT.
    """
    pass


class LLMRateLimitError(LLMProviderError):
    """
    SDK returned a rate-limit signal (HTTP 429 or equivalent).

    Mapped by the orchestrator to AIPipelineStatus.LLM_ERROR with a
    distinct error_message — the rep is told to retry shortly.
    """
    pass


class LLMAuthError(LLMProviderError):
    """
    SDK returned an authentication failure (HTTP 401 / 403 or
    equivalent).

    Surfaces a configuration problem — the API key is missing,
    rotated, or revoked. The rep is told to contact their admin.
    """
    pass


# =============================================================================
# ABSTRACT PROVIDER
# =============================================================================

class LLMProvider(ABC):
    """
    Abstract base for a single-call LLM provider.

    Concrete subclasses implement `call(...)` and are instantiated by
    the factory in providers/__init__.py. The orchestrator NEVER
    instantiates a provider directly — it goes through
    get_active_provider() so the active key from config can be
    swapped without touching the call sites.
    """

    @abstractmethod
    def call(
        self,
        *,
        system: str,
        user: str,
        temperature: float,
        model: str,
        max_tokens: int,
        timeout_s: int,
    ) -> LLMCallResult:
        """
        Perform a single LLM call.

        Args:
          system        System prompt (role, output format, hard rules).
          user          User prompt (task spec + dynamic payload).
          temperature   Sampling temperature (typically 0.0 for
                        structured extraction).
          model         Model identifier to pass to the SDK.
          max_tokens    Ceiling on response tokens.
          timeout_s     Per-call timeout in seconds.

        Returns:
          LLMCallResult with content + token counts + measured
          duration_ms + the actual model_used by the provider.

        Raises:
          LLMTimeoutError    on per-call timeout.
          LLMRateLimitError  on provider rate limiting.
          LLMAuthError       on auth failure.
          LLMProviderError   on any other SDK error not classified
                             into the above.

        Implementation notes:
          * The wall-clock duration is measured by the provider via
            time.perf_counter() — the abstract base offers
            _measure_duration_ms() as a helper.
          * The SDK's own retry policy (rate-limit backoff, etc.)
            applies — providers do NOT add an outer retry loop.
            Whether to retry an entire stage is the orchestrator's
            decision.
        """
        raise NotImplementedError

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    @staticmethod
    def _measure_duration_ms(start_perf_counter: float) -> int:
        """
        Compute elapsed milliseconds from a time.perf_counter() mark.

        Usage:
            start = time.perf_counter()
            ...SDK call...
            duration = self._measure_duration_ms(start)

        Rationale:
          time.perf_counter() is the recommended high-resolution
          monotonic clock for measuring intervals. time.time() is
          subject to system clock adjustments and is NOT safe for
          duration measurement.
        """
        return int((time.perf_counter() - start_perf_counter) * 1000)