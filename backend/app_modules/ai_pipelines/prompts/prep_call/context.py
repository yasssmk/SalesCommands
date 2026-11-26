# app_modules/ai_pipelines/prompts/prep_call/context.py
"""
Context layer for the prep-call tactical brief pipeline.

Renders the dynamic context block: input pack summary, brief mode,
dominant rhetoric register, applicable maturity modulations, and
mixing rules.
"""

import json

from .guide_v1 import (  # frozen v1 guide (G10)
    BRIEF_MODES,
    MODE_TO_DOMINANT_REGISTER,
    RHETORIC_REGISTERS,
    MATURITY_MODULATIONS,
    MIXING_RULES,
)


__all__ = ['CONTEXT_VERSION', 'build_context_layer']

CONTEXT_VERSION = 'v1'


def build_context_layer(input_pack, brief_mode):
    """
    Assemble the context block from the input pack and brief mode.

    Args:
        input_pack: dict returned by PrepInputPackAssembler.build().
        brief_mode: str — one of DISCOVERY, CONVICTION, PROOF, DECISION.

    Returns:
        str: ready-to-concatenate context block.
    """
    sections = []

    # -- Brief mode --
    mode_info = BRIEF_MODES.get(brief_mode, {})
    sections.append(
        f"BRIEF MODE: {brief_mode}\n"
        f"Description: {mode_info.get('description', '')}\n"
        f"Priority: {mode_info.get('priority', '')}"
    )

    # -- Dominant register --
    register_key = MODE_TO_DOMINANT_REGISTER.get(brief_mode, '')
    register = RHETORIC_REGISTERS.get(register_key, {})
    if register:
        sections.append(
            f"DOMINANT REGISTER\n"
            f"Purpose: {register.get('purpose', '')}\n"
            f"Procedures: {register.get('procedures', '')}\n"
            f"When to use: {register.get('when_to_use', '')}\n"
            f"Avoid if: {register.get('avoid_if', '')}"
        )

    # -- Maturity modulations --
    modulations = _applicable_modulations(input_pack)
    if modulations:
        mod_lines = ["MATURITY MODULATIONS (apply these adjustments):"]
        for mod in modulations:
            mod_lines.append(f"  - {mod['instruction']}")
        sections.append('\n'.join(mod_lines))

    # -- Mixing rules --
    sections.append(f"MIXING RULES: {MIXING_RULES}")

    # -- Prep context --
    ctx = input_pack.get('prep_context', {})
    ctx_lines = ["PREP CONTEXT"]
    if ctx.get('account_name'):
        ctx_lines.append(f"Account: {ctx['account_name']}")
    # The decision cycle's UUID is NOT sent to the LLM (amendment A15): it
    # carries no meaning for the model. The account name stays.
    if ctx.get('deal_value'):
        ctx_lines.append(f"Deal value: {ctx['deal_value']}")

    activity = ctx.get('upcoming_activity', {})
    if activity:
        ctx_lines.append(
            f"Upcoming activity: {activity.get('type', 'unknown')} "
            f"on {activity.get('date', 'unscheduled')}"
        )
        contact = activity.get('primary_contact')
        if contact:
            ctx_lines.append(
                f"Primary contact: role={contact.get('role', 'unknown')}, "
                f"department={contact.get('department', 'unknown')}"
            )

    step_exp = ctx.get('step_expectations', {})
    if step_exp.get('goal'):
        ctx_lines.append(f"Step goal: {step_exp['goal']}")
    if step_exp.get('criterias'):
        ctx_lines.append(
            f"Step criterias: {', '.join(str(c) for c in step_exp['criterias'])}"
        )

    if ctx.get('current_step'):
        ctx_lines.append(f"Current step: {ctx['current_step']}")
    if ctx.get('last_deal_health_snapshot_date'):
        ctx_lines.append(
            f"Last deal health snapshot: {ctx['last_deal_health_snapshot_date']}"
        )

    sections.append('\n'.join(ctx_lines))

    # -- Maturity snapshot --
    maturity = input_pack.get('maturity_snapshot')
    if maturity:
        mat_lines = ["MATURITY SNAPSHOT"]
        if maturity.get('global_reading'):
            mat_lines.append(f"Global reading: {maturity['global_reading']}")
        for dim in maturity.get('dimensions', []):
            mat_lines.append(f"  {dim['key']}: {dim['status']}")
        sections.append('\n'.join(mat_lines))
    else:
        sections.append(
            "MATURITY SNAPSHOT: No deal health snapshot available. "
            "Treat all dimensions as missing_evidence."
        )

    # -- Stakeholder focus --
    stakeholder = input_pack.get('stakeholder_focus')
    if stakeholder:
        sh_lines = [
            f"STAKEHOLDER FOCUS",
            f"Role: {stakeholder.get('role', 'unknown')}",
            f"Department: {stakeholder.get('department', 'unknown')}",
        ]
        if stakeholder.get('their_pains'):
            sh_lines.append(
                f"Their pains: {json.dumps(stakeholder['their_pains'], ensure_ascii=False)}"
            )
        if stakeholder.get('their_desires'):
            sh_lines.append(
                f"Their desires: {json.dumps(stakeholder['their_desires'], ensure_ascii=False)}"
            )
        if stakeholder.get('their_resistances'):
            sh_lines.append(
                f"Resistances: {json.dumps(stakeholder['their_resistances'], ensure_ascii=False)}"
            )
        if stakeholder.get('human_impact'):
            sh_lines.append(
                f"Human impact: {json.dumps(stakeholder['human_impact'], ensure_ascii=False)}"
            )
        sections.append('\n'.join(sh_lines))

    # -- Participants (G4: every one, by label — first names only) --
    participants = input_pack.get('participants') or []
    if participants:
        part_lines = ["PARTICIPANTS (one angle per person)"]
        for person in participants:
            part_lines.append(f"  {_participant_text(person)}")
        sections.append('\n'.join(part_lines))

    # -- Campaign (G8: an activity of a campaign outside a cycle) --
    campaign = input_pack.get('campaign')
    if campaign:
        sections.append(_campaign_text(campaign))

    # -- Previous conversations (G7 / G8: same cycle or same sequence) --
    previous = input_pack.get('previous_activities') or []
    if previous:
        prev_lines = ["PREVIOUS CONVERSATIONS (oldest first)"]
        for row in previous:
            prev_lines.append(f"  {_previous_text(row)}")
        sections.append('\n'.join(prev_lines))

    # -- Levers --
    levers = input_pack.get('levers', {})
    if any(levers.get(k) for k in ('desires', 'value', 'cost_frictions', 'constraints')):
        lever_lines = ["LEVERS"]
        for key in ('desires', 'value', 'cost_frictions', 'constraints'):
            items = levers.get(key, [])
            if items:
                lever_lines.append(f"  {key}: {json.dumps(items, ensure_ascii=False)}")
        sections.append('\n'.join(lever_lines))

    # -- Competitive context --
    comp = input_pack.get('competitive_context', {})
    incumbents = comp.get('incumbents', [])
    competing = comp.get('competing_on_deal', [])
    if incumbents or competing:
        comp_lines = ["COMPETITIVE CONTEXT"]
        for inc in incumbents:
            comp_lines.append(f"  Incumbent: {_incumbent_text(inc)}")
        for c in competing:
            comp_lines.append(f"  Competitor on deal: {c.get('tool', 'unknown')}")
        sections.append('\n'.join(comp_lines))

    # -- Evidence scope --
    scope = input_pack.get('evidence_scope', {})
    sections.append(
        f"EVIDENCE SCOPE\n"
        f"Validated signals: {scope.get('validated_signals_count', 0)}\n"
        f"Transcripts analyzed: {scope.get('transcripts_count', 0)}\n"
        f"Note: {scope.get('coverage_note', 'Based on captured evidence.')}"
    )

    return '\n\n'.join(sections)


