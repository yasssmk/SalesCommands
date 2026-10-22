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
CONTEXT_VERSION = 'v5'


def build_context_layer(activity, transcript=None):
    """
    Assemble the context block for the next-steps pipeline.

    Single-stage pipeline -> no `target_stage` argument. The block is
    the session grounding only; the request layer (next_steps_v1.py)
    carries the entire schema + emission rules.

    Args:
        activity: app_modules.activities.models.Activity. Anchor for
            session grounding (tenant, account, activity).
        transcript: The analysed transcript (optional). Its export header,
            when there is one, gives the Conversation date (v5).

    Returns:
        str: A ready-to-concatenate context block. Will be combined
        with the request layer by PromptBuilder.assemble() to form the
        final user message.
    """
    return _build_session_block(activity, transcript)
