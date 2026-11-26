# app_modules/ai_pipelines/services/game_plan_access.py
"""
Who may GENERATE a Game Plan (prep call) on an activity, and on which
activity — sprint 2 Game Plan, G3 (PO decisions).

THE two predicates, enforced server side by the run endpoint
(views/prep_call_view.py) and served read-only on the activity detail
(activities/serializers.py — can_run_game_plan / game_plan_blocked_reason),
so the front never offers an impossible action.

can_run_game_plan(request, activity) — PERMISSION (refused with a 403):
  * tenant: the activity belongs to the requester's tenant (JWT client
    account), whatever the role;
  * the activity's cycle: decision_cycles/services/deal_health_access.py
    can_run_deal_health — an admin, a manager (TENANT-WIDE,
    permissions/checks.py is_manager_or_admin) or the cycle's owner; reused,
    not copied;
  * without a cycle: an admin or a manager (is_manager_or_admin);
  * the activity's owner (Activity.owner).

game_plan_blocked_reason(activity) — BUSINESS RULES (200 + an INFO code,
never a 400; None when a generation is allowed), in this order:
  * PREP_CALL_TYPE_NOT_ELIGIBLE — neither a plan type nor a message type
    (constants PREP_CALL_PLAN_TYPES / PREP_CALL_MESSAGE_TYPES);
  * PREP_CALL_ACTIVITY_CLOSED — a terminal activity (not in
    activities.constants.NON_TERMINAL_STATUSES): its Game Plan stays
    readable, no new one is generated;
  * PREP_CALL_NO_CAMPAIGN_NO_DC — neither a campaign nor a decision cycle.
"""

from app_modules.activities.constants import NON_TERMINAL_STATUSES
from app_modules.decision_cycles.services.deal_health_access import can_run_deal_health
from permissions.checks import is_manager_or_admin
from permissions.compat import get_auth_ctx

from ..constants import (
    PREP_CALL_ACTIVITY_CLOSED_CODE,
    PREP_CALL_MESSAGE_TYPES,
    PREP_CALL_NO_CAMPAIGN_NO_DC_CODE,
    PREP_CALL_PLAN_TYPES,
    PREP_CALL_TYPE_NOT_ELIGIBLE_CODE,
    PrepCallOutputKind,
)


def can_run_game_plan(request, activity):
    """True when the requester may generate a Game Plan on `activity`."""
    user = getattr(request, 'user', None)
    if activity is None or user is None or not user.is_authenticated:
        return False
    ctx = get_auth_ctx(request)
    if not ctx.client_id or str(activity.client_id) != str(ctx.client_id):
        return False
    if activity.decision_cycle_id and can_run_deal_health(request, activity.decision_cycle):
        return True
    if is_manager_or_admin(request):
        return True
    return bool(activity.owner_id) and str(activity.owner_id) == str(user.id)


def game_plan_blocked_reason(activity):
    """The INFO code that stops a generation on `activity`, or None."""
    if activity.activity_type not in PREP_CALL_PLAN_TYPES | PREP_CALL_MESSAGE_TYPES:
        return PREP_CALL_TYPE_NOT_ELIGIBLE_CODE
    if activity.status not in NON_TERMINAL_STATUSES:
        return PREP_CALL_ACTIVITY_CLOSED_CODE
    if not activity.decision_cycle_id and not activity.campaign_id:
        return PREP_CALL_NO_CAMPAIGN_NO_DC_CODE
    return None


def game_plan_output_kind(activity):
    """PLAN for a conversation, MESSAGE for an email / a LinkedIn message."""
    if activity.activity_type in PREP_CALL_MESSAGE_TYPES:
        return PrepCallOutputKind.MESSAGE
    return PrepCallOutputKind.PLAN
