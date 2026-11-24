# backend/tests/permissions/test_get_queryset_through_tenant_filter.py
"""
GUARDRAIL — every redefined get_queryset goes through the tenant filter
(TD-323, Lot 0 sécurité 0.3).

The shared tenant filter only protects a view whose ``get_queryset`` reaches
it: ``BaseAPIView.get_queryset`` → ``filter_queryset_by_client``, wrapped by
``ScopedQuerysetMixin.get_queryset``. A view that REDEFINES ``get_queryset``
and builds its queryset from ``Model.objects…`` without going through that
socle serves every tenant — that is exactly how ClientAccountViewSet leaked
(TD-322: ``get_queryset`` = ``ClientAccount.objects.all()``, no ``super()``).

This test walks the live URL configuration (shared ``live_view_classes``
fixture) and, for every live view built on ``BaseAPIView`` or
``ScopedQuerysetMixin``, inspects EVERY project-level ``get_queryset`` override
in its MRO. Each one must call ``super().get_queryset(...)`` or
``self.filter_queryset_by_client(...)`` — checked on the code's AST, so a
comment or docstring mentioning them does not count — or be listed in
``GET_QUERYSET_TENANT_FILTER_ALLOWLIST`` with its justification.

Limit (by design): the check proves the socle is CALLED, not that its result
is the one returned; it is a guardrail against forgetting the socle, not a
proof of isolation (the per-module isolation tests do that).
"""

import ast
import inspect
import textwrap

from core.apps_shared_methods import BaseAPIView
from permissions.mixins import ScopedQuerysetMixin

# The socle itself: the two get_queryset implementations every override must
# reach. They are not subject to the rule.
SOCLE_GET_QUERYSETS = frozenset({BaseAPIView.get_queryset, ScopedQuerysetMixin.get_queryset})

# Third-party code (DRF / Django) is not checked: only project overrides are.
THIRD_PARTY_PREFIXES = ('rest_framework.', 'django.')

# Overrides allowed to NOT call the socle, each with WHY it is still scoped to
# the requester's tenant. Key: "<module>.<Class>" of the class DEFINING the
# get_queryset override. An entry is a reviewed exception, never a shortcut.
GET_QUERYSET_TENANT_FILTER_ALLOWLIST = {
    'app_modules.decision_cycles.views.deal_product_views.DealProductViewSet': (
        'Nested under a DecisionCycle: rows are filtered on decision_cycle=<parent> '
        'AND client_id=<parent>.client_id (deal_product_views.py:123-128), and the '
        'parent is resolved through DecisionCycleViewSet.get_queryset() — the full '
        'socle, tenant + role scope (CycleScopedMixin, deal_product_views.py:52-76): '
        'another tenant\'s cycle is a 404.'
    ),
    'app_modules.decision_cycles.views.deal_health_snapshot_views.DealHealthSnapshotViewSet': (
        'Same pattern as DealProductViewSet (CycleScopedMixin): filtered on '
        'decision_cycle=<parent> AND client_id=<parent>.client_id '
        '(deal_health_snapshot_views.py:72-81), parent resolved through '
        'DecisionCycleViewSet.get_queryset().'
    ),
    'app_modules.decision_cycles.views.manager_note_views.ManagerNoteViewSet': (
        'Filtered on decision_cycle=<parent> AND client_id=<parent>.client_id '
        '(manager_note_views.py:109-114); the parent cycle is looked up with '
        'client_id=<tenant of the token> (manager_note_views.py:80-95) — '
        'tenant-wide on purpose (TD-27), another tenant\'s cycle or a token '
        'without tenant is a 404.'
    ),
}


def _calls_tenant_filter(func):
    """True if the function's code calls super().get_queryset(...) or
    <anything>.filter_queryset_by_client(...)."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        attr, owner = node.func.attr, node.func.value
        if attr == 'filter_queryset_by_client':
            return True
        if (attr == 'get_queryset' and isinstance(owner, ast.Call)
                and isinstance(owner.func, ast.Name) and owner.func.id == 'super'):
            return True
    return False


def _project_overrides(view_cls):
    """(defining class, function) for every project-level get_queryset
    redefinition in the view's MRO, the socle excluded."""
    for klass in view_cls.__mro__:
        func = klass.__dict__.get('get_queryset')
        if func is None or func in SOCLE_GET_QUERYSETS:
            continue
        if klass.__module__.startswith(THIRD_PARTY_PREFIXES):
            continue
        yield klass, func


def _label(klass):
    return f'{klass.__module__}.{klass.__name__}'


def _guarded_live_views(live_view_classes):
    return [
        cls for cls in live_view_classes
        if issubclass(cls, (BaseAPIView, ScopedQuerysetMixin))
    ]


def test_every_get_queryset_override_goes_through_the_tenant_filter(live_view_classes):
    offenders = {}
    for view_cls in _guarded_live_views(live_view_classes):
        for klass, func in _project_overrides(view_cls):
            label = _label(klass)
            if label in GET_QUERYSET_TENANT_FILTER_ALLOWLIST:
                continue
            if not _calls_tenant_filter(func):
                source_file = inspect.getsourcefile(func)
                line = inspect.getsourcelines(func)[1]
                offenders[label] = f'{source_file}:{line}'

    assert not offenders, (
        'These get_queryset overrides bypass the shared tenant filter, so they '
        'can serve OTHER tenants\' rows (TD-322 / TD-323):\n'
        + '\n'.join(f'  - {label}  ({where})' for label, where in sorted(offenders.items()))
        + '\n\nWhat to do: build the queryset from `super().get_queryset()` '
        '(BaseAPIView → filter_queryset_by_client; ScopedQuerysetMixin also '
        'applies the role scope), or pass it through '
        '`self.filter_queryset_by_client(...)`. Only if the queryset is '
        'provably scoped to the requester\'s tenant by other means, add the '
        'class to GET_QUERYSET_TENANT_FILTER_ALLOWLIST in this file with the '
        'justification — a reviewed exception, never a shortcut.'
    )


def test_allowlist_has_no_stale_or_unjustified_entry(live_view_classes):
    """Every allowlisted class still defines a live get_queryset override
    (no stale entry) and carries a real justification."""
    live_overriders = {
        _label(klass)
        for view_cls in _guarded_live_views(live_view_classes)
        for klass, _ in _project_overrides(view_cls)
    }
    stale = sorted(set(GET_QUERYSET_TENANT_FILTER_ALLOWLIST) - live_overriders)
    assert not stale, f'Allowlist entries with no live get_queryset override: {stale}'
    unjustified = sorted(
        label for label, why in GET_QUERYSET_TENANT_FILTER_ALLOWLIST.items()
        if not (why or '').strip()
    )
    assert not unjustified, f'Allowlist entries without justification: {unjustified}'


def test_the_walker_sees_the_guarded_views(live_view_classes):
    """Non-vacuity of the walk itself: the guardrail actually inspects live
    overrides (it would pass vacuously on an empty walk)."""
    guarded = _guarded_live_views(live_view_classes)
    overriders = [klass for view_cls in guarded for klass, _ in _project_overrides(view_cls)]
    assert len(guarded) >= 50
    assert len(overriders) >= 20
    assert any(_label(k) == 'end_users.views.client_account_viewset.ClientAccountViewSet'
               for k in overriders)
