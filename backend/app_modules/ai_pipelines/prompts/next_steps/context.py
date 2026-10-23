# app_modules/ai_pipelines/prompts/next_steps/context.py
"""
Context layer for the next_steps prompt family (Sprint B4).

The NextStepsPipeline is single-stage and carries no canonical
taxonomy axes. Its context layer therefore reduces to the session
grounding block (tenant, prospect, activity) -- enough to
disambiguate "what conversation are we extracting suggestions from?"
without the taxonomy / techcatalog blocks that the qualification
pipeline emits.

Composition strategy
--------------------
We DELIBERATELY reuse the session-block helper from the existing
transcript_signals/context.py rather than copying the rendering code.

  * `_build_session_block(activity)` is the single source of truth for
    the "SESSION CONTEXT" block (tenant_name + account name/industry/
    segment + activity type/date). Any improvement
    to that block (e.g. richer disambiguation, RGPD field tightening)
    must propagate to every pipeline that uses it -- import-side reuse
    guarantees that.

  * We do NOT import _build_taxonomy_block:
    NextStepSignal has no canonical axes and is not tied to the
    TechCatalog. The next-step prompt is meant to elicit a STRUCTURED
    PAYLOAD (suggested_title / suggested_activity_type /
    suggested_due_date / source_quote), not a taxonomy-bound diagnosis.

Decision cycle block (v6, Sprint Next steps 3.2)
------------------------------------------------
After the session block, the decision cycle of the conversation, as concise
JSON (no taxonomy, still):

  * its steps by order -- `ref` (NEXT_STEPS_STEP_REF_FORMAT, "S4"), `name`,
    `status` DERIVED from the step's activities, `current` on the step the
    deal is at (decision_steps_state: the shared definitions of the step
    status and of DecisionStep.is_current);
  * its OPEN activities (NON_TERMINAL_STATUSES), in the
    ActivitySequenceService order, the conversation itself excepted --
    `title`, `type`, `date` (scheduled, else due), `step` (ref), `people`:
    the contacts by FIRST NAME only.

A conversation outside any decision cycle says so in one line. The block is
DATA: how the model uses it is the request layer's business.

Versioning
----------
`CONTEXT_VERSION` is captured in AIPipelineRun.prompt_versions
alongside SYSTEM_PROMPT_VERSION and NEXT_STEPS_PROMPT_VERSION. It is
INDEPENDENT from the transcript_signals/context.py CONTEXT_VERSION:
either layer can evolve without forcing the other to bump.

Underscore-import note
----------------------
`_build_session_block` is prefixed with an underscore in
transcript_signals/context.py, signalling "module-private" by Python
convention. Importing it across modules is intentional reuse with a
documented contract -- when we make a breaking change to the helper,
this importer is the explicit caller list to migrate. The alternative
(promoting the helper to a public `build_session_block`) is deferred:
making it public means committing to its signature stability across
versions, which we're not ready to do until a third caller arrives.
"""

import json

from ...constants import NEXT_STEPS_STEP_REF_FORMAT
from ..transcript_signals.context import _build_session_block


__all__ = ['CONTEXT_VERSION', 'build_context_layer']


# v2 (Sprint TechStack T4b): the reused session block now presents the date
# as the "Conversation date", reference of every relative date (null when the
# activity has no date) -- transcript_signals context v5.
# v3 (TD-279 B3): the reused session block lists the contacts as "registered
# on this activity", no longer "in this conversation".
# v4 (TD-279 B4b): the reused session block no longer lists the contacts.
# v5 (D7 / TD-281): the reused session block takes the Conversation date from
# the transcript's export header when there is one -- transcript_signals v10.
# v6 (Sprint Next steps 3.2): + the decision cycle block -- steps (ref, name,
# derived status, current) and open activities (title, type, date, step,
# first names).
CONTEXT_VERSION = 'v6'


def build_context_layer(activity, transcript=None):
    """
    Assemble the context block for the next-steps pipeline.

    Single-stage pipeline -> no `target_stage` argument. The block is
    the session grounding, then the decision cycle block (v6); the request
    layer (next_steps_v1.py) carries the entire schema + emission rules.

    Args:
        activity: app_modules.activities.models.Activity. Anchor for
            session grounding (tenant, account, activity) and for the
            decision cycle block (its cycle, steps, open activities).
        transcript: The analysed transcript (optional). Its export header,
            when there is one, gives the Conversation date (v5).

    Returns:
        str: A ready-to-concatenate context block. Will be combined
        with the request layer by PromptBuilder.assemble() to form the
        final user message.
    """
    return '\n\n'.join([
        _build_session_block(activity, transcript),
        _build_decision_cycle_block(activity),
    ])


def _compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def _step_ref(order):
    return NEXT_STEPS_STEP_REF_FORMAT.format(order=order)


def _build_decision_cycle_block(activity):
    """The decision cycle of the conversation (module docstring, v6)."""
    if activity.decision_cycle_id is None:
        return ('DECISION CYCLE\n'
                '- none: this conversation is not linked to a decision cycle')
    return '\n'.join([
        'DECISION CYCLE (the deal this conversation belongs to)',
        '- Steps, in order (ref = step reference; status derived from the step\'s '
        'activities; "current" = the step the deal is at):',
        _compact(_steps(activity.decision_cycle)),
        '- Open activities already in this cycle, the conversation itself excepted '
        '(people: first names only):',
        _compact(_open_activities(activity)),
    ])


def _steps(cycle):
    from app_modules.activities.services.next_step_materialization import (
        decision_steps_state,
    )
    return [
        {'ref': _step_ref(step.order), 'name': step.name, 'status': status,
         **({'current': True} if current else {})}
        for step, status, current in decision_steps_state(cycle)
    ]


def _open_activities(activity):
    from app_modules.activities.constants import NON_TERMINAL_STATUSES
    from app_modules.activities.models import Activity
    from app_modules.activities.services.activity_sequence_service import (
        ActivitySequenceService,
        SequenceScope,
    )
    sequence = [
        a for a in ActivitySequenceService.get_sequence_for_scope(
            SequenceScope.DECISION_CYCLE, activity.decision_cycle_id, activity.client_id,
        )
        if a['status'] in NON_TERMINAL_STATUSES and a['id'] != activity.id
    ]
    first_names = {}
    for activity_id, first_name in (
        Activity.contacts.through.objects
        .filter(activity_id__in=[a['id'] for a in sequence])
        .order_by('contact__first_name', 'contact__last_name')
        .values_list('activity_id', 'contact__first_name')
    ):
        first_names.setdefault(activity_id, []).append(first_name)
    return [
        {'title': a['title'], 'type': a['activity_type'], 'date': _iso(a),
         'step': _step_ref(a['decision_step_order']) if a['decision_step_id'] else None,
         'people': first_names.get(a['id'], [])}
        for a in sequence
    ]


def _iso(sequence_entry):
    """The activity's date: scheduled, else due (ISO), else None."""
    date = sequence_entry['scheduled_date'] or sequence_entry['due_date']
    return date.isoformat() if date else None
