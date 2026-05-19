# app_modules/ai_pipelines/providers/claude_provider.py
"""
Anthropic provider implementation.

Wraps the anthropic SDK (pinned at 0.42.0 in requirements.txt) into
the LLMProvider abstraction declared in providers/base.py. Maps
Anthropic-specific exception classes onto the generic hierarchy so
the orchestrator stays provider-agnostic.

API key:
  Read from the ANTHROPIC_API_KEY environment variable by the SDK
  directly at client construction. Rotation requires a Django
  restart — the provider does not re-read the env per call.

Retry policy:
  The Anthropic SDK 0.42 ships with a default max_retries for
  transient failures (5xx, connection errors). This provider does
  NOT add an outer retry loop — same stance as OpenAIProvider.

Response format:
  Plain-text completion mode. Unlike OpenAI, Anthropic has no
  structured JSON mode — pure prompt engineering enforces JSON
  output. Pipelines handle parse failures by re-prompting.

Notable differences from OpenAI:
  * `system` is a TOP-LEVEL parameter on .messages.create(), not a
    message in the messages array.
  * `response.content` is a LIST of content blocks. For text-only
    responses (no tool use), each block has a `.text` attribute.
    We concatenate the .text of all blocks for robustness against
    future block types and multi-block responses.
  * Token field names are `input_tokens` / `output_tokens`
    (vs OpenAI's `prompt_tokens` / `completion_tokens`).
  * `max_tokens` is REQUIRED.

Privacy:
  Same stance as OpenAIProvider — logs include model identifier,
  token counts, and duration only. Prompts and responses are
  NEVER logged. Defence-in-depth at the source (the
  SafeExtraFilter in settings.LOGGING would redact anyway).
"""

import logging
import time

from anthropic import (
    Anthropic,
    APITimeoutError,
    RateLimitError,
    AuthenticationError,
    APIError,
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


class ClaudeProvider(LLMProvider):
    """
    Anthropic Messages API implementation of LLMProvider.

    Eager client instantiation — Anthropic() reads
    ANTHROPIC_API_KEY from os.environ at __init__. A missing key
    surfaces immediately at startup rather than at first call. The
    factory in providers/__init__.py instantiates ClaudeProvider
    only when config.ACTIVE_PROVIDER == 'claude', so deployments
    using OpenAI do NOT need ANTHROPIC_API_KEY set.
    """

    def __init__(self) -> None:
        # Anthropic() reads ANTHROPIC_API_KEY from os.environ at
        # this point. Raises AuthenticationError when the key is
        # missing or malformed — surfaces at startup which is the
        # desired behavior.
        self._client = Anthropic()

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
        Perform a single Anthropic messages.create completion.

        See LLMProvider.call docstring for the abstract contract.

        Anthropic-specific exception mapping:
          anthropic.APITimeoutError      -> LLMTimeoutError
          anthropic.RateLimitError       -> LLMRateLimitError
          anthropic.AuthenticationError  -> LLMAuthError
          anthropic.APIError (others)    -> LLMProviderError

        Content extraction:
          response.content is a LIST of content blocks. Iterates and
          concatenates the .text of every block that exposes one —
          robust against future block types and multi-block
          responses. Empty content surfaces as LLMProviderError
          rather than silently returning ''.
        """
        start = time.perf_counter()

        try:
            response = self._client.messages.create(
                model=model,
                system=system,
                messages=[
                    {'role': 'user', 'content': user},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout_s,
            )

        except APITimeoutError as e:
            duration_ms = self._measure_duration_ms(start)
            logger.warning(
                'ClaudeProvider.call timeout',
                extra={
                    'model':       model,
                    'timeout_s':   timeout_s,
                    'duration_ms': duration_ms,
                },
            )
            raise LLMTimeoutError(str(e)) from e

        except RateLimitError as e:
            logger.warning(
                'ClaudeProvider.call rate-limited',
                extra={'model': model},
            )
            raise LLMRateLimitError(str(e)) from e

        except AuthenticationError as e:
            logger.error(
                'ClaudeProvider.call auth failure',
                extra={'model': model},
            )
            raise LLMAuthError(str(e)) from e

        except APIError as e:
            # Catch-all base for the remaining Anthropic exception
            # subclasses: APIConnectionError, PermissionDeniedError,
            # BadRequestError, InternalServerError, content filter
            # trigger, etc.
            logger.warning(
                'ClaudeProvider.call provider error',
                extra={
                    'model':      model,
                    'error_type': type(e).__name__,
                },
            )
            raise LLMProviderError(str(e)) from e

        duration_ms = self._measure_duration_ms(start)

        # ----- Usage extraction (defensive) -----
        usage = getattr(response, 'usage', None)
        if usage:
            input_tokens  = getattr(usage, 'input_tokens',  0)
            output_tokens = getattr(usage, 'output_tokens', 0)
        else:
            input_tokens  = 0
            output_tokens = 0

        # ----- Content extraction (defensive) -----
        # response.content is a LIST of content blocks (TextBlock,
        # ToolUseBlock, ...). For our prompts we expect only
        # TextBlock(s). Concatenate the .text of every block that
        # exposes one — robust against future block types and
        # multi-block responses. Empty content surfaces as a
        # provider error rather than silently returning ''.
        blocks = getattr(response, 'content', None) or []
        text_parts = [getattr(b, 'text', '') for b in blocks]
        content = ''.join(text_parts)

        if not content:
            raise LLMProviderError(
                'Anthropic returned no text content — possible content '
                'filter trigger or unexpected block-only response.'
            )

        # response.model echoes the requested model identifier
        # (Anthropic does not auto-route to a more specific version
        # like OpenAI does). Captured for audit fidelity.
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