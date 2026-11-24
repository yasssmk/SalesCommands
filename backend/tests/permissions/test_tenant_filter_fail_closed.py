# backend/tests/permissions/test_tenant_filter_fail_closed.py
"""
FAIL-CLOSED tenant filter (TD-323, Lot 0 sécurité 0.2).

``ClientScopeManager.ViewMixin.filter_queryset_by_client`` (core/client_scope.py)
is the shared tenant filter every ``BaseAPIView.get_queryset`` goes through.
When the queryset's model had NO tenant field (no ``client_account`` /
``client_id``, not the tenant root), it used to log a warning and return the
queryset UNFILTERED: every tenant's rows, to any authenticated user. That is
exactly how ClientAccountViewSet leaked (TD-322).

It now FAILS CLOSED: such a queryset comes back EMPTY and an ERROR is logged.
The only way out is an explicit, documented opt-out on the view
(``tenant_scope_exempt_reason``, a non-empty justification) — and no live view
uses it (the read-only inventory of 0.2 found none), which the last test
locks.

The path exercised is the real one: a BaseAPIView subclass whose
``get_queryset`` (BaseAPIView → filter_queryset_by_client) runs on a DRF
request authenticated on tenant A. ``StandardDepartment`` is the live model
with no tenant field (a global reference list).

DB: Postgres.
"""

import logging

import pytest
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.test import APIRequestFactory, force_authenticate

from app_modules.core_modules.models import StandardDepartment
from core.apps_shared_methods import BaseAPIView
from core.client_scope import ClientScopeManager, TENANT_SCOPE_EXEMPT_ATTR
from end_users.models import ClientAccount, User

from tests.signals.conftest import (  # noqa: F401
    tenant_a_id,
    tenant_b_id,
    client_account_a,
    client_account_b,
    role_individual_a,
    user_a,
)

DEPARTMENT_NAMES = (
    StandardDepartment.DepartmentChoices.HR,
    StandardDepartment.DepartmentChoices.FINANCE,
)


class _TenantlessView(BaseAPIView):
    """A view whose queryset model has no tenant field."""
    queryset = StandardDepartment.objects.all()


class _ExemptView(BaseAPIView):
    queryset = StandardDepartment.objects.all()
    tenant_scope_exempt_reason = 'Global reference list, identical for every tenant.'


class _BlankReasonView(BaseAPIView):
    queryset = StandardDepartment.objects.all()
    tenant_scope_exempt_reason = '   '


class _TenantRootView(BaseAPIView):
    queryset = ClientAccount.objects.all()


@pytest.fixture
def departments(db):
    for name in DEPARTMENT_NAMES:
        StandardDepartment.objects.get_or_create(name=name)
    count = StandardDepartment.objects.count()
    assert count >= len(DEPARTMENT_NAMES), 'non-vacuity: rows must exist'
    return count


def _view_for(view_cls, user, tenant_id):
    """Instantiate the view on a DRF request authenticated on ``tenant_id``,
    with the claims shape produced by CustomJWTAuthentication."""
    django_request = APIRequestFactory().get('/')
    force_authenticate(
        django_request,
        user=user,
        token={'origin': 'end_users', 'user_id': str(user.id),
               'client_account': str(tenant_id)},
    )
    view = view_cls()
    view.setup(django_request)
    view.request = view.initialize_request(django_request)
    view.format_kwarg = None
    return view


@pytest.mark.django_db
class TestFailClosed:

    def test_tenantless_model_is_never_returned_unfiltered(
        self, departments, user_a, client_account_a
    ):
        view = _view_for(_TenantlessView, user_a, client_account_a.id)
        assert view.get_queryset().count() == 0, (
            'a model without tenant field came back unfiltered '
            f'({departments} rows visible to tenant A)'
        )

    def test_fallback_logs_an_error(
        self, departments, user_a, client_account_a, caplog
    ):
        view = _view_for(_TenantlessView, user_a, client_account_a.id)
        with caplog.at_level(logging.ERROR, logger='core.client_scope'):
            list(view.get_queryset())
        errors = [r for r in caplog.records
                  if r.levelno >= logging.ERROR and r.getMessage() == 'no_client_scope_field']
        assert errors, 'the fail-closed branch must log an ERROR'
        assert errors[0].model == 'StandardDepartment'
        assert errors[0].view == '_TenantlessView'

    def test_blank_justification_is_not_an_opt_out(
        self, departments, user_a, client_account_a
    ):
        view = _view_for(_BlankReasonView, user_a, client_account_a.id)
        assert view.get_queryset().count() == 0

    def test_explicit_opt_out_returns_the_queryset(
        self, departments, user_a, client_account_a
    ):
        view = _view_for(_ExemptView, user_a, client_account_a.id)
        assert view.get_queryset().count() == departments


@pytest.mark.django_db
class TestScopedModelsUnchanged:
    """Fail-closed touches only the no-field branch: tenant-scoped models
    keep being filtered on the token's tenant."""

    def test_tenant_root_is_pinned_to_own_tenant(
        self, user_a, client_account_a, client_account_b
    ):
        view = _view_for(_TenantRootView, user_a, client_account_a.id)
        assert list(view.get_queryset().values_list('id', flat=True)) == [client_account_a.id]

    def test_client_account_fk_model_is_filtered(
        self, user_a, client_account_a, client_account_b
    ):
        User.objects.create(email='b@tenant-b.test', client_account=client_account_b)

        class _UserView(BaseAPIView):
            queryset = User.objects.all()

        view = _view_for(_UserView, user_a, client_account_a.id)
        assert set(view.get_queryset().values_list('client_account_id', flat=True)) == {
            client_account_a.id
        }


def _live_view_classes():
    def walk(patterns):
        for p in patterns:
            if isinstance(p, URLResolver):
                yield from walk(p.url_patterns)
            elif isinstance(p, URLPattern):
                cls = getattr(p.callback, 'cls', None) or getattr(p.callback, 'view_class', None)
                if cls is not None:
                    yield cls
    return set(walk(get_resolver().url_patterns))


def test_no_live_view_opts_out_of_the_tenant_filter():
    """The opt-out exists for a justified exception; today none is
    justified (0.2 inventory). A new one must be a deliberate, reviewed
    change of this test."""
    exempt = sorted(
        f'{cls.__module__}.{cls.__name__}'
        for cls in _live_view_classes()
        if issubclass(cls, ClientScopeManager.ViewMixin)
        and getattr(cls, TENANT_SCOPE_EXEMPT_ATTR, None)
    )
    assert exempt == []
