# app_modules/ai_pipelines/prompts/prep_call/__init__.py
"""
Prompt package for the prep-call tactical brief pipeline.

Three layers assembled by PromptBuilder.assemble():
  * system  — coach role, guardrails (§5.4), output constraints.
  * context — input pack + rhetoric guide + brief mode.
  * request — brief generation task + output JSON schema.

Versioning: each layer carries an independent version constant captured
in AIPipelineRun.prompt_versions for audit traceability.
"""

from .system import SYSTEM_PROMPT, SYSTEM_PROMPT_VERSION
from .context import build_context_layer, CONTEXT_VERSION
from .brief_v1 import build_brief_request, BRIEF_PROMPT_VERSION


__all__ = [
    'SYSTEM_PROMPT',
    'SYSTEM_PROMPT_VERSION',
    'build_context_layer',
    'CONTEXT_VERSION',
    'build_brief_request',
    'BRIEF_PROMPT_VERSION',
]
