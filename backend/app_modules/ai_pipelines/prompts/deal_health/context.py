# app_modules/ai_pipelines/prompts/deal_health/context.py
"""
Context layer for the deal-health diagnostic pipeline.

Renders the cycle grounding block: deal identity, current step with
expectations, products, readiness summary, people roster, and the
previous snapshot reading (if any).

This does NOT reuse _build_session_block from transcript_signals —
there is no Activity; the context is cycle-level.
"""

__all__ = ['CONTEXT_VERSION', 'build_context_layer']

CONTEXT_VERSION = 'v1'


def build_context_layer(pack):
    """
    Assemble the context block from an evidence pack dict.

    Args:
        pack: dict returned by DealHealthEvidenceBuilder.build().

    Returns:
        str: ready-to-concatenate context block.
    """
    sections = []

    # -- Deal identity --
    cycle = pack['cycle']
    sections.append(
        f"DEAL CONTEXT\n"
        f"Deal name: {cycle['name']}\n"
        f"Estimated value: {cycle['estimated_value']}"
    )

    # -- Current step --
    step = cycle.get('current_step')
    if step:
        step_lines = [f"Current step: {step['name']}"]
        if step.get('goal'):
            step_lines.append(f"  Goal: {step['goal']}")
        if step.get('criterias'):
            step_lines.append(
                f"  Criterias: {', '.join(str(c) for c in step['criterias'])}"
            )
        if step.get('metrics'):
            step_lines.append(
                f"  Metrics: {', '.join(str(m) for m in step['metrics'])}"
            )
        sections.append('\n'.join(step_lines))
    else:
        sections.append("Current step: none identified")

    # -- Products --
    products = cycle.get('products', [])
    if products:
        product_lines = ["Products:"]
        for p in products:
            product_lines.append(f"  - {p['name']} (qty: {p['quantity']})")
        sections.append('\n'.join(product_lines))

    # -- Readiness --
    readiness = pack.get('readiness', {})
    score = readiness.get('score', 0)
    dims = readiness.get('dimensions', [])
    filled_names = [d['name'] for d in dims if d.get('filled')]
    missing_names = [d['name'] for d in dims if not d.get('filled')]
    readiness_lines = [f"Readiness score: {score}/100"]
    if filled_names:
        readiness_lines.append(f"  Covered: {', '.join(filled_names)}")
    if missing_names:
        readiness_lines.append(f"  Missing: {', '.join(missing_names)}")
    sections.append('\n'.join(readiness_lines))

    # -- People --
    people = pack.get('people', {})
    qualified = people.get('qualified', [])
    unqualified_count = people.get('unqualified_count', 0)
    if qualified:
        people_lines = ["Stakeholders (qualified):"]
        for q in qualified:
            dept = ''
            if q.get('target_department'):
                dept = f" [{q['target_department']['name']}]"
            contact_name = ''
            if q.get('target_contact'):
                c = q['target_contact']
                contact_name = f" {c.get('first_name', '')} {c.get('last_name', '')}".strip()
            people_lines.append(
                f"  - {q['role_display']}{dept}{' — ' + contact_name if contact_name else ''}"
                f" (influence: {q.get('influence_display') or 'unknown'})"
            )
        sections.append('\n'.join(people_lines))
    if unqualified_count:
        sections.append(
            f"Unqualified contacts (no role assigned): {unqualified_count}"
        )

    # -- Previous snapshot --
    prev = pack.get('previous_snapshot')
    if prev:
        sections.append(
            f"Previous diagnostic ({prev['snapshot_date']}):\n"
            f"  {prev['global_reading']}"
        )

    return '\n\n'.join(sections)
