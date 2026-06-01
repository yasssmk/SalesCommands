# backend/tests/signals/test_blocker_api.py
"""
API-level coverage for BlockerSignal endpoints (Sprint B1).

Endpoints under test (mounted via app_modules.signals.urls):
  GET    /module-signals/blockers/
  POST   /module-signals/blockers/
  GET    /module-signals/blockers/{id}/
  PATCH  /module-signals/blockers/{id}/
  POST   /module-signals/blockers/{id}/validate/
  POST   /module-signals/blockers/{id}/reject/

Auth is plugged in via `APIClient.force_authenticate(user, token=claims)`
— see conftest.py for the claim shape and the rationale for not minting
a real JWT here. Cross-tenant isolation is exercised via a second
authenticated client (`authed_api_b`) targeting tenant A resources.

All tests wrap in `pytest.mark.django_db(transaction=True)` because the
ViewSets use `@transaction.atomic` and the cache_invalidation receivers
run through `transaction.on_commit`.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from app_modules.signals.constants import SignalSource, SignalStatus
from app_modules.signals.models import BlockerSignal


pytestmark = pytest.mark.django_db(transaction=True)


# =============================================================================
# URL HELPERS
# =============================================================================

def _url_list():
    return reverse('module_signals:blocker-list')


def _url_detail(pk):
    return reverse('module_signals:blocker-detail', kwargs={'pk': pk})


def _url_validate(pk):
    return reverse('module_signals:blocker-validate', kwargs={'pk': pk})


def _url_reject(pk):
    return reverse('module_signals:blocker-reject', kwargs={'pk': pk})


# =============================================================================
# CREATE
# =============================================================================

class TestCreateBlockerAPI:
    """POST /module-signals/blockers/ — create-time business rules."""

    def test_create_manual_blocker_forces_validated_status(
        self, authed_api_a, account, activity, contact,
    ):
        payload = {
            'account': str(account.id),
            'source_activity': str(activity.id),
            'summary': 'Budget non confirmé pour Q3',
            'source': SignalSource.MANUAL,
            'contact': str(contact.id),
        }
        response = authed_api_a.post(_url_list(), payload, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body['success'] is True
        data = body['data']
        assert data['status'] == SignalStatus.VALIDATED
        assert data['canonical_key'] is None
        # Shadow override: signal_category never serialized for BlockerSignal.
        assert 'signal_category' not in data
        assert 'signal_category_display' not in data
        # Compact contact payload is exposed top-level (not via source_context).
        assert data['contact'] is not None
        assert data['contact']['id'] == str(contact.id)
        assert data['contact']['first_name'] == contact.first_name
        # source_context.activity is wired up via SignalSourceSerializer.
        assert data['source_context']['activity']['id'] == str(activity.id)

    def test_create_llm_blocker_forces_pending_status(
        self, authed_api_a, account, activity,
    ):
        payload = {
            'account': str(account.id),
            'source_activity': str(activity.id),
            'summary': 'Décideur final pas identifié',
            'source': SignalSource.LLM_EXTRACTED,
            'confidence': 0.85,
        }
        response = authed_api_a.post(_url_list(), payload, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()['data']
        assert data['status'] == SignalStatus.PENDING
        assert data['confidence'] == 0.85

    def test_create_llm_blocker_ignores_client_supplied_status(
        self, authed_api_a, account, activity,
    ):
        """
        The Create serializer does not expose `status` as a writable field,
        so an LLM payload that smuggles `status=VALIDATED` is silently
        ignored: the signal is created with the model's default PENDING.
        Defence-in-depth model rule (BaseSignal.save rule 2) covers the
        direct-ORM path — exercised in test_blocker_model.py.
        """
        payload = {
            'account': str(account.id),
            'source_activity': str(activity.id),
            'summary': 'smuggled validate attempt',
            'source': SignalSource.LLM_EXTRACTED,
            'status': SignalStatus.VALIDATED,  # ignored by the serializer
        }
        response = authed_api_a.post(_url_list(), payload, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()['data']
        assert data['status'] == SignalStatus.PENDING

    def test_create_blocker_without_source_activity_returns_400(
        self, authed_api_a, account,
    ):
        payload = {
            'account': str(account.id),
            'summary': 'orphan blocker',
            'source': SignalSource.MANUAL,
        }
        response = authed_api_a.post(_url_list(), payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        body_text = response.content.decode().lower()
        assert 'source activity' in body_text or 'source_activity' in body_text

    def test_create_blocker_without_summary_returns_400(
        self, authed_api_a, account, activity,
    ):
        payload = {
            'account': str(account.id),
            'source_activity': str(activity.id),
            'summary': '',
            'source': SignalSource.MANUAL,
        }
        response = authed_api_a.post(_url_list(), payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# =============================================================================
# LIST / RETRIEVE
# =============================================================================

class TestListRetrieveBlockerAPI:
    """GET / GET-detail — filtering, structure, scoping."""

    def test_list_blockers_filtered_by_source_activity(
        self, authed_api_a, account, activity, user_a,
    ):
        # Seed two blockers on the activity + one on a different activity.
        b1 = BlockerSignal(
            account=account, source_activity=activity,
            summary='b1', source=SignalSource.MANUAL,
        )
        b1.save(user=user_a, client_id=account.client_id)

        b2 = BlockerSignal(
            account=account, source_activity=activity,
            summary='b2', source=SignalSource.MANUAL,
        )
        b2.save(user=user_a, client_id=account.client_id)

        # Decoy: another activity on the same tenant — must NOT appear.
        from app_modules.activities.models import Activity
        from app_modules.activities.constants import ActivityType, ActivityStatus
        other_activity = Activity(
            title='Other call',
            activity_type=ActivityType.MEETING,
            status=ActivityStatus.COMPLETED,
            account=account,
            owner=user_a,
        )
        other_activity.save(user=user_a, client_id=account.client_id)
        b3 = BlockerSignal(
            account=account, source_activity=other_activity,
            summary='b3-decoy', source=SignalSource.MANUAL,
        )
        b3.save(user=user_a, client_id=account.client_id)

        response = authed_api_a.get(
            _url_list(),
            {'source_activity': str(activity.id)},
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        # DRF returns either a paginated dict or a list — handle both.
        results = body.get('results') or body.get('data', {}).get('results') or body
        if isinstance(results, dict):
            results = results.get('results', results)
        ids = {row['id'] for row in results}
        assert str(b1.id) in ids
        assert str(b2.id) in ids
        assert str(b3.id) not in ids

        for row in results:
            assert 'signal_category' not in row
            assert row['canonical_key'] is None

    def test_retrieve_blocker_returns_full_detail(
        self, authed_api_a, account, activity, contact, user_a,
    ):
        b = BlockerSignal(
            account=account, source_activity=activity,
            summary='detail check', source=SignalSource.MANUAL,
            contact=contact,
        )
        b.save(user=user_a, client_id=account.client_id)

        response = authed_api_a.get(_url_detail(b.id))
        assert response.status_code == status.HTTP_200_OK
        # GET retrieve returns the serializer payload directly (no
        # {success, data} wrapper — only state-changing actions wrap).
        data = response.json()
        assert data['id'] == str(b.id)
        assert data['summary'] == 'detail check'
        assert data['status'] == SignalStatus.VALIDATED
        # Detail-only fields surface here (Detail extends List).
        assert 'validated_at' in data
        assert 'metadata' in data
        assert 'original_value' in data
        assert data['contact']['id'] == str(contact.id)


# =============================================================================
# VALIDATE / REJECT
# =============================================================================

class TestValidateRejectBlockerAPI:
    """Custom @actions — validate / reject lifecycle transitions."""

    def test_validate_pending_blocker_sets_validated_state(
        self, authed_api_a, account, activity, user_a,
    ):
        pending = BlockerSignal(
            account=account, source_activity=activity,
            summary='to validate', source=SignalSource.LLM_EXTRACTED,
            confidence=0.7,
        )
        pending.save(user=user_a, client_id=account.client_id)
        assert pending.status == SignalStatus.PENDING

        response = authed_api_a.post(_url_validate(pending.id), {}, format='json')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()['data']
        assert data['status'] == SignalStatus.VALIDATED
        assert data['validated_by'] is not None
        assert data['validated_by']['id'] == str(user_a.id)
        assert data['validated_at'] is not None

    def test_validate_already_validated_blocker_returns_400(
        self, authed_api_a, account, activity, user_a,
    ):
        validated = BlockerSignal(
            account=account, source_activity=activity,
            summary='already validated', source=SignalSource.MANUAL,
        )
        validated.save(user=user_a, client_id=account.client_id)
        assert validated.status == SignalStatus.VALIDATED

        response = authed_api_a.post(_url_validate(validated.id), {}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'pending' in response.content.decode().lower()

    def test_reject_blocker_with_reason_records_metadata(
        self, authed_api_a, account, activity, user_a,
    ):
        pending = BlockerSignal(
            account=account, source_activity=activity,
            summary='to reject', source=SignalSource.LLM_EXTRACTED,
        )
        pending.save(user=user_a, client_id=account.client_id)

        response = authed_api_a.post(
            _url_reject(pending.id),
            {'reason': 'doublon avec autre blocker'},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()['data']
        assert data['status'] == SignalStatus.REJECTED
        assert data['metadata']['rejection_reason'] == 'doublon avec autre blocker'
        assert 'rejected_at' in data['metadata']
        assert data['metadata']['rejected_by'] == str(user_a.id)


# =============================================================================
# PATCH
# =============================================================================

class TestPatchBlockerAPI:
    """PATCH /module-signals/blockers/{id}/ — restricted partial update."""

    def test_patch_summary_and_clear_contact(
        self, authed_api_a, account, activity, contact, user_a,
    ):
        b = BlockerSignal(
            account=account, source_activity=activity,
            summary='original summary', source=SignalSource.MANUAL,
            contact=contact,
        )
        b.save(user=user_a, client_id=account.client_id)

        response = authed_api_a.patch(
            _url_detail(b.id),
            {'summary': 'revised summary — relance Q2', 'contact': None},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()['data']
        assert data['summary'] == 'revised summary — relance Q2'
        assert data['contact'] is None


# =============================================================================
# MULTI-TENANT ISOLATION
# =============================================================================

class TestBlockerAPIMultiTenant:
    """Cross-tenant access must be rejected by the ScopedQuerysetMixin filter."""

    def test_retrieve_cross_tenant_returns_404(
        self, authed_api_b, account, activity, user_a,
    ):
        # Resource lives in tenant A …
        b = BlockerSignal(
            account=account, source_activity=activity,
            summary='tenant-A only', source=SignalSource.MANUAL,
        )
        b.save(user=user_a, client_id=account.client_id)

        # …but caller is authenticated as tenant B.
        response = authed_api_b.get(_url_detail(b.id))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_validate_cross_tenant_returns_404(
        self, authed_api_b, account, activity, user_a,
    ):
        pending = BlockerSignal(
            account=account, source_activity=activity,
            summary='cross-tenant validate', source=SignalSource.LLM_EXTRACTED,
        )
        pending.save(user=user_a, client_id=account.client_id)

        response = authed_api_b.post(_url_validate(pending.id), {}, format='json')
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_cross_tenant_returns_empty_results(
        self, authed_api_b, account, activity, user_a,
    ):
        b = BlockerSignal(
            account=account, source_activity=activity,
            summary='tenant-A only', source=SignalSource.MANUAL,
        )
        b.save(user=user_a, client_id=account.client_id)

        response = authed_api_b.get(
            _url_list(),
            {'source_activity': str(activity.id)},
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        results = body.get('results') or body.get('data', {}).get('results') or body
        if isinstance(results, dict):
            results = results.get('results', results)
        ids = {row['id'] for row in results}
        assert str(b.id) not in ids
