# backend/tests/signals/test_nextstep_api.py
"""
API-level coverage for NextStepSignal endpoints (Sprint B2).

Endpoints under test (mounted via app_modules.signals.urls):
  GET    /module-signals/next-steps/
  POST   /module-signals/next-steps/
  GET    /module-signals/next-steps/{id}/
  PATCH  /module-signals/next-steps/{id}/
  POST   /module-signals/next-steps/{id}/validate/
  POST   /module-signals/next-steps/{id}/reject/

Auth is plugged in via `APIClient.force_authenticate(user, token=claims)`
— see conftest.py for the claim shape and the rationale for not minting
a real JWT here. Cross-tenant isolation is exercised via a second
authenticated client (`authed_api_b`) targeting tenant A resources.

All tests wrap in `pytest.mark.django_db(transaction=True)` because the
ViewSets use `@transaction.atomic` and the cache_invalidation receivers
run through `transaction.on_commit`.
"""

import datetime

import pytest
from django.urls import reverse
from rest_framework import status

from app_modules.activities.constants import ActivityType
from app_modules.signals.constants import SignalSource, SignalStatus
from app_modules.signals.models import NextStepSignal


pytestmark = pytest.mark.django_db(transaction=True)


# =============================================================================
# URL HELPERS
# =============================================================================

def _url_list():
    return reverse('module_signals:next-step-list')


def _url_detail(pk):
    return reverse('module_signals:next-step-detail', kwargs={'pk': pk})


def _url_validate(pk):
    return reverse('module_signals:next-step-validate', kwargs={'pk': pk})


def _url_reject(pk):
    return reverse('module_signals:next-step-reject', kwargs={'pk': pk})


# =============================================================================
# CREATE
# =============================================================================

