# app_modules/ai_pipelines/prompts/prep_call/__init__.py
"""
Prompt package of the Game Plan (prep call).

v2 (sprint 2 Game Plan, G10) — what the pipeline sends:
  * system_v2_1 (G13d; v2 kept in system_v2) — the account executive's
    posture, the hard rules (v2.1: no invented slot, no claimed action), the
    deal health v2's output-language rule;
  * context_v2 — the input pack v2, section by section;
  * outline_v2 — the task, the field rules, the strict schema
    PREP_CALL_OUTLINE_SCHEMA;
  * message_v2 (G11) — the AI message: one per recipient, in its language,
    the strict schema PREP_CALL_MESSAGE_SCHEMA (with MESSAGE_SYSTEM_PROMPT).

v1 (system.py, context.py, brief_v1.py, guide_v1.py) is kept, frozen: it
documents what produced the v1 snapshots (schema_version 1), which stay
readable. The pipeline no longer imports it.

Versioning: each layer carries its own version constant, captured in
AIPipelineRun.prompt_versions.
"""

# G13f: the system v2.2 and the outline v2.1 (v2 / v2.1 kept, unchanged).
from .system_v2_2 import MESSAGE_SYSTEM_PROMPT, SYSTEM_PROMPT, SYSTEM_PROMPT_VERSION
from .message_v2 import (
    MESSAGE_PROMPT_VERSION,
    PREP_CALL_MESSAGE_SCHEMA,
    build_message_request,
)
from .context_v2 import build_context_layer, CONTEXT_VERSION
from .outline_v2_1 import (
    OUTLINE_PROMPT_VERSION,
    PREP_CALL_OUTLINE_SCHEMA,
    build_outline_request,
)


__all__ = [
    'SYSTEM_PROMPT',
    'SYSTEM_PROMPT_VERSION',
    'build_context_layer',
    'CONTEXT_VERSION',
    'build_outline_request',
    'OUTLINE_PROMPT_VERSION',
    'PREP_CALL_OUTLINE_SCHEMA',
    'MESSAGE_SYSTEM_PROMPT',
    'build_message_request',
    'MESSAGE_PROMPT_VERSION',
    'PREP_CALL_MESSAGE_SCHEMA',
]
