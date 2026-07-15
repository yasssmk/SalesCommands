"""
Shared role-scope queryset filtering.

This is the SINGLE SOURCE OF TRUTH for `mine` / `team` / `client` scope
filtering. It was extracted verbatim from
``ScopedQuerysetMixin.get_queryset`` so that both the DRF mixin AND
non-view consumers (e.g. the BI aggregation layer) apply IDENTICAL scope
filtering — including the account-owner (C6) inheritance in ``mine``
(``account__account_owner_id``).

Behaviour contract (unchanged from the mixin):

- scope ``None`` / ``'none'`` -> ``queryset.none()``
- scope ``'client'``         -> queryset returned unchanged (tenant filtering
  is applied by the caller BEFORE this function)
- scope ``'team'``           -> OR of owner_team / owner_user / created_by /
  assigned_to_user over the manager's team (+ sub-teams) members
- scope ``'mine'``           -> OR of owner_user / created_by /
  assigned_to_user / account_owner_user (C6) for the current user; empty
  ``queryset.none()`` when the module declares no ownership field
- any other scope value      -> queryset returned unchanged

Field names are resolved through ``OWNERSHIP_MAP`` (``resolve_field``) exactly
as the mixin did — no convention, no per-model guessing.

IMPORTANT: do NOT reimplement mine/team scope filtering anywhere else. Reuse
this function. In particular ``permissions.scoping.apply_scope_filter`` does
NOT carry the C6 account-owner term and must not be used where C6 matters.
"""

import logging

from django.db.models import Q, QuerySet

from .ownership import resolve_field

logger = logging.getLogger(__name__)

# Robust import of get_correlation_id (mirrors permissions/mixins.py)
try:
    from backend.core.logging.context import get_correlation_id
except ImportError:  # pragma: no cover - import shim
    try:
        from core.logging.context import get_correlation_id
    except ImportError:  # pragma: no cover - import shim
        def get_correlation_id():
            return '-'


def _model_field_names(queryset: QuerySet) -> set:
    return {f.name for f in queryset.model._meta.get_fields()}


def _is_valid_field(field_name, model_fields) -> bool:
    """A field is usable in a Q filter if it is a traversal (contains ``__``)
    or a real field on the model. Matches the mixin helpers exactly."""
    if not field_name:
        return False
    # Traversal fields (with __) are always valid for Q filters
    if '__' in field_name:
        return True
    return field_name in model_fields


def _apply_team_scope(queryset: QuerySet, module: str, auth_ctx) -> QuerySet:
    """Team scope: manager's teams (+ sub-teams) members, plus self.

    Extracted verbatim from ScopedQuerysetMixin.get_queryset (team branch).
    """
    # Imported here (as in the mixin) to avoid a circular import at module load.
    from permissions.owner_scope import (
        get_all_descendant_team_ids,
        get_team_member_ids,
    )

    managed_team_ids = set()

    # Teams where the user is the manager
    if auth_ctx.user_id and auth_ctx.client_id:
        from end_users.models import Team
        manager_teams = Team.objects.filter(
            client_account_id=auth_ctx.client_id,
            manager_id=auth_ctx.user_id,
        ).values_list('id', flat=True)
        managed_team_ids = set(str(tid) for tid in manager_teams)

    # Include the user's own team
    if auth_ctx.team_id:
        managed_team_ids.add(str(auth_ctx.team_id))

    # Expand to all descendant (sub-)teams
    all_team_ids = (
        get_all_descendant_team_ids(managed_team_ids, auth_ctx.client_id)
        if managed_team_ids else set()
    )

    # Resolve all members of those teams, always including self
    team_member_ids = (
        get_team_member_ids(all_team_ids, auth_ctx.client_id)
        if all_team_ids else set()
    )
    team_member_ids.add(auth_ctx.user_id)

    logger.debug("scope_team", extra={
        'correlation_id': get_correlation_id(),
        'scope': 'team',
        'managed_teams': list(managed_team_ids),
        'all_teams': list(all_team_ids),
        'team_members_count': len(team_member_ids),
        'event': 'queryset_filter',
    })

    q_filter = Q()
    model_fields = _model_field_names(queryset)

    # owner_team IN all_team_ids
    team_field = resolve_field(module, 'owner_team')
    if team_field and _is_valid_field(team_field, model_fields) and all_team_ids:
        q_filter |= Q(**{f'{team_field}__in': all_team_ids})

    # owner_user IN team_member_ids
    owner_field = resolve_field(module, 'owner_user')
    if owner_field and _is_valid_field(owner_field, model_fields) and team_member_ids:
        q_filter |= Q(**{f'{owner_field}__in': team_member_ids})

    # created_by IN team_member_ids
    created_field = resolve_field(module, 'created_by')
    if created_field and _is_valid_field(created_field, model_fields):
        q_filter |= Q(**{f'{created_field}__in': team_member_ids})

    # assigned_to_user IN team_member_ids
    assigned_field = resolve_field(module, 'assigned_to_user')
    if assigned_field and _is_valid_field(assigned_field, model_fields):
        q_filter |= Q(**{f'{assigned_field}__in': team_member_ids})

    if q_filter:
        queryset = queryset.filter(q_filter)
    else:
        logger.debug("no_team_ownership_fields", extra={
            'correlation_id': get_correlation_id(),
            'biz_module': module,
            'event': 'queryset_filter',
        })
    return queryset


