# app_modules/decision_cycles/services/deal_health_access.py
"""
Who may RUN a deal health on a decision cycle — sprint « Deal health v2 »,
sub-step 6b (PO decision n° 6): an admin, a manager, or the owner of the
cycle. Nobody else. Reading the snapshots is not concerned (unchanged).

THE single predicate, enforced server side by the run endpoint
(ai_pipelines/views/deal_health_view.py — the standard permission refusal)
and served read-only on the cycle payloads (serializers.py
can_run_deal_health) so the front never offers an impossible action. Meant
to be reused for reading / editing the stakeholder profiles.

The rule, on the existing patterns:
  * tenant: the cycle belongs to the requester's tenant (JWT client
    account) — strict scoping, whatever the role;
  * admin / manager: the JWT role flags, exactly as
    decision_cycles/views/manager_note_views.py _get_effective_tier /
    _is_manager_or_admin (permissions/compat.get_auth_ctx — no DB query).
    Same scope as that pattern: TENANT-WIDE — any manager of the tenant,
    not only the owner's team (the TD-27 family);
  * owner: DecisionCycle.owner (decision_cycles/models.py, OWNERSHIP).
The module gate stays the ai_pipelines registry (create: client for every
tier — permissions/registry/ai_pipelines_registry.py): the per-cycle rule
cannot be written there (ownership 'none'), hence this predicate.
"""

from permissions.compat import get_auth_ctx


def _is_manager_or_admin(ctx):
    """The JWT role flags (manager_note_views.py _get_effective_tier)."""
    if ctx.is_superuser:
        return True
    return any(
        isinstance(role, dict) and (role.get('is_admin') or role.get('is_manager'))
        for role in ctx.roles
    )


def can_run_deal_health(request, decision_cycle):
    """
    True when the requester may run a deal health on `decision_cycle`.

    Args:
        request: the DRF request (its JWT carries the tenant and role flags).
        decision_cycle: DecisionCycle instance.
    """
    user = getattr(request, 'user', None)
    if decision_cycle is None or user is None or not user.is_authenticated:
        return False
    ctx = get_auth_ctx(request)
    if not ctx.client_id or str(decision_cycle.client_id) != str(ctx.client_id):
        return False
    if _is_manager_or_admin(ctx):
        return True
    return bool(decision_cycle.owner_id) and str(decision_cycle.owner_id) == str(user.id)
