# app_modules/ai_pipelines/prompts/prep_call/context.py
"""
Context layer for the prep-call tactical brief pipeline.

Renders the dynamic context block: input pack summary, brief mode,
dominant rhetoric register, applicable maturity modulations, and
mixing rules.
"""

import json

from app_modules.ai_pipelines.services.prep_call.rhetoric_guide import (
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
    if ctx.get('decision_cycle_id'):
        ctx_lines.append(f"Decision cycle: {ctx['decision_cycle_id']}")
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
            comp_lines.append(f"  Incumbent: {inc.get('tool', 'unknown')}")
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
