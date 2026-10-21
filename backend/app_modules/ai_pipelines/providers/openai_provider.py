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
  By default, plain-text completion mode (no `response_format={"type":
  "json_object"}`). Reasons:
    * Symmetric with Claude, which has no equivalent strict mode.
    * Cleaner LLMProvider abstraction — no provider-specific
      capabilities leak into the contract.
    * Prompts already enforce JSON-only output. Pipelines re-prompt
      on parse failure (TranscriptSignalsPipeline behavior).
  TD-279 P0 -- OPTIONAL, per call (default = unchanged):
    * response_schema -> response_format json_schema, strict;
    * reasoning_effort -> reasoning-model mode: reasoning_effort sent,
      max_completion_tokens instead of max_tokens, temperature NOT sent
      (driven by the caller's config, never by the model name);
    * in either mode, a refusal or a truncated answer (finish_reason
      "length") raises LLMProviderError -- in the default mode the
      content is still returned (the pipeline's parse retry decides).

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

    SUPPORTS_RESPONSE_SCHEMA = True

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
        temperature: float | None,
        model: str,
        max_tokens: int,
        timeout_s: int,
        response_schema: dict | None = None,
        reasoning_effort: str | None = None,
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

        kwargs = {
            'model': model,
            'messages': [
                {'role': 'system', 'content': system},
                {'role': 'user',   'content': user},
            ],
            'timeout': timeout_s,
        }
        if reasoning_effort is not None:
            # Reasoning-model mode: no temperature, completion budget.
            kwargs['reasoning_effort'] = reasoning_effort
            kwargs['max_completion_tokens'] = max_tokens
        else:
            if temperature is not None:
                kwargs['temperature'] = temperature
            kwargs['max_tokens'] = max_tokens
        if response_schema is not None:
            kwargs['response_format'] = {
                'type': 'json_schema',
                'json_schema': {
                    'name':   response_schema['name'],
                    'schema': response_schema['schema'],
                    'strict': True,
                },
            }
        strict_mode = response_schema is not None or reasoning_effort is not None

        try:
            response = self._client.chat.completions.create(**kwargs)

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
            details = getattr(usage, 'completion_tokens_details', None)
            reasoning_tokens = getattr(details, 'reasoning_tokens', 0) or 0
        else:
            input_tokens  = 0
            output_tokens = 0
            reasoning_tokens = 0

        # ----- Content extraction (defensive) -----
        # Missing choices or null message.content indicates a
        # malformed response (content filter, truncation at start,
        # ...). Surface as a provider error rather than silently
        # returning empty content.
        try:
            choice = response.choices[0]
            content = choice.message.content or ''
        except (IndexError, AttributeError) as e:
            raise LLMProviderError(
                f'Malformed OpenAI response — no choices or message: {e!r}'
            ) from e

        if strict_mode:
            # Structured / reasoning mode only (TD-279 P0): a refusal or a
            # truncated answer is never handed over as content.
            if getattr(choice.message, 'refusal', None):
                raise LLMProviderError('OpenAI refused the request (structured output refusal).')
            if getattr(choice, 'finish_reason', None) == 'length':
                raise LLMProviderError(
                    'OpenAI answer truncated (finish_reason "length") -- '
                    'max_tokens too low for this call.'
                )

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
            reasoning_tokens=reasoning_tokens,
        )