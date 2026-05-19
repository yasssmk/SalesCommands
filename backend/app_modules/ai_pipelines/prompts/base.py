# app_modules/ai_pipelines/prompts/base.py
"""
Prompt assembly and response handling.

Three layers are assembled into the (system_prompt, user_prompt) pair
that LLMProvider.call() expects:

  1. system  — role, output rules, hard constraints. Largely static
                within a pipeline use case.
  2. context — dynamic tenant / account / activity context. Built at
                run time by the pipeline.
  3. request — task spec plus the actual payload (transcript, etc.).

Plus response-side helpers:

  - strip_fences  : remove ```json ... ``` markdown wrappers that
                    Claude (and occasionally OpenAI) add despite
                    explicit instructions to the contrary.
  - parse_json    : json.loads wrapped in a typed PromptParseError.
  - parse_response: convenience combo of strip_fences + parse_json.

Privacy:
  Helpers DO NOT log response content. Parse failures raise
  PromptParseError carrying the failure reason + position only.
  The orchestrator (pipelines/base.py) decides how much of the
  failed payload to persist in AIPipelineRun.sub_calls for support
  diagnostics.

Where re-prompting lives:
  NOT here. Re-prompt logic requires access to the LLMProvider and
  belongs in the pipeline orchestrator (F.1 pipelines/base.py).
  The builder simply surfaces parse failures via PromptParseError;
  the orchestrator catches and decides whether to retry the stage.
"""

from __future__ import annotations

import json
import re
from typing import Any


# =============================================================================
# EXCEPTIONS
# =============================================================================

class PromptParseError(Exception):
    """
    Raised when an LLM response cannot be parsed as the expected JSON
    structure.

    The orchestrator catches this and decides whether to:
      * Re-prompt the LLM with a "Your previous response was not
        valid JSON. Retry, JSON only." instruction.
      * Surface as a parse_error sub-call status in
        AIPipelineRun.sub_calls and move on.
    """
    pass


# =============================================================================
# REGEX — fence stripping
# =============================================================================

# Match content that is ENTIRELY wrapped in a single markdown fence.
#
# Accepted shapes:
#   ```json\n{"x":1}\n```
#   ```JSON\n{"x":1}\n```
#   ```\n{"x":1}\n```
#   ```yaml\n...\n```          (any language tag — we don't enforce)
#
# Surrounding whitespace tolerated. Inner content captured in group 1.
#
# The pattern is intentionally STRICT: it requires the entire content
# to be fence-wrapped (^...$). Responses with internal fences mixed
# into commentary do NOT match — we leave them alone and let the
# downstream parse fail, which surfaces a clear parse_error rather
# than partially-extracted content that might look superficially OK.
_FENCE_RE = re.compile(
    r'^\s*```[a-zA-Z]*\s*\n(.*?)\n?\s*```\s*$',
    re.DOTALL,
)


# =============================================================================
# PROMPT BUILDER
# =============================================================================

class PromptBuilder:
    """
    Static helpers for 3-layer prompt assembly and response handling.

    The class is a namespace — no state, no instances. All methods
    are static.
    """

    # -------------------------------------------------------------------------
    # ASSEMBLY
    # -------------------------------------------------------------------------

    @staticmethod
    def assemble(
        system: str,
        context: str,
        request: str,
    ) -> tuple[str, str]:
        """
        Assemble the 3 layers into (system_prompt, user_prompt).

        Mapping:
            system layer             -> system_prompt
            context + request layers -> user_prompt
                                        (separated by '\\n\\n---\\n\\n')

        The `---` separator is a Markdown horizontal rule that LLMs
        reliably treat as a section break. Using it consistently lets
        prompt authors target either side ("Use the context above to
        ..." / "Below the rule, you'll find ...") without ambiguity.

        All inputs are stripped of leading / trailing whitespace to
        keep the output predictable across prompt authors who may or
        may not include trailing newlines.

        Returns:
            (system_prompt, user_prompt) — pass directly to
            LLMProvider.call(system=..., user=..., ...).
        """
        user = f"{context.strip()}\n\n---\n\n{request.strip()}"
        return system.strip(), user

    # -------------------------------------------------------------------------
    # FENCE STRIPPING
    # -------------------------------------------------------------------------

    @staticmethod
    def strip_fences(content: str) -> str:
        """
        Strip surrounding ```<lang>...``` markdown fences if present.

        Handled cases:
```json
            {"foo":"bar"}
```
            -> {"foo":"bar"}
            {"foo":"bar"}

            -> {"foo":"bar"}

            {"foo":"bar"}      (no fences)
            -> {"foo":"bar"}   (returned unchanged after .strip())

        The regex only matches when the ENTIRE content is fence-
        wrapped. For responses where the LLM added commentary around
        an internal fence ("Here is the JSON: ```{...}```"), the
        content is returned as-is (only outer whitespace stripped)
        and the downstream parse will fail with a clear error.
        This is intentional — silent partial extraction would mask
        prompt-engineering issues.

        Returns:
            Inner content if fence-wrapped, otherwise the input
            stripped of outer whitespace.
        """
        if not content:
            return content
        match = _FENCE_RE.match(content)
        if match:
            return match.group(1).strip()
        return content.strip()

    # -------------------------------------------------------------------------
    # JSON PARSING
    # -------------------------------------------------------------------------

    @staticmethod
    def parse_json(content: str) -> Any:
        """
        Parse content as JSON.

        Returns whatever json.loads produces (dict, list, str, ...).
        The caller is expected to validate the structural shape
        against its expected schema.

        Raises:
            PromptParseError on:
              - empty / whitespace-only content
              - json.JSONDecodeError

            The error message includes the decoder message and the
            line / column position; it does NOT echo back the LLM
            response content — that decision belongs to the
            orchestrator (privacy + persistence of partial payloads).
        """
        if not content or not content.strip():
            raise PromptParseError('Empty content — cannot parse JSON.')

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise PromptParseError(
                f'JSON parse failed: {e.msg} at line {e.lineno} col {e.colno}.'
            ) from e

    # -------------------------------------------------------------------------
    # CONVENIENCE — strip + parse
    # -------------------------------------------------------------------------

    @staticmethod
    def parse_response(content: str) -> Any:
        """
        Convenience: strip_fences then parse_json.

        Used by pipelines on the raw `LLMCallResult.content` to obtain
        the structured response in one call. Equivalent to:

            PromptBuilder.parse_json(
                PromptBuilder.strip_fences(content)
            )

        Raises:
            PromptParseError on any parse failure (delegated from
            parse_json — strip_fences is non-raising).
        """
        stripped = PromptBuilder.strip_fences(content)
        return PromptBuilder.parse_json(stripped)