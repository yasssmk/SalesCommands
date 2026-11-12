# app_modules/ai_pipelines/services/analysis_state.py
"""
THE « already analysed » definition of an activity (sprint « Cycle de vie
des contacts », 8g-7, TD-25). An analysis SUCCEEDED when a run of the
activity ended SUCCESS or PARTIAL — the runs the last-run endpoint returns
(views/last_run_view.py), read by the wizard (RunAIWizard: runsByPipeline)
and by the Source band (ActivityNotesTab: lastRun) to lock the transcript.

Read by:
  * LastRunView — its base queryset;
  * ActivityExtractionView — ONE analysis per pipeline (« Source / Notes »
    1.6, PO Q4): an analysed pipeline is never re-run, whatever the
    transcript posted (analysed_run_of);
  * ActivityUpdateSerializer — the transcript can no longer be changed once
    the activity is analysed (no re-run: the transcript stays the analysed
    one). A failed analysis (PARSE_ERROR / LLM_ERROR / TIMEOUT) leaves it
    editable.
"""

from ..constants import AIPipelineStatus

ANALYSED_RUN_STATUSES = (AIPipelineStatus.SUCCESS, AIPipelineStatus.PARTIAL)


def analysed_runs(activity, client_id):
    """The successful runs of `activity` — the « analysed » evidence."""
    from ..models import AIPipelineRun
    return AIPipelineRun.objects.filter(
        client_id=client_id, source_activity=activity, status__in=ANALYSED_RUN_STATUSES,
    )


def analysed_run_of(activity, client_id, pipeline_type):
    """The latest successful run of `pipeline_type` on `activity`, or None —
    a pipeline with one is ANALYSED and never re-run."""
    return (
        analysed_runs(activity, client_id)
        .filter(pipeline_type=pipeline_type)
        .order_by('-created_at')
        .first()
    )


def is_activity_analysed(activity):
    return analysed_runs(activity, activity.client_id).exists()
