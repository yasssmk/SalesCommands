# app_modules/ai_pipelines/prompts/deal_health/__init__.py
"""
Prompt package for the deal-health diagnostic pipeline.

Three layers assembled by PromptBuilder.assemble():
  * system  — analyst role, QA rules, output constraints.
  * context — cycle grounding (deal, step, products, readiness, people).
  * request — validated signals as evidence + output JSON schema.

Versioning: each layer carries an independent version constant captured
in AIPipelineRun.prompt_versions for audit traceability.

v2 (sprint « Deal health v2 », step 5): system_v2 / context_v2 /
diagnostic_v2 — the « manager / coach » diagnostic with a strict Structured
Outputs schema; the v1 modules are kept unchanged (exported as before).
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
