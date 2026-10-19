# backend/tests/signals/test_competitor_api_lifecycle_and_isolation.py
"""
Sprint Competitor C0 — characterisation tests of the competitors API.

No API test called /module-signals/competitors/ before this file.

A. CRUD on the real endpoints, DB state re-read:
     POST   /module-signals/competitors/            (create)
     GET    /module-signals/competitors/{id}/       (retrieve)
     PATCH  /module-signals/competitors/{id}/       (partial update)
     DELETE /module-signals/competitors/{id}/       (destroy)
   Create without source_activity -> 400 SOURCE_ACTIVITY_REQUIRED (the
   competitor Create serializer raises a StandardizedValidationError, so the
   TD-248 handler defect is not on this path).
B. Lifecycle: validate / reject / reopen, status re-read from the DB.
C. Tenant isolation — a user of tenant A, on a Competitor of tenant B: list
   (absent), retrieve / PATCH / validate / reject / reopen / DELETE (404,
   nothing changed); create with a source_activity or account of another
   tenant (400 OBJECT_NOT_FOUND, nothing written, no leak) or a source_activity
   of another account of the same tenant (400 INVALID_ACCOUNT).

Model: test_techstack_api_lifecycle_and_isolation.py (Sprint TechStack T5),
itself calqued on test_signals_tenant_isolation.py. Fixtures from
tests/signals/conftest.py.

No application code changes: these tests characterise the existing guards
(proved non-vacuous by targeted mutation).
"""

import pytest
from django.urls import reverse
from rest_framework import status

from app_modules.signals.constants import SignalSource, SignalStatus
from app_modules.signals.models import CompetitorSignal
from core.error_messages import (
    ContactErrorMessages,
    CoreErrorMessages,
    SignalErrorMessages,
)


pytestmark = pytest.mark.django_db(transaction=True)


OBJECT_NOT_FOUND = str(CoreErrorMessages.OBJECT_NOT_FOUND)
INVALID_ACCOUNT = str(ContactErrorMessages.INVALID_ACCOUNT)
SOURCE_ACTIVITY_REQUIRED = str(SignalErrorMessages.SOURCE_ACTIVITY_REQUIRED)
TENANT_B_COMPETITOR = 'Tenant-B-only Rival'


# =============================================================================
# HELPERS
# =============================================================================

def _url_list():
    return reverse('module_signals:competitor-list')


def _url_detail(pk):
    return reverse('module_signals:competitor-detail', kwargs={'pk': pk})


def _url_action(name, pk):
    return reverse(f'module_signals:competitor-{name}', kwargs={'pk': pk})


def _payload(account, activity, **overrides):
    body = {
        'account': str(account.id),
        'source_activity': str(activity.id),
        'competitor_name': 'Intercom',
        'summary': 'The prospect is also evaluating Intercom instead of us.',
        'source_quote': "We're also looking at Intercom.",
    }
    body.update(overrides)
    return body


