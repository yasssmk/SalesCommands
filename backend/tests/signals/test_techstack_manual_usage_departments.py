# backend/tests/signals/test_techstack_manual_usage_departments.py
"""
Tech scope (usage) finition — the MANUAL entry path writes the M2M.

The legacy single FK usage_department is gone. Creating or editing a
TechStackSignal by hand (the Create / Update serializers behind the REST
API and the wizard) now writes the multi-department usage_departments M2M:
a list of StandardDepartment ids, several accepted, independent of
usage_scope.

Real path: POST / PATCH on /module-signals/tech-stack/ through the same
authed harness the other tech API tests use.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from app_modules.signals.constants import SignalSource
from app_modules.signals.models import TechStackSignal


pytestmark = pytest.mark.django_db(transaction=True)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def dept_sales(db):
    from app_modules.core_modules.models import StandardDepartment
    d, _ = StandardDepartment.objects.get_or_create(name='Sales')
    return d


@pytest.fixture
def dept_marketing(db):
    from app_modules.core_modules.models import StandardDepartment
    d, _ = StandardDepartment.objects.get_or_create(name='Marketing')
    return d


def _url_list():
    return reverse('module_signals:tech-stack-list')


def _url_detail(pk):
    return reverse('module_signals:tech-stack-detail', kwargs={'pk': pk})


def _payload(account, activity, **overrides):
    body = {
        'account': str(account.id),
        'source_activity': str(activity.id),
        'tech_name': 'HubSpot',
        'source_quote': 'We run marketing in HubSpot',
    }
    body.update(overrides)
    return body


def _names(sig):
    return set(sig.usage_departments.values_list('name', flat=True))


# =============================================================================
# CREATE
# =============================================================================

class TestManualCreateWritesM2M:

    def test_create_with_a_single_department(
        self, authed_api_a, account, activity, dept_marketing,
    ):
        resp = authed_api_a.post(
            _url_list(),
            _payload(account, activity, usage_departments=[dept_marketing.id]),
            format='json',
        )
        assert resp.status_code == status.HTTP_201_CREATED, resp.data

        sig = TechStackSignal.objects.get(account=account)
        assert _names(sig) == {'Marketing'}

    def test_create_with_several_departments(
        self, authed_api_a, account, activity, dept_sales, dept_marketing,
    ):
        resp = authed_api_a.post(
            _url_list(),
            _payload(
                account, activity,
                usage_departments=[dept_sales.id, dept_marketing.id],
            ),
            format='json',
        )
        assert resp.status_code == status.HTTP_201_CREATED, resp.data

        sig = TechStackSignal.objects.get(account=account)
        assert _names(sig) == {'Sales', 'Marketing'}

    def test_create_without_departments_is_valid_and_empty(
        self, authed_api_a, account, activity,
    ):
        resp = authed_api_a.post(
            _url_list(), _payload(account, activity), format='json',
        )
        assert resp.status_code == status.HTTP_201_CREATED, resp.data
        sig = TechStackSignal.objects.get(account=account)
        assert _names(sig) == set()

    def test_departments_are_independent_of_usage_scope(
        self, authed_api_a, account, activity, dept_marketing,
    ):
        """
        No scope↔department conditional remains: a COMPANY-scale tool may
        still carry designated departments (the old FK rule forbade this).
        """
        resp = authed_api_a.post(
            _url_list(),
            _payload(
                account, activity,
                usage_scope='COMPANY',
                usage_departments=[dept_marketing.id],
            ),
            format='json',
        )
        assert resp.status_code == status.HTTP_201_CREATED, resp.data
        sig = TechStackSignal.objects.get(account=account)
        assert sig.usage_scope == 'COMPANY'
        assert _names(sig) == {'Marketing'}

    def test_the_dropped_singular_key_is_not_exposed_on_read(
        self, authed_api_a, account, activity, dept_marketing,
    ):
        authed_api_a.post(
            _url_list(),
            _payload(account, activity, usage_departments=[dept_marketing.id]),
            format='json',
        )
        resp = authed_api_a.get(_url_list())
        rows = resp.data.get('results') or resp.data.get('data') or resp.data
        if isinstance(rows, dict):
            rows = rows.get('results') or rows.get('data') or []
        row = rows[0]
        assert 'usage_department' not in row
        assert 'usage_departments' in row


# =============================================================================
# UPDATE
# =============================================================================

class TestManualUpdateWritesM2M:

    def _make(self, account, activity, user, depts=()):
        sig = TechStackSignal(
            account=account,
            source_activity=activity,
            tech_name='HubSpot',
            source=SignalSource.MANUAL,
            source_quote='We use HubSpot',
        )
        sig.save(user=user, client_id=account.client_id)
        if depts:
            sig.usage_departments.set(depts)
        return sig

    def test_patch_replaces_the_department_set(
        self, authed_api_a, account, activity, user_a, dept_sales, dept_marketing,
    ):
        sig = self._make(account, activity, user_a, depts=[dept_sales])

        resp = authed_api_a.patch(
            _url_detail(sig.id),
            {'usage_departments': [dept_marketing.id]},
            format='json',
        )
        assert resp.status_code == status.HTTP_200_OK, resp.data

        sig.refresh_from_db()
        assert _names(sig) == {'Marketing'}

    def test_patch_can_clear_the_department_set(
        self, authed_api_a, account, activity, user_a, dept_sales,
    ):
        sig = self._make(account, activity, user_a, depts=[dept_sales])

        resp = authed_api_a.patch(
            _url_detail(sig.id),
            {'usage_departments': []},
            format='json',
        )
        assert resp.status_code == status.HTTP_200_OK, resp.data

        sig.refresh_from_db()
        assert _names(sig) == set()

    def test_notes_only_patch_leaves_departments_untouched(
        self, authed_api_a, account, activity, user_a, dept_sales,
    ):
        sig = self._make(account, activity, user_a, depts=[dept_sales])

        resp = authed_api_a.patch(
            _url_detail(sig.id), {'notes': 'renegotiating'}, format='json',
        )
        assert resp.status_code == status.HTTP_200_OK, resp.data

        sig.refresh_from_db()
        assert _names(sig) == {'Sales'}
