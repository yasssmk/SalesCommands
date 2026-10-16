# backend/tests/signals/test_techstack_api_lifecycle_and_isolation.py
"""
Sprint TechStack T5 — characterisation tests of the tech-stack API.

A. Lifecycle actions on the real endpoints, status re-read from the DB:
     POST /module-signals/tech-stack/{id}/reject/
     POST /module-signals/tech-stack/{id}/reopen/
B. Tenant isolation — a user of tenant A, on a TechStack of tenant B:
     list (absent), retrieve / PATCH / validate / reject / reopen (404,
     nothing changed); and cannot create a TechStack whose source_activity or
     account belongs to another tenant (400 OBJECT_NOT_FOUND, nothing written,
     no leak), nor whose source_activity belongs to another account of the
     same tenant (400 INVALID_ACCOUNT).

Model: test_signals_tenant_isolation.py (contract messages, `_assert_400`,
DB-state assertions, positive control) and TestBlockerAPIMultiTenant
(test_blocker_api.py) for the read / action side. Fixtures from
tests/signals/conftest.py. Payload = test_techstack_api_create_validate.py.

No application code changes: these tests characterise the existing guards
(proved non-vacuous by targeted mutation).
"""

import pytest
from django.urls import reverse
from rest_framework import status

from app_modules.signals.constants import SignalSource, SignalStatus
from app_modules.signals.models import TechStackSignal
from core.error_messages import ContactErrorMessages, CoreErrorMessages


pytestmark = pytest.mark.django_db(transaction=True)


OBJECT_NOT_FOUND = str(CoreErrorMessages.OBJECT_NOT_FOUND)
INVALID_ACCOUNT = str(ContactErrorMessages.INVALID_ACCOUNT)
TENANT_B_TECH = 'Tenant-B-only Tool'


# =============================================================================
# HELPERS
# =============================================================================

def _url_list():
    return reverse('module_signals:tech-stack-list')


def _url_detail(pk):
    return reverse('module_signals:tech-stack-detail', kwargs={'pk': pk})


def _url_action(name, pk):
    return reverse(f'module_signals:tech-stack-{name}', kwargs={'pk': pk})


def _payload(account, activity, **overrides):
    body = {
        'account': str(account.id),
        'source_activity': str(activity.id),
        'tech_name': 'Salesforce',
        'source_quote': 'We run the whole pipeline in Salesforce',
    }
    body.update(overrides)
    return body


def _mk(account, activity, user, *, tech_name='Salesforce',
        source=SignalSource.LLM_EXTRACTED):
    """PENDING when LLM_EXTRACTED, VALIDATED when MANUAL (BaseSignal.save)."""
    sig = TechStackSignal(
        account=account, source_activity=activity, tech_name=tech_name,
        source=source, source_quote=f'We use {tech_name}',
    )
    sig.save(user=user, client_id=account.client_id)
    return sig


def _rows(response):
    payload = response.json()
    rows = payload.get('results') or payload.get('data') or payload
    if isinstance(rows, dict):
        rows = rows.get('results') or rows.get('data') or []
    return rows


def _assert_400(response, message):
    """400 + the exact contract message somewhere in the standardized body."""
    assert response.status_code == status.HTTP_400_BAD_REQUEST, (
        response.status_code, response.content,
    )
    assert message in response.content.decode(), response.content


# =============================================================================
# A — reject / reopen on the real endpoints
# =============================================================================

