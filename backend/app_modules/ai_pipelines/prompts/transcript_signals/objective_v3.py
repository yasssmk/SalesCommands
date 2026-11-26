# app_modules/ai_pipelines/prompts/transcript_signals/objective_v3.py
"""
Request layer for Objective signal extraction — v3 (sprint 2 Game Plan, G5 —
TD-219).

v3 = v2 (objective_v1.py, kept unchanged) + two fields the extraction now
emits, so the objective's « How is success measured? » section is filled from
what was SAID:

    success_criteria  string  -- what the prospect said would show the
                                 objective is met, verbatim or near-verbatim;
                                 "" when nothing is said
    notes             string  -- the context STATED around the objective
                                 (who carries it, why, what it depends on);
                                 "" when nothing is said

Never invented: no figure, threshold or context that the transcript does not
state. The v3 text is BUILT from the v2 one (the next_steps_v3 pattern): the
two fields inserted right after `target_date` in the OUTPUT SCHEMA, their rules
inserted before the EMISSION RULES; everything else is v2's, unchanged.

The stage also sends a strict response schema (OBJECTIVE_RESPONSE_SCHEMA,
Structured Outputs — the people stage's pattern): every key required, the two
new ones string or null. The server keeps validating the values
(services/transcript_signal_extractor.py _build_objective_data): an absent or
invalid success_criteria / notes is "", and the signal is KEPT.
"""

from . import objective_v1 as _v1


__all__ = [
    'OBJECTIVE_PROMPT_VERSION',
    'OBJECTIVE_RESPONSE_SCHEMA',
    'build_objective_request',
]


OBJECTIVE_PROMPT_VERSION = 'v3'


# The v2 OUTPUT SCHEMA line the two fields follow.
_SCHEMA_ANCHOR = (
    '      "target_date": "<YYYY-MM-DD deadline of the objective, or null when no '
    'deadline is said -- see TARGET DATE>",\n'
)
_SCHEMA_FIELDS = (
    '      "success_criteria": "<what the prospect SAID would show the objective is met, '
    'verbatim or near-verbatim, or \\"\\" -- see SUCCESS CRITERIA AND NOTES>",\n'
    '      "notes": "<the context STATED around the objective, or \\"\\" -- see SUCCESS '
    'CRITERIA AND NOTES>",\n'
)

# The v2 section the new rules come before.
_RULES_ANCHOR = 'EMISSION RULES\n'
_RULES = """SUCCESS CRITERIA AND NOTES
- "success_criteria" -- how the PROSPECT said they will know the objective is
  met: a measure, a threshold, an observable outcome, kept verbatim or
  near-verbatim, in the transcript's language. "" when the transcript does not
  say it. Never invent a figure, a threshold or a measure; never turn the
  objective itself into its own criterion.
  « Pour nous, c'est réussi si la clôture est signée au jour 3. »
      -> "success_criteria": "la clôture est signée au jour 3"
  "We want to grow faster." (no measure said)
      -> "success_criteria": ""
- "notes" -- the context STATED around the objective only: who carries it,
  why it matters to them, what it depends on, what was said about it. One or
  two short sentences, in the transcript's language. "" when nothing beyond
  the objective is said. Never add your own analysis, advice or guess.
  "The board reviews the close time in June."
      -> "notes": "The board reviews the close time in June."

"""


def _insert_after(text, anchor, addition):
    if text.count(anchor) != 1:
        raise ImportError(f'objective_v3: the v2 anchor {anchor[:40]!r} is not found once.')
    return text.replace(anchor, anchor + addition)


def _insert_before(text, anchor, addition):
    if text.count(anchor) != 1:
        raise ImportError(f'objective_v3: the v2 anchor {anchor[:40]!r} is not found once.')
    return text.replace(anchor, addition + anchor)


def build_objective_request(transcript):
    """The v3 request layer: the v2 one, with the two fields and their rules
    (see the module docstring)."""
    text = _v1.build_objective_request(transcript)
    text = _insert_after(text, _SCHEMA_ANCHOR, _SCHEMA_FIELDS)
    return _insert_before(text, _RULES_ANCHOR, _RULES)


# Built once at import: a v2 text that lost an anchor fails at startup.
build_objective_request('')


def _nullable_string():
    return {'type': ['string', 'null']}


# The strict response schema of the objective stage (Structured Outputs, the
# PEOPLE_RESPONSE_SCHEMA pattern): every key of the OUTPUT SCHEMA required —
# strict mode — the optional values as string-or-null. The vocabularies (what,
# dimension, scope_level, target_department) stay validated by the server
# (_build_objective_data), as before.
OBJECTIVE_RESPONSE_SCHEMA = {
    'name': 'objective_signals',
    'schema': {
        'type': 'object',
        'additionalProperties': False,
        'required': ['signals'],
        'properties': {
            'signals': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'additionalProperties': False,
                    'required': [
                        'what', 'dimension', 'scope_level', 'target_department',
                        'summary', 'source_quote', 'target_date',
                        'success_criteria', 'notes', 'confidence', 'is_inferred',
                    ],
                    'properties': {
                        'what':              {'type': 'string'},
                        'dimension':         {'type': 'string'},
                        'scope_level':       {'type': 'string'},
                        'target_department': _nullable_string(),
                        'summary':           {'type': 'string'},
                        'source_quote':      {'type': 'string'},
                        'target_date':       _nullable_string(),
                        'success_criteria':  _nullable_string(),
                        'notes':             _nullable_string(),
                        'confidence':        {'type': 'number'},
                        'is_inferred':       {'type': 'boolean'},
                    },
                },
            },
        },
    },
}
