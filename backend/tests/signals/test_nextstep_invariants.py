# backend/tests/signals/test_nextstep_invariants.py
"""
Sprint Next steps — bloc 2.1: the next step invariants, through the real
endpoints.

  a) A next step becomes VALIDATED only with an activity: created from it
     (Activity.next_step_signal, reverse created_activities) OR linked
     (attached_activity). Central point: SignalManager.validate, reached by
     POST .../next-steps/{id}/validate/ and by the conversion
     (services/next_step_materialization.py).
  b) A next step is never created MANUAL (PO: a next step typed by hand is
     an activity — "Set a next step manually"). Central point:
     NextStepSignal.save() at create time — the API (SignalManager.create)
     and any direct ORM save go through it.
  c) A RESOLVED next step (it has its activity) can be neither reopened nor
     edited: the activity is the reference.
  d) Never both a created AND a linked activity.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from app_modules.activities.constants import ActivityType
from app_modules.signals.constants import SignalSource, SignalStatus
from app_modules.signals.models import NextStepSignal
from core.error_messages import SignalErrorMessages


pytestmark = pytest.mark.django_db


def _url(name, pk=None):
    if pk is None:
        return reverse(f'module_signals:next-step-{name}')
    return reverse(f'module_signals:next-step-{name}', kwargs={'pk': pk})


def _error_text(response):
    error = response.json()['error']
    return ' '.join(error) if isinstance(error, list) else error


def _pending(account, activity, user, **fields):
    ns = NextStepSignal(
        account=account, source_activity=activity,
        suggested_title='Revue sécurité avec le DSI',
        suggested_activity_type=ActivityType.MEETING,
        source=SignalSource.LLM_EXTRACTED, confidence=0.8,
        **fields,
    )
    ns.save(user=user, client_id=account.client_id)
    return ns


def _activity(account, user, **fields):
    from app_modules.activities.models import Activity
    a = Activity(
        title='Security review', activity_type=ActivityType.MEETING,
        account=account, owner=user, **fields,
    )
    a.save(user=user, client_id=account.client_id)
    return a


def _convert(authed_api, account, contact, ns):
    """The real conversion path: POST /module-activities/ with the signal."""
    return authed_api.post('/module-activities/', {
        'title': 'Security review',
        'activity_type': 'MEETING',
        'account_id': str(account.id),
        'contact_ids': [str(contact.id)],
        'scheduled_date': '2026-11-03',
        'next_step_signal_id': str(ns.id),
    }, format='json')


# =============================================================================
# a) VALIDATED only with an activity
# =============================================================================

class TestValidateRequiresAnActivity:

    def test_validate_without_activity_is_refused(
        self, authed_api_a, account, activity, user_a,
    ):
        ns = _pending(account, activity, user_a)

        response = authed_api_a.post(_url('validate', ns.id), {}, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert _error_text(response) == str(SignalErrorMessages.NEXT_STEP_REQUIRES_ACTIVITY)
        ns.refresh_from_db()
        assert ns.status == SignalStatus.PENDING

    def test_validate_with_a_linked_activity_is_accepted(
        self, authed_api_a, account, activity, user_a,
    ):
        ns = _pending(account, activity, user_a,
                      attached_activity=_activity(account, user_a))

        response = authed_api_a.post(_url('validate', ns.id), {}, format='json')

        assert response.status_code == status.HTTP_200_OK, response.content
        ns.refresh_from_db()
        assert ns.status == SignalStatus.VALIDATED

    def test_validate_with_a_created_activity_is_accepted(
        self, authed_api_a, account, activity, user_a,
    ):
        ns = _pending(account, activity, user_a)
        _activity(account, user_a, next_step_signal=ns)

        response = authed_api_a.post(_url('validate', ns.id), {}, format='json')

        assert response.status_code == status.HTTP_200_OK, response.content
        ns.refresh_from_db()
        assert ns.status == SignalStatus.VALIDATED

    def test_conversion_still_validates(
        self, authed_api_a, account, activity, contact, user_a,
    ):
        ns = _pending(account, activity, user_a)

        response = _convert(authed_api_a, account, contact, ns)

        assert response.status_code == status.HTTP_201_CREATED, response.content
        ns.refresh_from_db()
        assert ns.status == SignalStatus.VALIDATED


# =============================================================================
# b) never created MANUAL
# =============================================================================

class TestManualCreationRefused:

    def _payload(self, account, activity, **extra):
        return {
            'account': str(account.id),
            'source_activity': str(activity.id),
            'suggested_title': 'Saisi à la main',
            'suggested_activity_type': ActivityType.EMAIL,
            **extra,
        }

    def test_api_manual_creation_is_refused(self, authed_api_a, account, activity):
        response = authed_api_a.post(
            _url('list'), self._payload(account, activity, source=SignalSource.MANUAL),
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert _error_text(response) == str(SignalErrorMessages.NEXT_STEP_MANUAL_NOT_ALLOWED)
        assert not NextStepSignal.objects.filter(source_activity=activity).exists()

    def test_api_creation_without_source_is_refused(self, authed_api_a, account, activity):
        """The model default source is MANUAL — omitting it is the same."""
        response = authed_api_a.post(
            _url('list'), self._payload(account, activity), format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not NextStepSignal.objects.filter(source_activity=activity).exists()

    def test_api_llm_creation_still_accepted(self, authed_api_a, account, activity):
        response = authed_api_a.post(
            _url('list'),
            self._payload(account, activity, source=SignalSource.LLM_EXTRACTED),
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED, response.content
        assert response.json()['data']['status'] == SignalStatus.PENDING

    def test_signal_manager_and_orm_manual_creation_are_refused(
        self, account, activity, user_a,
    ):
        from app_modules.signals.services import SignalManager
        from core.exceptions import StandardizedValidationError

        with pytest.raises(StandardizedValidationError):
            SignalManager.create(
                data={
                    'signal_type': 'next_step', 'account': account,
                    'source_activity': activity, 'suggested_title': 'x',
                    'suggested_activity_type': ActivityType.EMAIL,
                    'source': SignalSource.MANUAL,
                },
                user=user_a, client_id=account.client_id,
            )
        with pytest.raises(StandardizedValidationError):
            NextStepSignal(
                account=account, source_activity=activity,
                suggested_title='x', suggested_activity_type=ActivityType.EMAIL,
                source=SignalSource.MANUAL,
            ).save(user=user_a, client_id=account.client_id)
        assert not NextStepSignal.objects.filter(source_activity=activity).exists()


# =============================================================================
# c) a resolved next step: no reopen, no edit
# =============================================================================

class TestResolvedNextStepIsFrozen:

    def test_reopen_of_a_converted_next_step_is_refused(
        self, authed_api_a, account, activity, contact, user_a,
    ):
        ns = _pending(account, activity, user_a)
        assert _convert(authed_api_a, account, contact, ns).status_code == 201

        response = authed_api_a.post(_url('reopen', ns.id), {}, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert _error_text(response) == str(SignalErrorMessages.NEXT_STEP_RESOLVED)
        ns.refresh_from_db()
        assert ns.status == SignalStatus.VALIDATED

    def test_reopen_of_a_linked_next_step_is_refused(
        self, authed_api_a, account, activity, user_a,
    ):
        ns = _pending(account, activity, user_a,
                      attached_activity=_activity(account, user_a))
        assert authed_api_a.post(_url('validate', ns.id), {}, format='json').status_code == 200

        response = authed_api_a.post(_url('reopen', ns.id), {}, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert _error_text(response) == str(SignalErrorMessages.NEXT_STEP_RESOLVED)

    def test_reopen_of_a_rejected_unresolved_next_step_still_works(
        self, authed_api_a, account, activity, user_a,
    ):
        ns = _pending(account, activity, user_a)
        assert authed_api_a.post(_url('reject', ns.id), {}, format='json').status_code == 200

        response = authed_api_a.post(_url('reopen', ns.id), {}, format='json')

        assert response.status_code == status.HTTP_200_OK, response.content
        ns.refresh_from_db()
        assert ns.status == SignalStatus.PENDING

    def test_patch_of_a_resolved_next_step_is_refused(
        self, authed_api_a, account, activity, contact, user_a,
    ):
        ns = _pending(account, activity, user_a)
        assert _convert(authed_api_a, account, contact, ns).status_code == 201

        response = authed_api_a.patch(
            _url('detail', ns.id), {'suggested_title': 'changed after'},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert _error_text(response) == str(SignalErrorMessages.NEXT_STEP_RESOLVED)
        ns.refresh_from_db()
        assert ns.suggested_title == 'Revue sécurité avec le DSI'

    def test_patch_of_an_unresolved_next_step_still_works(
        self, authed_api_a, account, activity, user_a,
    ):
        ns = _pending(account, activity, user_a)

        response = authed_api_a.patch(
            _url('detail', ns.id), {'suggested_title': 'refined'}, format='json',
        )

        assert response.status_code == status.HTTP_200_OK, response.content


# =============================================================================
# d) never both a created and a linked activity
# =============================================================================

class TestCreatedAndLinkedAreExclusive:

    def test_converting_a_linked_next_step_is_refused(
        self, authed_api_a, account, activity, contact, user_a,
    ):
        from app_modules.activities.models import Activity
        ns = _pending(account, activity, user_a,
                      attached_activity=_activity(account, user_a))
        before = Activity.objects.filter(client_id=account.client_id).count()

        response = _convert(authed_api_a, account, contact, ns)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert _error_text(response) == str(SignalErrorMessages.NEXT_STEP_CREATED_AND_LINKED)
        assert Activity.objects.filter(client_id=account.client_id).count() == before
        ns.refresh_from_db()
        assert ns.status == SignalStatus.PENDING

    def test_validating_a_next_step_both_created_and_linked_is_refused(
        self, authed_api_a, account, activity, user_a,
    ):
        ns = _pending(account, activity, user_a,
                      attached_activity=_activity(account, user_a))
        _activity(account, user_a, next_step_signal=ns)

        response = authed_api_a.post(_url('validate', ns.id), {}, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert _error_text(response) == str(SignalErrorMessages.NEXT_STEP_CREATED_AND_LINKED)
        ns.refresh_from_db()
        assert ns.status == SignalStatus.PENDING
