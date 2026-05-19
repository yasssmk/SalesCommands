# app_modules/ai_pipelines/providers/openai_provider.py
"""
OpenAI provider implementation.

Wraps the openai SDK (pinned at 1.63.2 in requirements.txt) into the
LLMProvider abstraction declared in providers/base.py. Maps the
SDK's specific exception classes onto the generic hierarchy so the
orchestrator stays provider-agnostic.

API key:
  Read from the OPENAI_API_KEY environment variable by the SDK
  directly at client construction. Rotation requires a Django
  restart — the provider does not re-read the env per call.

Retry policy:
  The OpenAI SDK 1.x ships with a default `max_retries=2` for
  transient failures (5xx, connection errors). This provider does
  NOT add an outer retry loop — whether to retry an entire stage
  is the orchestrator's responsibility (decided per pipeline).

Response format:
  Plain-text completion mode (no `response_format={"type":
  "json_object"}`). Reasons:
    * Symmetric with Claude, which has no equivalent strict mode.
    * Cleaner LLMProvider abstraction — no provider-specific
      capabilities leak into the contract.
    * Prompts already enforce JSON-only output. Pipelines re-prompt
      on parse failure (TranscriptSignalsPipeline behavior).

Privacy:
  Logs include model identifier, token counts, and duration only.
  Prompts and responses are NEVER logged — they may contain
  customer transcripts, contact names, and other sensitive payload.
  The settings.SafeExtraFilter would redact such fields anyway,
  but defence-in-depth at the source is preferred.
"""

import logging
import time

from openai import (
    OpenAI,
    APITimeoutError,
    RateLimitError,
    AuthenticationError,
    OpenAIError,
)

from .base import (
    LLMAuthError,
    LLMCallResult,
    LLMProvider,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)


logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """
    OpenAI Chat Completions implementation of LLMProvider.

    Eager client instantiation: the OpenAI() SDK wrapper is created
    at __init__ to share the underlying httpx connection pool across
    all calls. A missing OPENAI_API_KEY surfaces as OpenAIError at
    construction time — fail fast at startup, not at first request.
    """

    def __init__(self) -> None:
        # OpenAI() reads OPENAI_API_KEY from os.environ at this
        # point. Raises OpenAIError when the key is missing or
        # malformed — surfaces at startup which is the desired
        # behavior for a misconfigured deployment.
        self._client = OpenAI()

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
        Perform a single OpenAI chat completion.

        See LLMProvider.call docstring for the abstract contract.

        OpenAI-specific exception mapping:
          openai.APITimeoutError      -> LLMTimeoutError
          openai.RateLimitError       -> LLMRateLimitError
          openai.AuthenticationError  -> LLMAuthError
          openai.OpenAIError (others) -> LLMProviderError

        Defensive extraction:
          response.usage may be None on certain SDK versions or
          response shapes — guarded with getattr defaults.
          response.choices[0].message.content may be None on
          content-filter triggers — surfaced as LLMProviderError
          rather than returning empty content silently.
        """
        start = time.perf_counter()

        try:
            response = self._client.chat.completions.create(
                model=model,
                messages=[
                    {'role': 'system', 'content': system},
                    {'role': 'user',   'content': user},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout_s,
            )

        except APITimeoutError as e:
            duration_ms = self._measure_duration_ms(start)
            logger.warning(
                'OpenAIProvider.call timeout',
                extra={
                    'model':       model,
                    'timeout_s':   timeout_s,
                    'duration_ms': duration_ms,
                },
            )
            raise LLMTimeoutError(str(e)) from e

        except RateLimitError as e:
            logger.warning(
                'OpenAIProvider.call rate-limited',
                extra={'model': model},
            )
            raise LLMRateLimitError(str(e)) from e

        except AuthenticationError as e:
            logger.error(
                'OpenAIProvider.call auth failure',
                extra={'model': model},
            )
            raise LLMAuthError(str(e)) from e

        except OpenAIError as e:
            # Catch-all for OpenAIError subclasses not handled above:
            # APIConnectionError, InternalServerError, BadRequestError,
            # content-filter triggers, etc.
            logger.warning(
                'OpenAIProvider.call provider error',
                extra={
                    'model':      model,
                    'error_type': type(e).__name__,
                },
            )
            raise LLMProviderError(str(e)) from e

        duration_ms = self._measure_duration_ms(start)

        # ----- Usage extraction (defensive) -----
        # response.usage is typically populated for non-streaming
        # completions, but guard against None for SDK quirks.
        usage = getattr(response, 'usage', None)
        if usage:
            input_tokens  = getattr(usage, 'prompt_tokens',     0)
            output_tokens = getattr(usage, 'completion_tokens', 0)
        else:
            input_tokens  = 0
            output_tokens = 0

        # ----- Content extraction (defensive) -----
        # Missing choices or null message.content indicates a
        # malformed response (content filter, truncation at start,
        # ...). Surface as a provider error rather than silently
        # returning empty content.
        try:
            content = response.choices[0].message.content or ''
        except (IndexError, AttributeError) as e:
            raise LLMProviderError(
                f'Malformed OpenAI response — no choices or message: {e!r}'
            ) from e

        if not content:
            raise LLMProviderError(
                'OpenAI returned empty content — possible content filter trigger.'
            )

        # response.model often reflects a more specific version than
        # the requested alias (e.g. "gpt-4o-mini-2024-07-18" when
        # requesting "gpt-4o-mini"). Captured for audit fidelity.
        model_used = getattr(response, 'model', model)

        logger.debug(
            'OpenAIProvider.call success',
            extra={
                'model_requested': model,
                'model_used':      model_used,
                'duration_ms':     duration_ms,
                'input_tokens':    input_tokens,
                'output_tokens':   output_tokens,
            },
        )

        return LLMCallResult(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model_used=model_used,
            duration_ms=duration_ms,
        )