class TestCreateNextStepAPI:
    """POST /module-signals/next-steps/ — create-time business rules."""

    def test_create_manual_next_step_forces_validated_status(
        self, authed_api_a, account, activity, contact, contact_extra,
    ):
        payload = {
            'account': str(account.id),
            'source_activity': str(activity.id),
            'suggested_title': 'Envoyer récap chiffré sous 48h',
            'suggested_activity_type': ActivityType.EMAIL,
            'suggested_due_date': '2026-12-15',
            'suggested_contacts': [str(contact.id), str(contact_extra.id)],
            'source': SignalSource.MANUAL,
        }
        response = authed_api_a.post(_url_list(), payload, format='json')

        assert response.status_code == status.HTTP_201_CREATED, response.content
        body = response.json()
        assert body['success'] is True
        data = body['data']
        assert data['status'] == SignalStatus.VALIDATED
        assert data['canonical_key'] is None
        # Shadow override: signal_category never serialized for NextStepSignal.
        assert 'signal_category' not in data
        assert 'signal_category_display' not in data
        # Structured payload echoed back.
        assert data['suggested_title'] == 'Envoyer récap chiffré sous 48h'
        assert data['suggested_activity_type'] == ActivityType.EMAIL
        assert data['suggested_activity_type_display'] == 'Email'
        assert data['suggested_due_date'] == '2026-12-15'
        # suggested_contacts compact payload, both attendees present.
        contact_ids = {c['id'] for c in data['suggested_contacts']}
        assert contact_ids == {str(contact.id), str(contact_extra.id)}
        # source_context.activity is wired up via SignalSourceSerializer.
        assert data['source_context']['activity']['id'] == str(activity.id)

    def test_create_llm_next_step_forces_pending_status(
        self, authed_api_a, account, activity,
    ):
        payload = {
            'account': str(account.id),
            'source_activity': str(activity.id),
            'suggested_title': 'Caler une démo technique',
            'suggested_activity_type': ActivityType.MEETING,
            'source': SignalSource.LLM_EXTRACTED,
            'confidence': 0.85,
            'source_quote': 'Le DSI a demandé une démo sous quinzaine',
        }
        response = authed_api_a.post(_url_list(), payload, format='json')

        assert response.status_code == status.HTTP_201_CREATED, response.content
        data = response.json()['data']
        assert data['status'] == SignalStatus.PENDING
        assert data['confidence'] == 0.85

    def test_create_llm_next_step_ignores_client_supplied_status(
        self, authed_api_a, account, activity,
    ):
        """
        The Create serializer does not expose `status` as a writable field,
        so an LLM payload that smuggles `status=VALIDATED` is silently
        ignored: the signal is created with the model's default PENDING.
        Defence-in-depth model rule (BaseSignal.save rule 2) covers the
        direct-ORM path — exercised in test_nextstep_model.py.
        """
        payload = {
            'account': str(account.id),
            'source_activity': str(activity.id),
            'suggested_title': 'smuggled validate attempt',
            'suggested_activity_type': ActivityType.CALL,
            'source': SignalSource.LLM_EXTRACTED,
            'status': SignalStatus.VALIDATED,  # ignored by the serializer
        }
        response = authed_api_a.post(_url_list(), payload, format='json')

        assert response.status_code == status.HTTP_201_CREATED, response.content
        data = response.json()['data']
        assert data['status'] == SignalStatus.PENDING

    def test_create_next_step_without_source_activity_returns_400(
        self, authed_api_a, account,
    ):
        payload = {
            'account': str(account.id),
            'suggested_title': 'orphan',
            'suggested_activity_type': ActivityType.TASK,
            'source': SignalSource.MANUAL,
        }
        response = authed_api_a.post(_url_list(), payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        body_text = response.content.decode().lower()
        assert 'source activity' in body_text or 'source_activity' in body_text

    def test_create_next_step_without_title_returns_400(
        self, authed_api_a, account, activity,
    ):
        payload = {
            'account': str(account.id),
            'source_activity': str(activity.id),
            'suggested_title': '',
            'suggested_activity_type': ActivityType.EMAIL,
            'source': SignalSource.MANUAL,
        }
        response = authed_api_a.post(_url_list(), payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_next_step_without_activity_type_returns_400(
        self, authed_api_a, account, activity,
    ):
        payload = {
            'account': str(account.id),
            'source_activity': str(activity.id),
            'suggested_title': 'missing type',
            'source': SignalSource.MANUAL,
        }
        response = authed_api_a.post(_url_list(), payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_next_step_with_invalid_activity_type_returns_400(
        self, authed_api_a, account, activity,
    ):
        payload = {
            'account': str(account.id),
            'source_activity': str(activity.id),
            'suggested_title': 'bad type',
            'suggested_activity_type': 'NOT_A_TYPE',
            'source': SignalSource.MANUAL,
        }
        response = authed_api_a.post(_url_list(), payload, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_next_step_without_due_date_is_accepted(
        self, authed_api_a, account, activity,
    ):
        """suggested_due_date is nullable — omitting it must NOT raise."""
        payload = {
            'account': str(account.id),
            'source_activity': str(activity.id),
            'suggested_title': 'no deadline',
            'suggested_activity_type': ActivityType.TASK,
            'source': SignalSource.MANUAL,
        }
        response = authed_api_a.post(_url_list(), payload, format='json')
        assert response.status_code == status.HTTP_201_CREATED, response.content
        data = response.json()['data']
        assert data['suggested_due_date'] is None

    def test_create_next_step_without_contacts_returns_empty_list(
        self, authed_api_a, account, activity,
    ):
        payload = {
            'account': str(account.id),
            'source_activity': str(activity.id),
            'suggested_title': 'no attendees',
            'suggested_activity_type': ActivityType.TASK,
            'source': SignalSource.MANUAL,
        }
        response = authed_api_a.post(_url_list(), payload, format='json')
        assert response.status_code == status.HTTP_201_CREATED, response.content
        data = response.json()['data']
        assert data['suggested_contacts'] == []


# =============================================================================
# LIST / RETRIEVE
# =============================================================================

class TestListRetrieveNextStepAPI:
    """GET / GET-detail — filtering, structure, scoping."""

    def test_list_next_steps_filtered_by_source_activity(
        self, authed_api_a, account, activity, user_a,
    ):
        # Seed two next-steps on the activity + one on a different activity.
        n1 = NextStepSignal(
            account=account, source_activity=activity,
            suggested_title='n1', suggested_activity_type=ActivityType.EMAIL,
            source=SignalSource.MANUAL,
        )
        n1.save(user=user_a, client_id=account.client_id)

        n2 = NextStepSignal(
            account=account, source_activity=activity,
            suggested_title='n2', suggested_activity_type=ActivityType.CALL,
            source=SignalSource.MANUAL,
        )
        n2.save(user=user_a, client_id=account.client_id)

        # Decoy: another activity on the same tenant — must NOT appear.
        from app_modules.activities.models import Activity
        from app_modules.activities.constants import ActivityType as AT, ActivityStatus
        other_activity = Activity(
            title='Other call',
            activity_type=AT.MEETING,
            status=ActivityStatus.COMPLETED,
            account=account,
            owner=user_a,
        )
        other_activity.save(user=user_a, client_id=account.client_id)
        n3 = NextStepSignal(
            account=account, source_activity=other_activity,
            suggested_title='n3-decoy', suggested_activity_type=AT.EMAIL,
            source=SignalSource.MANUAL,
        )
        n3.save(user=user_a, client_id=account.client_id)

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
        assert str(n1.id) in ids
        assert str(n2.id) in ids
        assert str(n3.id) not in ids

        for row in results:
            assert 'signal_category' not in row
            assert row['canonical_key'] is None

    def test_retrieve_next_step_returns_full_detail(
        self, authed_api_a, account, activity, contact, contact_extra, user_a,
    ):
        ns = NextStepSignal(
            account=account, source_activity=activity,
            suggested_title='detail check',
            suggested_activity_type=ActivityType.MEETING,
            suggested_due_date=datetime.date(2027, 1, 10),
            source=SignalSource.MANUAL,
        )
        ns.save(user=user_a, client_id=account.client_id)
        ns.suggested_contacts.set([contact, contact_extra])

        response = authed_api_a.get(_url_detail(ns.id))
        assert response.status_code == status.HTTP_200_OK
        # GET retrieve returns the serializer payload directly (no
        # {success, data} wrapper — only state-changing actions wrap).
        data = response.json()
        assert data['id'] == str(ns.id)
        assert data['suggested_title'] == 'detail check'
        assert data['suggested_activity_type'] == ActivityType.MEETING
        assert data['suggested_due_date'] == '2027-01-10'
        assert data['status'] == SignalStatus.VALIDATED
        # Detail-only fields surface here (Detail extends List).
        assert 'validated_at' in data
        assert 'metadata' in data
        assert 'original_value' in data
        contact_ids = {c['id'] for c in data['suggested_contacts']}
        assert contact_ids == {str(contact.id), str(contact_extra.id)}


# =============================================================================
# VALIDATE / REJECT
# =============================================================================

class TestValidateRejectNextStepAPI:
    """Custom @actions — validate / reject lifecycle transitions."""

    def test_validate_pending_next_step_sets_validated_state(
        self, authed_api_a, account, activity, user_a,
    ):
        pending = NextStepSignal(
            account=account, source_activity=activity,
            suggested_title='to validate',
            suggested_activity_type=ActivityType.EMAIL,
            source=SignalSource.LLM_EXTRACTED,
            confidence=0.7,
        )
        pending.save(user=user_a, client_id=account.client_id)
        assert pending.status == SignalStatus.PENDING

        response = authed_api_a.post(_url_validate(pending.id), {}, format='json')
        assert response.status_code == status.HTTP_200_OK, response.content
        data = response.json()['data']
        assert data['status'] == SignalStatus.VALIDATED
        assert data['validated_by'] is not None
        assert data['validated_by']['id'] == str(user_a.id)
        assert data['validated_at'] is not None

    def test_validate_already_validated_next_step_returns_400(
        self, authed_api_a, account, activity, user_a,
    ):
        validated = NextStepSignal(
            account=account, source_activity=activity,
            suggested_title='already validated',
            suggested_activity_type=ActivityType.CALL,
            source=SignalSource.MANUAL,
        )
        validated.save(user=user_a, client_id=account.client_id)
        assert validated.status == SignalStatus.VALIDATED

        response = authed_api_a.post(_url_validate(validated.id), {}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'pending' in response.content.decode().lower()

    def test_reject_next_step_with_reason_records_metadata(
        self, authed_api_a, account, activity, user_a,
    ):
        pending = NextStepSignal(
            account=account, source_activity=activity,
            suggested_title='to reject',
            suggested_activity_type=ActivityType.EMAIL,
            source=SignalSource.LLM_EXTRACTED,
        )
        pending.save(user=user_a, client_id=account.client_id)

        response = authed_api_a.post(
            _url_reject(pending.id),
            {'reason': 'doublon avec autre next-step'},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK, response.content
        data = response.json()['data']
        assert data['status'] == SignalStatus.REJECTED
        assert data['metadata']['rejection_reason'] == 'doublon avec autre next-step'
        assert 'rejected_at' in data['metadata']
        assert data['metadata']['rejected_by'] == str(user_a.id)


# =============================================================================
# PATCH
# =============================================================================

class TestPatchNextStepAPI:
    """PATCH /module-signals/next-steps/{id}/ — restricted partial update."""

    def test_patch_title_and_type(
        self, authed_api_a, account, activity, user_a,
    ):
        ns = NextStepSignal(
            account=account, source_activity=activity,
            suggested_title='original title',
            suggested_activity_type=ActivityType.CALL,
            source=SignalSource.MANUAL,
        )
        ns.save(user=user_a, client_id=account.client_id)

        response = authed_api_a.patch(
            _url_detail(ns.id),
            {
                'suggested_title': 'refined title — set up Q2 demo',
                'suggested_activity_type': ActivityType.MEETING,
            },
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK, response.content
        data = response.json()['data']
        assert data['suggested_title'] == 'refined title — set up Q2 demo'
        assert data['suggested_activity_type'] == ActivityType.MEETING

    def test_patch_suggested_due_date_and_contacts(
        self, authed_api_a, account, activity, contact, contact_extra, user_a,
    ):
        ns = NextStepSignal(
            account=account, source_activity=activity,
            suggested_title='evolving',
            suggested_activity_type=ActivityType.EMAIL,
            source=SignalSource.MANUAL,
        )
        ns.save(user=user_a, client_id=account.client_id)
        ns.suggested_contacts.set([contact])

        response = authed_api_a.patch(
            _url_detail(ns.id),
            {
                'suggested_due_date': '2027-03-30',
                'suggested_contacts': [str(contact_extra.id)],
            },
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK, response.content
        data = response.json()['data']
        assert data['suggested_due_date'] == '2027-03-30'
        contact_ids = {c['id'] for c in data['suggested_contacts']}
        assert contact_ids == {str(contact_extra.id)}

    def test_patch_clear_due_date(
        self, authed_api_a, account, activity, user_a,
    ):
        ns = NextStepSignal(
            account=account, source_activity=activity,
            suggested_title='dated',
            suggested_activity_type=ActivityType.TASK,
            suggested_due_date=datetime.date(2026, 12, 1),
            source=SignalSource.MANUAL,
        )
        ns.save(user=user_a, client_id=account.client_id)

        response = authed_api_a.patch(
            _url_detail(ns.id),
            {'suggested_due_date': None},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK, response.content
        data = response.json()['data']
        assert data['suggested_due_date'] is None


# =============================================================================
# MULTI-TENANT ISOLATION
# =============================================================================

class TestNextStepAPIMultiTenant:
    """Cross-tenant access must be rejected by the ScopedQuerysetMixin filter."""

    def test_retrieve_cross_tenant_returns_404(
        self, authed_api_b, account, activity, user_a,
    ):
        # Resource lives in tenant A …
        ns = NextStepSignal(
            account=account, source_activity=activity,
            suggested_title='tenant-A only',
            suggested_activity_type=ActivityType.CALL,
            source=SignalSource.MANUAL,
        )
        ns.save(user=user_a, client_id=account.client_id)

        # …but caller is authenticated as tenant B.
        response = authed_api_b.get(_url_detail(ns.id))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_validate_cross_tenant_returns_404(
        self, authed_api_b, account, activity, user_a,
    ):
        pending = NextStepSignal(
            account=account, source_activity=activity,
            suggested_title='cross-tenant validate',
            suggested_activity_type=ActivityType.EMAIL,
            source=SignalSource.LLM_EXTRACTED,
        )
        pending.save(user=user_a, client_id=account.client_id)

        response = authed_api_b.post(_url_validate(pending.id), {}, format='json')
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_cross_tenant_returns_empty_results(
        self, authed_api_b, account, activity, user_a,
    ):
        ns = NextStepSignal(
            account=account, source_activity=activity,
            suggested_title='tenant-A only',
            suggested_activity_type=ActivityType.CALL,
            source=SignalSource.MANUAL,
        )
        ns.save(user=user_a, client_id=account.client_id)

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
        assert str(ns.id) not in ids