class TestRejectAndReopen:

    def test_reject_pending_sets_rejected_and_stores_the_reason(
        self, authed_api_a, account, activity, user_a,
    ):
        sig = _mk(account, activity, user_a)
        assert sig.status == SignalStatus.PENDING

        response = authed_api_a.post(
            _url_action('reject', sig.id), {'reason': 'Not used anymore'}, format='json',
        )

        assert response.status_code == status.HTTP_200_OK, response.content
        assert response.json()['data']['status'] == SignalStatus.REJECTED
        sig.refresh_from_db()
        assert sig.status == SignalStatus.REJECTED
        assert sig.metadata['rejection_reason'] == 'Not used anymore'
        assert sig.metadata['rejected_by'] == str(user_a.id)

    def test_reject_a_validated_signal_is_refused_and_status_unchanged(
        self, authed_api_a, account, activity, user_a,
    ):
        sig = _mk(account, activity, user_a, source=SignalSource.MANUAL)
        assert sig.status == SignalStatus.VALIDATED

        response = authed_api_a.post(_url_action('reject', sig.id), {}, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        sig.refresh_from_db()
        assert sig.status == SignalStatus.VALIDATED

    def test_reopen_rejected_sets_pending(self, authed_api_a, account, activity, user_a):
        sig = _mk(account, activity, user_a)
        authed_api_a.post(_url_action('reject', sig.id), {}, format='json')
        sig.refresh_from_db()
        assert sig.status == SignalStatus.REJECTED

        response = authed_api_a.post(_url_action('reopen', sig.id), {}, format='json')

        assert response.status_code == status.HTTP_200_OK, response.content
        sig.refresh_from_db()
        assert sig.status == SignalStatus.PENDING

    def test_reopen_validated_sets_pending_and_clears_validation(
        self, authed_api_a, account, activity, user_a,
    ):
        sig = _mk(account, activity, user_a)
        authed_api_a.post(_url_action('validate', sig.id), {}, format='json')
        sig.refresh_from_db()
        assert sig.status == SignalStatus.VALIDATED
        assert sig.validated_by_id == user_a.id

        response = authed_api_a.post(_url_action('reopen', sig.id), {}, format='json')

        assert response.status_code == status.HTTP_200_OK, response.content
        sig.refresh_from_db()
        assert sig.status == SignalStatus.PENDING
        assert sig.validated_by_id is None
        assert sig.validated_at is None

    def test_reopen_a_pending_signal_is_refused(self, authed_api_a, account, activity, user_a):
        sig = _mk(account, activity, user_a)

        response = authed_api_a.post(_url_action('reopen', sig.id), {}, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        sig.refresh_from_db()
        assert sig.status == SignalStatus.PENDING


# =============================================================================
# B — tenant A acting on a TechStack of tenant B
# =============================================================================

@pytest.fixture
def tenant_b_pending(other_tenant_account, other_tenant_activity, user_b):
    return _mk(other_tenant_account, other_tenant_activity, user_b, tech_name=TENANT_B_TECH)


@pytest.fixture
def tenant_b_validated(other_tenant_account, other_tenant_activity, user_b):
    return _mk(other_tenant_account, other_tenant_activity, user_b,
               tech_name=TENANT_B_TECH, source=SignalSource.MANUAL)


class TestCrossTenantReadAndActions:

    def test_list_does_not_contain_the_other_tenant_signal(
        self, tenant_b_pending, authed_api_a, account, activity, user_a,
    ):
        own = _mk(account, activity, user_a, tech_name='Own tool')

        response = authed_api_a.get(_url_list())

        assert response.status_code == status.HTTP_200_OK
        ids = {row['id'] for row in _rows(response)}
        assert str(own.id) in ids                      # positive control
        assert str(tenant_b_pending.id) not in ids
        assert TENANT_B_TECH not in response.content.decode()

    def test_list_filtered_on_the_other_tenant_activity_is_empty(
        self, tenant_b_pending, authed_api_a, other_tenant_activity,
    ):
        response = authed_api_a.get(
            _url_list(), {'source_activity': str(other_tenant_activity.id)},
        )
        assert response.status_code == status.HTTP_200_OK
        assert str(tenant_b_pending.id) not in {row['id'] for row in _rows(response)}

    def test_retrieve_is_404(self, tenant_b_pending, authed_api_a):
        response = authed_api_a.get(_url_detail(tenant_b_pending.id))
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert TENANT_B_TECH not in response.content.decode()

    def test_patch_is_404_and_nothing_changes(self, tenant_b_pending, authed_api_a):
        response = authed_api_a.patch(
            _url_detail(tenant_b_pending.id), {'tech_name': 'Hijacked'}, format='json',
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        tenant_b_pending.refresh_from_db()
        assert tenant_b_pending.tech_name == TENANT_B_TECH

    @pytest.mark.parametrize('action', ['validate', 'reject'])
    def test_validate_and_reject_are_404_and_status_unchanged(
        self, action, tenant_b_pending, authed_api_a,
    ):
        response = authed_api_a.post(_url_action(action, tenant_b_pending.id), {}, format='json')
        assert response.status_code == status.HTTP_404_NOT_FOUND
        tenant_b_pending.refresh_from_db()
        assert tenant_b_pending.status == SignalStatus.PENDING

    def test_reopen_is_404_and_status_unchanged(self, tenant_b_validated, authed_api_a):
        response = authed_api_a.post(
            _url_action('reopen', tenant_b_validated.id), {}, format='json',
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        tenant_b_validated.refresh_from_db()
        assert tenant_b_validated.status == SignalStatus.VALIDATED


class TestCrossTenantCreate:

    def test_source_activity_of_other_tenant_is_400_object_not_found(
        self, authed_api_a, account, other_tenant_activity,
    ):
        response = authed_api_a.post(
            _url_list(), _payload(account, other_tenant_activity), format='json',
        )
        _assert_400(response, OBJECT_NOT_FOUND)
        assert 'Discovery call with Globex' not in response.content.decode()
        assert TechStackSignal.objects.count() == 0

    def test_account_of_other_tenant_is_400_object_not_found(
        self, authed_api_a, other_tenant_account, activity,
    ):
        response = authed_api_a.post(
            _url_list(), _payload(other_tenant_account, activity), format='json',
        )
        _assert_400(response, OBJECT_NOT_FOUND)
        assert 'Globex' not in response.content.decode()
        assert TechStackSignal.objects.count() == 0

    def test_source_activity_of_other_account_same_tenant_is_400_invalid_account(
        self, authed_api_a, account, other_account_activity,
    ):
        response = authed_api_a.post(
            _url_list(), _payload(account, other_account_activity), format='json',
        )
        _assert_400(response, INVALID_ACCOUNT)
        assert TechStackSignal.objects.count() == 0

    def test_positive_control_same_tenant_same_account_is_201(
        self, authed_api_a, account, activity,
    ):
        response = authed_api_a.post(_url_list(), _payload(account, activity), format='json')
        assert response.status_code == status.HTTP_201_CREATED, response.content
        assert TechStackSignal.objects.filter(account=account).count() == 1
