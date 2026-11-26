# app_modules/ai_pipelines/prompts/prep_call/context_v2.py
"""
Context layer v2 of the Game Plan (prep call) — sprint 2 Game Plan, G10.

The input pack v2 (G7 / G8) as the LLM reads it: labelled sections, each
given as it is in the pack — no brief mode (removed), no rhetoric register,
no database id (deal / snapshot / participant ids and the seller profile's
update date stay server side).

Reused, not redefined: the v1 renderers of the participants, the tools, the
campaign and the previous conversations (prompts/prep_call/context.py), and
the deal health v2's compact JSON (prompts/deal_health/context_v2.py).
"""

from ..deal_health.context_v2 import _compact, _without
from .context import _campaign_text, _incumbent_text, _participant_text, _previous_text


__all__ = ['CONTEXT_VERSION', 'build_context_layer']

CONTEXT_VERSION = 'v2'


def _section(title, value):
    return f"{title}\n{_compact(value)}"


def build_context_layer(input_pack):
    """
    Assemble the context block of the Game Plan v2.

    Args:
        input_pack: dict returned by PrepInputPackAssembler.build().

    Returns:
        str
    """
    sections = []

    activity = input_pack.get('activity') or {}
    sections.append(_section('THE CONVERSATION TO PREPARE', _without(activity)))

    ctx = input_pack.get('prep_context') or {}
    if ctx.get('account_name'):
        sections.append(f"ACCOUNT: {ctx['account_name']}")
    if input_pack.get('account'):
        sections.append(_section('ACCOUNT CONTEXT', input_pack['account']))

    deal = input_pack.get('deal')
    if deal:
        sections.append(_section('THE DEAL', _without(deal, 'id')))
    if ctx.get('current_step'):
        sections.append(f"Current step: {ctx['current_step']}")

    # The latest deal-health snapshot, read ONCE by the pack: its v1 view
    # (maturity_snapshot — global reading, the 7 dimensions: every snapshot
    # has it) and its v2 keys (None on a v1 snapshot: left out).
    deal_health = input_pack.get('deal_health')
    if deal_health:
        lines = ['LATEST DEAL HEALTH DIAGNOSTIC']
        if deal_health.get('snapshot_date'):
            lines.append(f"Last deal health snapshot: {deal_health['snapshot_date']}")
        maturity = input_pack.get('maturity_snapshot') or {}
        if maturity.get('global_reading'):
            lines.append(f"Global reading: {maturity['global_reading']}")
        lines += [f"  {d.get('key')}: {d.get('status')}" for d in maturity.get('dimensions') or []]
        v2 = {k: v for k, v in _without(deal_health, 'snapshot_id', 'schema_version', 'snapshot_date').items()
              if v not in (None, '', [], {})}
        if v2:
            lines.append(_compact(v2))
        sections.append('\n'.join(lines))
    else:
        sections.append('LATEST DEAL HEALTH DIAGNOSTIC: No deal health snapshot available.')

    participants = input_pack.get('participants') or []
    if participants:
        sections.append('\n'.join(
            ['PARTICIPANTS (ref = the label, exactly as written here)']
            + [f"  {_participant_text(p)}" for p in participants]
        ))
    else:
        sections.append('PARTICIPANTS: none registered on the activity.')

    if input_pack.get('objectives'):
        sections.append(_section('VALIDATED OBJECTIVES', input_pack['objectives']))

    levers = input_pack.get('levers') or {}
    if any(levers.get(k) for k in ('desires', 'value', 'cost_frictions', 'constraints')):
        sections.append(_section('LEVERS', levers))

    comp = input_pack.get('competitive_context') or {}
    comp_lines = (
        [f"  Incumbent: {_incumbent_text(inc)}" for inc in comp.get('incumbents') or []]
        + [f"  Competitor on deal: {c.get('tool', 'unknown')}" for c in comp.get('competing_on_deal') or []]
    )
    if comp_lines:
        sections.append('\n'.join(['COMPETITIVE CONTEXT'] + comp_lines))

    if input_pack.get('manager_notes'):
        sections.append(_section('MANAGER NOTES', input_pack['manager_notes']))

    seller = input_pack.get('seller_profile')
    if seller:
        sections.append(_section('THE SELLER (our company)', _without(seller, 'updated_at')))
    else:
        sections.append('THE SELLER (our company): no seller profile yet — no reference, '
                        'certification or positioning is available.')

    campaign = input_pack.get('campaign')
    if campaign:
        sections.append(_campaign_text(campaign))

    previous = input_pack.get('previous_activities') or []
    if previous:
        sections.append('\n'.join(
            ['PREVIOUS CONVERSATIONS (oldest first)'] + [f"  {_previous_text(r)}" for r in previous]
        ))

    return '\n\n'.join(sections)

