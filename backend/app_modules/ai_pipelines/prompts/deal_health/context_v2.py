# app_modules/ai_pipelines/prompts/deal_health/context_v2.py
"""
Context layer v2 of the deal-health diagnostic — sprint « Deal health v2 »,
step 5.

ONE function decides what is sent (llm_view): the deal's static context,
the declared step, the stakeholders (by their llm_people label, with their
current profile), the previous diagnostic and the NEW evidence (signals,
activities, manager notes — step 3b). No database id is ever sent.

Two renderings of the same view, chosen by constants.DEAL_HEALTH_INPUT_FORMAT
and compared at step 7:
  * 'sections' — labelled sections, each a compact JSON (the next_steps
    context pattern, prompts/next_steps/context.py _compact);
  * 'json'     — the whole view as ONE JSON document.
"""

import json

from app_modules.ai_pipelines.constants import (
    DEAL_HEALTH_INPUT_FORMAT,
    DEAL_HEALTH_INPUT_FORMAT_JSON,
)


__all__ = ['CONTEXT_VERSION', 'build_context_layer', 'llm_view']

CONTEXT_VERSION = 'v2'


def _compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def _without(row, *keys):
    return {k: v for k, v in row.items() if k not in keys and not k.startswith('_')}


def llm_view(pack):
    """The deal-health input as sent to the LLM — ordered sections, no ids."""
    cycle = pack.get('cycle') or {}
    step = cycle.get('current_step')
    people = pack.get('people') or {}
    readiness = pack.get('readiness') or {}

    return {
        'deal': {
            'name': cycle.get('name'),
            'estimated_value': cycle.get('estimated_value'),
            'description': cycle.get('description') or '',
            'origin_campaign': cycle.get('source_campaign'),
        },
        'declared_step': (
            {
                'step': step.get('stage'),
                'name': step.get('name'),
                'goal': step.get('goal', ''),
                'criteria': step.get('criterias', []),
                'metrics': step.get('metrics', []),
            }
            if step else None
        ),
        'account': pack.get('account') or {},
        'products': cycle.get('products', []),
        'readiness': {
            'score': readiness.get('score', 0),
            'covered': [d['name'] for d in readiness.get('dimensions', []) if d.get('filled')],
            'missing': [d['name'] for d in readiness.get('dimensions', []) if not d.get('filled')],
        },
        'stakeholders': pack.get('stakeholders') or [],
        'unqualified_contacts': people.get('unqualified_count', 0),
        'previous_diagnostic': _previous(pack.get('previous_snapshot')),
        'new_evidence': {
            'signals': {
                kind: rows for kind, rows in (pack.get('signals') or {}).items() if rows
            },
            'activities': [
                _without(a, 'activity_id') for a in (pack.get('activities') or [])
            ],
            'manager_notes': pack.get('manager_notes') or [],
        },
    }


def _previous(prev):
    if not prev:
        return None
    return {
        'date': prev.get('snapshot_date', ''),
        # v2: the full previous diagnostic; v1: its global reading only.
        'diagnostic': prev.get('diagnostic') or {'global_reading': prev.get('global_reading', '')},
    }


_SECTION_TITLES = (
    ('deal', 'DEAL'),
    ('declared_step', 'DECLARED STEP (set by the rep)'),
    ('account', 'ACCOUNT'),
    ('products', 'PRODUCTS SOLD ON THIS DEAL (never claim more than this)'),
    ('readiness', 'READINESS'),
    ('stakeholders', 'STAKEHOLDERS (refer to them by "ref" only; "profile" = what is already known)'),
    ('unqualified_contacts', 'CONTACTS WITHOUT A ROLE'),
    ('previous_diagnostic', 'PREVIOUS DIAGNOSTIC'),
    ('new_evidence', 'NEW EVIDENCE SINCE THE PREVIOUS DIAGNOSTIC'),
)


def build_context_layer(pack, input_format=None):
    """
    Render the context block.

    Args:
        pack:         dict returned by DealHealthEvidenceBuilder.build().
        input_format: 'sections' | 'json' (default:
                      constants.DEAL_HEALTH_INPUT_FORMAT).
    """
    view = llm_view(pack)
    if (input_format or DEAL_HEALTH_INPUT_FORMAT) == DEAL_HEALTH_INPUT_FORMAT_JSON:
        return 'DEAL HEALTH INPUT (JSON)\n' + _compact(view)
    return '\n\n'.join(f"{title}\n{_compact(view[key])}" for key, title in _SECTION_TITLES)
