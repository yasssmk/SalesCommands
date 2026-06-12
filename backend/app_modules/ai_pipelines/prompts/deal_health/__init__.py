# app_modules/ai_pipelines/prompts/deal_health/__init__.py
"""
Prompt package for the deal-health diagnostic pipeline.

Three layers assembled by PromptBuilder.assemble():
  * system  — analyst role, QA rules, output constraints.
  * context — cycle grounding (deal, step, products, readiness, people).
  * request — validated signals as evidence + output JSON schema.

Versioning: each layer carries an independent version constant captured
in AIPipelineRun.prompt_versions for audit traceability.
"""

from .system import SYSTEM_PROMPT, SYSTEM_PROMPT_VERSION
from .context import build_context_layer, CONTEXT_VERSION
from .diagnostic_v1 import build_diagnostic_request, DIAGNOSTIC_PROMPT_VERSION


__all__ = [
    'SYSTEM_PROMPT',
    'SYSTEM_PROMPT_VERSION',
    'build_context_layer',
    'CONTEXT_VERSION',
    'build_diagnostic_request',
    'DIAGNOSTIC_PROMPT_VERSION',
]
