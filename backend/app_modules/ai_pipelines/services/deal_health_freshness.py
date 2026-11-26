# app_modules/ai_pipelines/services/deal_health_freshness.py
"""
The freshness of a cycle's deal health — sprint « Deal health v2 », step 8
(PO decision n° 7, amendment A13). Computed AT READ TIME, never stored.
THE service the Strategic tab reads (beside the latest snapshot — views/
deal_health_snapshot_views.py latest) and the Game Plan will reuse
(sprint 2).

    deal_health_freshness(cycle) -> {
        'applies':          bool,
        'has_new_info':     bool,
        'last_analysis_at': ISO datetime of the last snapshot | None,
        'reasons':          [DEAL_HEALTH_FRESHNESS_*],
    }

  applies      — false for a closed cycle (DEAL_HEALTH_CLOSED_OUTCOMES) or a
                 current declared step before DEAL_HEALTH_MIN_STEP (order of
                 PIPELINE_STEPS_ORDER), or no declared step at all;
  has_new_info — « new information to analyse », never « stale »:
                 the reasons of THE predicate the run guard reads too,
                 DealHealthEvidenceBuilder.new_info_reasons (sprint 2 Game
                 Plan, S7) — NO_ANALYSIS_YET, NEW_SOURCES (an analysed
                 activity, a validated signal, a manager note, the static
                 context; never a typed note nor a mere activity edit),
                 STEP_CHANGED, STAKEHOLDERS_CHANGED. A reason is present <=>
                 a re-run is accepted.

Cost: existence queries only (no pack, no transcript read) — a constant
number of queries whatever the number of sources.
"""

from app_modules.activities.services.next_step_materialization import current_decision_step
from app_modules.decision_cycles.constants import (
    DEAL_HEALTH_CLOSED_OUTCOMES,
    DEAL_HEALTH_MIN_STEP,
    PIPELINE_STEPS_ORDER,
)

from .deal_health_evidence_builder import DealHealthEvidenceBuilder


def _step_applies(stage):
    """The declared step is DEAL_HEALTH_MIN_STEP or after it."""
    if stage not in PIPELINE_STEPS_ORDER:
        return False
    return PIPELINE_STEPS_ORDER.index(stage) >= PIPELINE_STEPS_ORDER.index(DEAL_HEALTH_MIN_STEP)


def deal_health_freshness(cycle):
    """See the module docstring."""
    builder = DealHealthEvidenceBuilder()
    last = builder.latest_snapshot(cycle)
    last_at = last.snapshot_date.isoformat() if last is not None and last.snapshot_date else None

    current = current_decision_step(cycle)
    stage = current.stage if current is not None else None
    applies = cycle.outcome not in DEAL_HEALTH_CLOSED_OUTCOMES and _step_applies(stage)
    if not applies:
        return {'applies': False, 'has_new_info': False,
                'last_analysis_at': last_at, 'reasons': []}

    # THE predicate, shared with the run guard (S7).
    reasons = builder.new_info_reasons(cycle, last, stage)
    return {'applies': True, 'has_new_info': bool(reasons),
            'last_analysis_at': last_at, 'reasons': reasons}