def _mk(account, activity, user, *, competitor_name='Intercom',
        source=SignalSource.LLM_EXTRACTED):
    """PENDING when LLM_EXTRACTED, VALIDATED when MANUAL (BaseSignal.save)."""
    sig = CompetitorSignal(
        account=account, source_activity=activity,
        competitor_name=competitor_name,
        summary=f'The prospect weighs {competitor_name} against us.',
        source=source, source_quote=f'We also look at {competitor_name}',
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
# A — CRUD
# =============================================================================

class TestCreate:

    def test_manual_create_is_201_and_lands_validated(self, authed_api_a, account, activity):
        response = authed_api_a.post(
            _url_list(), _payload(account, activity, source='MANUAL'), format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED, response.content
        sig = CompetitorSignal.objects.get(account=account)
        assert sig.competitor_name == 'Intercom'
        assert sig.competitor_name_normalized == 'intercom'
        assert sig.status == SignalStatus.VALIDATED
        assert sig.source_activity_id == activity.id

    def test_create_without_source_activity_is_400_and_writes_nothing(
        self, authed_api_a, account, activity,
    ):
        payload = _payload(account, activity)
        payload.pop('source_activity')

        response = authed_api_a.post(_url_list(), payload, format='json')

        _assert_400(response, SOURCE_ACTIVITY_REQUIRED)
        assert CompetitorSignal.objects.count() == 0

    @pytest.mark.parametrize('field', ['competitor_name', 'summary'])
    def test_create_without_a_required_field_is_400(
        self, field, authed_api_a, account, activity,
    ):
        payload = _payload(account, activity)
        payload.pop(field)

        response = authed_api_a.post(_url_list(), payload, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.content
        assert CompetitorSignal.objects.count() == 0

    @pytest.mark.parametrize('field', ['competitor_name', 'summary'])
    @pytest.mark.parametrize('blank', ['', '   '])
    def test_create_with_a_blank_required_field_is_400(
        self, field, blank, authed_api_a, account, activity,
    ):
        response = authed_api_a.post(
            _url_list(), _payload(account, activity, **{field: blank}), format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.content
        assert CompetitorSignal.objects.count() == 0

    def test_normalized_name_is_not_writable_from_the_api(
        self, authed_api_a, account, activity,
    ):
        authed_api_a.post(
            _url_list(),
            _payload(account, activity, competitor_name='  Acme   Corp ',
                     competitor_name_normalized='hand-written'),
            format='json',
        )

        sig = CompetitorSignal.objects.get(account=account)
        assert sig.competitor_name_normalized == 'acme corp'


class TestRetrievePatchDelete:

    def test_retrieve_returns_name_and_summary(self, authed_api_a, account, activity, user_a):
        sig = _mk(account, activity, user_a)

        response = authed_api_a.get(_url_detail(sig.id))

        assert response.status_code == status.HTTP_200_OK, response.content
        # GET retrieve returns the serializer payload directly (no {success,
        # data} wrapper — only state-changing actions wrap, cf. test_blocker_api).
        data = response.json()
        assert data['id'] == str(sig.id)
        assert data['competitor_name'] == 'Intercom'
        assert data['summary'] == sig.summary

    def test_patch_name_summary_and_quote_and_the_normalized_key_follows(
        self, authed_api_a, account, activity, user_a,
    ):
        sig = _mk(account, activity, user_a, competitor_name='Inter com')

        response = authed_api_a.patch(
            _url_detail(sig.id),
            {
                'competitor_name': 'Intercom',
                'summary': 'Intercom is the other option on the table.',
                'source_quote': 'The other option is Intercom.',
            },
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK, response.content
        sig.refresh_from_db()
        assert sig.competitor_name == 'Intercom'
        assert sig.competitor_name_normalized == 'intercom'
        assert sig.summary == 'Intercom is the other option on the table.'
        assert sig.source_quote == 'The other option is Intercom.'

    @pytest.mark.parametrize('field', ['competitor_name', 'summary'])
    def test_blanking_a_required_field_is_refused(
        self, field, authed_api_a, account, activity, user_a,
    ):
        sig = _mk(account, activity, user_a)
        before = getattr(sig, field)

        response = authed_api_a.patch(_url_detail(sig.id), {field: '   '}, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.content
        sig.refresh_from_db()
        assert getattr(sig, field) == before

    def test_delete_is_204_and_removes_the_row(self, authed_api_a, account, activity, user_a):
        sig = _mk(account, activity, user_a)

        response = authed_api_a.delete(_url_detail(sig.id))

        assert response.status_code == status.HTTP_204_NO_CONTENT, response.content
        assert not CompetitorSignal.objects.filter(pk=sig.pk).exists()


# =============================================================================
# B — validate / reject / reopen on the real endpoints
# =============================================================================

class TestValidateRejectReopen:

    def test_validate_pending_sets_validated(self, authed_api_a, account, activity, user_a):
        sig = _mk(account, activity, user_a)
        assert sig.status == SignalStatus.PENDING

        response = authed_api_a.post(_url_action('validate', sig.id), {}, format='json')

        assert response.status_code == status.HTTP_200_OK, response.content
        sig.refresh_from_db()
        assert sig.status == SignalStatus.VALIDATED
        assert sig.validated_by_id == user_a.id
        assert sig.validated_at is not None

    def test_reject_pending_sets_rejected_and_stores_the_reason(
        self, authed_api_a, account, activity, user_a,
    ):
        sig = _mk(account, activity, user_a)

        response = authed_api_a.post(
            _url_action('reject', sig.id), {'reason': 'Not a competitor'}, format='json',
        )

        assert response.status_code == status.HTTP_200_OK, response.content
        assert response.json()['data']['status'] == SignalStatus.REJECTED
        sig.refresh_from_db()
        assert sig.status == SignalStatus.REJECTED
        assert sig.metadata['rejection_reason'] == 'Not a competitor'
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
# C — tenant A acting on a Competitor of tenant B
# =============================================================================

@pytest.fixture
def tenant_b_pending(other_tenant_account, other_tenant_activity, user_b):
    return _mk(other_tenant_account, other_tenant_activity, user_b,
               competitor_name=TENANT_B_COMPETITOR)


@pytest.fixture
def tenant_b_validated(other_tenant_account, other_tenant_activity, user_b):
    return _mk(other_tenant_account, other_tenant_activity, user_b,
               competitor_name=TENANT_B_COMPETITOR, source=SignalSource.MANUAL)


class TestCrossTenantReadAndActions:

    def test_list_does_not_contain_the_other_tenant_signal(
        self, tenant_b_pending, authed_api_a, account, activity, user_a,
    ):
        own = _mk(account, activity, user_a, competitor_name='Own rival')

        response = authed_api_a.get(_url_list())

        assert response.status_code == status.HTTP_200_OK
        ids = {row['id'] for row in _rows(response)}
        assert str(own.id) in ids                      # positive control
        assert str(tenant_b_pending.id) not in ids
        assert TENANT_B_COMPETITOR not in response.content.decode()

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
        assert TENANT_B_COMPETITOR not in response.content.decode()

    def test_patch_is_404_and_nothing_changes(self, tenant_b_pending, authed_api_a):
        response = authed_api_a.patch(
            _url_detail(tenant_b_pending.id), {'competitor_name': 'Hijacked'}, format='json',
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        tenant_b_pending.refresh_from_db()
        assert tenant_b_pending.competitor_name == TENANT_B_COMPETITOR

    def test_delete_is_404_and_the_row_stays(self, tenant_b_pending, authed_api_a):
        response = authed_api_a.delete(_url_detail(tenant_b_pending.id))
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert CompetitorSignal.objects.filter(pk=tenant_b_pending.pk).exists()

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
        assert CompetitorSignal.objects.count() == 0

    def test_account_of_other_tenant_is_400_object_not_found(
        self, authed_api_a, other_tenant_account, activity,
    ):
        response = authed_api_a.post(
            _url_list(), _payload(other_tenant_account, activity), format='json',
        )
        _assert_400(response, OBJECT_NOT_FOUND)
        assert 'Globex' not in response.content.decode()
        assert CompetitorSignal.objects.count() == 0

    def test_source_activity_of_other_account_same_tenant_is_400_invalid_account(
        self, authed_api_a, account, other_account_activity,
    ):
        response = authed_api_a.post(
            _url_list(), _payload(account, other_account_activity), format='json',
        )
        _assert_400(response, INVALID_ACCOUNT)
        assert CompetitorSignal.objects.count() == 0

    def test_positive_control_same_tenant_same_account_is_201(
        self, authed_api_a, account, activity,
    ):
        response = authed_api_a.post(_url_list(), _payload(account, activity), format='json')
        assert response.status_code == status.HTTP_201_CREATED, response.content
        assert CompetitorSignal.objects.filter(account=account).count() == 1