def _apply_mine_scope(queryset: QuerySet, module: str, auth_ctx) -> QuerySet:
    """Mine scope: records owned/created/assigned by the user, PLUS records
    whose parent account is owned by the user (C6 account-owner inheritance).

    Extracted verbatim from ScopedQuerysetMixin.get_queryset (mine branch).
    """
    q_filter = Q()
    model_fields = _model_field_names(queryset)

    # owner_user == user
    owner_field = resolve_field(module, 'owner_user')
    if owner_field and _is_valid_field(owner_field, model_fields):
        q_filter |= Q(**{owner_field: auth_ctx.user_id})

    # created_by == user
    created_field = resolve_field(module, 'created_by')
    if created_field and _is_valid_field(created_field, model_fields):
        q_filter |= Q(**{created_field: auth_ctx.user_id})

    # assigned_to_user == user
    assigned_field = resolve_field(module, 'assigned_to_user')
    if assigned_field and _is_valid_field(assigned_field, model_fields):
        q_filter |= Q(**{assigned_field: auth_ctx.user_id})

    # account_owner_user == user  (C6 account-owner inheritance)
    # Mapped to a traversal (account__account_owner_id); accepted by
    # _is_valid_field because it contains '__'. This is what lets an account
    # owner (AE) act on records created by anyone else on their account.
    account_owner_field = resolve_field(module, 'account_owner_user')
    if account_owner_field and _is_valid_field(account_owner_field, model_fields):
        q_filter |= Q(**{account_owner_field: auth_ctx.user_id})

    if q_filter:
        return queryset.filter(q_filter)

    # No ownership fields configured = no access for mine scope
    logger.warning("no_mine_ownership_fields_deny", extra={
        'correlation_id': get_correlation_id(),
        'biz_module': module,
        'event': 'queryset_filter',
    })
    return queryset.none()


def apply_role_scope(queryset: QuerySet, *, module: str, scope, auth_ctx) -> QuerySet:
    """Apply role-based (mine/team/client) filtering to ``queryset``.

    This is the reusable entry point shared by ``ScopedQuerysetMixin`` and any
    non-view consumer (BI aggregation). Tenant (client_id) filtering must be
    applied by the caller BEFORE calling this — ``'client'`` scope returns the
    queryset unchanged.

    Args:
        queryset: base queryset (already tenant-filtered by the caller).
        module: business module name (key into ``OWNERSHIP_MAP``).
        scope: resolved scope — ``'client'`` | ``'team'`` | ``'mine'`` |
            ``'none'`` | ``None``.
        auth_ctx: ``AuthContext`` (from ``get_auth_ctx``) providing
            ``user_id`` / ``client_id`` / ``team_id``.

    Returns:
        The scope-filtered queryset.
    """
    # 'none' / None -> no access
    if scope is None or scope == 'none':
        return queryset.none()

    # 'client' -> already tenant-filtered by the caller, nothing more to do
    if scope == 'client':
        return queryset

    if scope == 'team':
        return _apply_team_scope(queryset, module, auth_ctx)

    if scope == 'mine':
        return _apply_mine_scope(queryset, module, auth_ctx)

    # Unknown scope -> unchanged (preserves prior mixin behaviour where no
    # branch matched and the queryset fell through untouched).
    return queryset
