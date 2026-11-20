# app_modules/ai_pipelines/providers/claude_provider.py
"""
Anthropic provider implementation.

Wraps the anthropic SDK (pinned at 1.17.0 in requirements.txt — sub-step 5b
of sprint « Deal health v2 ») into the LLMProvider abstraction declared in
providers/base.py, on the contract of OpenAIProvider (openai_provider.py):
same parameters, same LLMCallResult, the Anthropic exceptions mapped onto the
same generic hierarchy, so the orchestrator stays provider-agnostic.

API key:
  Read from the ANTHROPIC_API_KEY environment variable by the SDK at client
  construction (REQUIRED_ENV_KEY — checked at load for the deal health:
  pipelines/deal_health.check_deal_health_provider). Rotation requires a
  Django restart — the provider does not re-read the env per call.

Retry policy:
  The SDK retries transient failures itself (connection errors, 408, 409,
  429, 5xx; max_retries 2 by default). This provider does NOT add an outer
  retry loop — same stance as OpenAIProvider.

Request (TD-279 P0 options, per call — the OpenAIProvider ones):
  * response_schema  -> output_config.format {type: json_schema, schema}
                        (Structured Outputs; SUPPORTS_RESPONSE_SCHEMA);
  * reasoning_effort -> output_config.effort;
  * temperature      -> sent (as extra_body: the 1.x SDK has no
                        `temperature` argument) ONLY to the models of
                        constants.CLAUDE_MODELS_ACCEPTING_TEMPERATURE —
                        recent models answer 400 to it;
  * the models of constants.CLAUDE_REFUSAL_FALLBACK_MODELS are called on
    the beta Messages endpoint with the server-side refusal fallback
    (CLAUDE_REFUSAL_FALLBACKS, beta CLAUDE_REFUSAL_FALLBACK_BETA).
  In the structured / reasoning mode, a refusal of the whole chain
  (stop_reason 'refusal') or a truncated answer (stop_reason 'max_tokens')
  raises LLMProviderError — as OpenAIProvider for its refusal / 'length'.

Notable differences from OpenAI:
  * `system` is a TOP-LEVEL parameter, not a message.
  * `response.content` is a LIST of content blocks; the .text of every
    text block is concatenated (a fallback block carries no text).
  * Token fields are `input_tokens` / `output_tokens`.
  * `max_tokens` is REQUIRED.

Privacy:
  Same stance as OpenAIProvider — logs include model identifier, token
  counts, and duration only. Prompts and responses are NEVER logged.
"""

import logging
import time

from anthropic import (
    Anthropic,
    APIError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)

from ..constants import (
    CLAUDE_MODELS_ACCEPTING_TEMPERATURE,
    CLAUDE_REFUSAL_FALLBACK_BETA,
    CLAUDE_REFUSAL_FALLBACK_MODELS,
    CLAUDE_REFUSAL_FALLBACKS,
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

_STOP_REFUSAL = 'refusal'
_STOP_MAX_TOKENS = 'max_tokens'


class ClaudeProvider(LLMProvider):
    """
    Anthropic Messages API implementation of LLMProvider.

    Eager client instantiation — the SDK client (and its connection pool) is
    shared by every call. The anthropic SDK 1.x does not raise at
    construction for a missing key: the deal health checks REQUIRED_ENV_KEY
    at load; any other caller gets LLMAuthError at the first call.
    """

    SUPPORTS_RESPONSE_SCHEMA = True
    REQUIRED_ENV_KEY = 'ANTHROPIC_API_KEY'

    def __init__(self) -> None:
        self._client = Anthropic()

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
        Perform a single Anthropic Messages completion.

        See LLMProvider.call docstring for the abstract contract, and the
        module docstring for the request options.

        Anthropic-specific exception mapping:
          anthropic.APITimeoutError      -> LLMTimeoutError
          anthropic.RateLimitError       -> LLMRateLimitError
          anthropic.AuthenticationError  -> LLMAuthError
          anthropic.APIError (others)    -> LLMProviderError
        """
        kwargs = {
            'model': model,
            'system': system,
            'messages': [{'role': 'user', 'content': user}],
            'max_tokens': max_tokens,
            'timeout': timeout_s,
        }
        output_config = {}
        if response_schema is not None:
            output_config['format'] = {
                'type': 'json_schema',
                'schema': response_schema['schema'],
            }
        if reasoning_effort is not None:
            output_config['effort'] = reasoning_effort
        if output_config:
            kwargs['output_config'] = output_config
        if temperature is not None and model in CLAUDE_MODELS_ACCEPTING_TEMPERATURE:
            kwargs['extra_body'] = {'temperature': temperature}
        strict_mode = response_schema is not None or reasoning_effort is not None

        start = time.perf_counter()
        try:
            if model in CLAUDE_REFUSAL_FALLBACK_MODELS:
                response = self._client.beta.messages.create(
                    betas=[CLAUDE_REFUSAL_FALLBACK_BETA],
                    fallbacks=CLAUDE_REFUSAL_FALLBACKS,
                    **kwargs,
                )
            else:
                response = self._client.messages.create(**kwargs)

        except APITimeoutError as e:
            duration_ms = self._measure_duration_ms(start)
            logger.warning(
                'ClaudeProvider.call timeout',
                extra={'model': model, 'timeout_s': timeout_s, 'duration_ms': duration_ms},
            )
            raise LLMTimeoutError(str(e)) from e

        except RateLimitError as e:
            logger.warning('ClaudeProvider.call rate-limited', extra={'model': model})
            raise LLMRateLimitError(str(e)) from e

        except AuthenticationError as e:
            logger.error('ClaudeProvider.call auth failure', extra={'model': model})
            raise LLMAuthError(str(e)) from e

        except APIError as e:
            # The remaining Anthropic errors: APIConnectionError,
            # PermissionDeniedError, BadRequestError, InternalServerError, ...
            logger.warning(
                'ClaudeProvider.call provider error',
                extra={'model': model, 'error_type': type(e).__name__},
            )
            raise LLMProviderError(str(e)) from e

        duration_ms = self._measure_duration_ms(start)

        usage = getattr(response, 'usage', None)
        input_tokens = getattr(usage, 'input_tokens', 0) if usage else 0
        output_tokens = getattr(usage, 'output_tokens', 0) if usage else 0

        stop_reason = getattr(response, 'stop_reason', None)
        if strict_mode and stop_reason == _STOP_REFUSAL:
            raise LLMProviderError('Anthropic refused the request (stop_reason "refusal").')
        if strict_mode and stop_reason == _STOP_MAX_TOKENS:
            raise LLMProviderError(
                'Anthropic answer truncated (stop_reason "max_tokens") -- '
                'raise max_tokens for this entry.'
            )

        blocks = getattr(response, 'content', None) or []
        # The .text of every block exposing one (a fallback or thinking block
        # carries none).
        content = ''.join(getattr(b, 'text', '') or '' for b in blocks)
        if not content:
            raise LLMProviderError(
                'Anthropic returned no text content — possible refusal or an '
                'unexpected block-only response.'
            )

        model_used = getattr(response, 'model', model)
        logger.debug(
            'ClaudeProvider.call success',
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