def _campaign_text(campaign):
    """The campaign block of the pack, as given (G8)."""
    lines = [f"CAMPAIGN: {campaign.get('name') or 'unknown'} ({campaign.get('type') or 'unknown'})"]
    if campaign.get('objective'):
        lines.append(f"Campaign objective: {campaign['objective']}")
    if campaign.get('contact_objective'):
        lines.append(f"Objective for this contact: {campaign['contact_objective']}")
    sequence = campaign.get('sequence') or {}
    if sequence.get('position') and sequence.get('total'):
        lines.append(f"Sequence: step {sequence['position']} of {sequence['total']}")
    for step in sequence.get('next_steps') or []:
        lines.append(f"  Next step: {step.get('type')} on {step.get('scheduled_date') or 'unscheduled'}")
    return '\n'.join(lines)


def _previous_text(row):
    """One previous conversation of the pack, as given (G7 / G8)."""
    text = f"{row.get('date')} {row.get('type')}"
    if row.get('outcome'):
        text += f" — {row['outcome']}"
    if row.get('notes'):
        text += f" — notes: {row['notes']}"
    return text


def _participant_text(person):
    """One participant of the pack, as given (G4): label, role, department,
    the profile values — never an id, a last name or a contact detail."""
    text = person.get('label') or 'unknown'
    details = []
    if person.get('role'):
        details.append(f"role: {person['role']}")
    if person.get('department'):
        details.append(f"department: {person['department']}")
    for field, value in (person.get('profile') or {}).items():
        if value not in (None, '', []):
            details.append(f"{field}: {value}")
    return f"{text} — {'; '.join(details)}" if details else text


def _incumbent_text(inc):
    """One tool of the pack, as given (TD-314, S6): name, usage (scope and
    using departments), discontinuation and its date — nothing derived here."""
    text = inc.get('tool', 'unknown')
    usage = inc.get('usage_scope')
    departments = inc.get('usage_departments') or []
    if usage or departments:
        text += f" — usage: {usage or 'unknown'}"
        if departments:
            text += f" ({', '.join(departments)})"
    if inc.get('discontinued'):
        text += f" — {inc['discontinued']}"
        if inc.get('discontinued_date'):
            text += f" ({inc['discontinued_date']})"
    return text


def _applicable_modulations(input_pack):
    """Return maturity modulations that apply to the current snapshot."""
    maturity = input_pack.get('maturity_snapshot')
    if not maturity:
        return []

    dims = {}
    for d in maturity.get('dimensions', []):
        dims[d.get('key')] = d.get('status')

    applicable = []
    for _key, mod in MATURITY_MODULATIONS.items():
        dimension = mod.get('dimension')
        if dimension is None:
            applicable.append(mod)
            continue
        status = dims.get(dimension)
        if status and status in mod.get('statuses', ()):
            applicable.append(mod)

    return applicable
