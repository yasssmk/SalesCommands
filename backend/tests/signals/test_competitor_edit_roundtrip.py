# backend/tests/signals/test_competitor_edit_roundtrip.py
"""
Sprint Competitor C2 — the Activity Competitor edit drawer round-trip.

The drawer (EditCompetitorContent) is opened with the /module-signals/all/
row and PATCHes exactly {competitor_name, summary, source_quote}. This test
builds the payload as the form does from that row, applies a rep's edits,
PATCHes the real route and reads the row back from the database.

Characterisation of the backend contract the drawer relies on (no backend
change in C2): the LIST row carries the three edited fields, the PATCH
persists them, the normalised name follows the new name, and the fields the
drawer never sends (status, source, account, source_activity) are untouched.
Model: test_techstack_edit_roundtrip.py (Sprint TechStack T2b).
"""

import pytest
from django.urls import reverse
from rest_framework import status

from app_modules.signals.constants import SignalSource, SignalStatus
from app_modules.signals.models import CompetitorSignal


pytestmark = pytest.mark.django_db(transaction=True)


def _competitor(account, activity, user):
    sig = CompetitorSignal(
        account=account, source_activity=activity,
        source=SignalSource.LLM_EXTRACTED, competitor_name='Inter com',
        summary='The prospect is also evaluating Intercom instead of us.',
        source_quote="We're also looking at Intercom.",
    )
    sig.save(user=user, client_id=account.client_id)
    return sig


def _all_row(api, activity, signal):
    response = api.get(
        reverse('module_signals:signal-all'), {'activity_id': str(activity.id)},
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    rows = body.get('results', body)
    return next(r for r in rows if r['id'] == str(signal.id))


def _form_payload(row, **edits):
    """
    Mirror of EditCompetitorContent: initial values read from the LIST row,
    the rep's edits applied, then the submit mapping (name and summary
    trimmed, quote as is).
    """
    values = {
        'competitor_name': row['competitor_name'] or '',
        'summary': row['summary'] or '',
        'source_quote': row['source_quote'] or '',
    }
    values.update(edits)
    return {
        'competitor_name': values['competitor_name'].strip(),
        'summary': values['summary'].strip(),
        'source_quote': values['source_quote'] or '',
    }


def _patch(api, signal, payload):
    return api.patch(
        reverse('module_signals:competitor-detail', kwargs={'pk': signal.id}),
        payload, format='json',
    )


class TestCompetitorEditRoundTrip:

    def test_the_list_row_carries_the_three_edited_fields(
        self, authed_api_a, account, activity, user_a,
    ):
        sig = _competitor(account, activity, user_a)
        row = _all_row(authed_api_a, activity, sig)
        assert row['competitor_name'] == 'Inter com'
        assert row['summary'] == sig.summary
        assert row['source_quote'] == sig.source_quote

    def test_edits_built_from_the_row_are_persisted(
        self, authed_api_a, account, activity, user_a,
    ):
        sig = _competitor(account, activity, user_a)
        row = _all_row(authed_api_a, activity, sig)

        payload = _form_payload(
            row,
            competitor_name='  Intercom ',
            summary='Intercom is the other option on the table.',
            source_quote='The other option is Intercom.',
        )
        response = _patch(authed_api_a, sig, payload)

        assert response.status_code == status.HTTP_200_OK, response.content
        sig.refresh_from_db()
        assert sig.competitor_name == 'Intercom'
        assert sig.competitor_name_normalized == 'intercom'
        assert sig.summary == 'Intercom is the other option on the table.'
        assert sig.source_quote == 'The other option is Intercom.'

    def test_an_unchanged_form_keeps_every_field(
        self, authed_api_a, account, activity, user_a,
    ):
        sig = _competitor(account, activity, user_a)
        row = _all_row(authed_api_a, activity, sig)

        response = _patch(authed_api_a, sig, _form_payload(row))

        assert response.status_code == status.HTTP_200_OK, response.content
        sig.refresh_from_db()
        assert sig.competitor_name == 'Inter com'
        assert sig.summary == 'The prospect is also evaluating Intercom instead of us.'
        assert sig.source_quote == "We're also looking at Intercom."

    def test_fields_the_drawer_never_sends_are_untouched(
        self, authed_api_a, account, activity, user_a,
    ):
        sig = _competitor(account, activity, user_a)
        row = _all_row(authed_api_a, activity, sig)

        _patch(authed_api_a, sig, _form_payload(row, competitor_name='HubSpot'))

        sig.refresh_from_db()
        assert sig.status == SignalStatus.PENDING
        # The drawer never sends `source`: the server marks an edited LLM
        # signal LLM_MODIFIED (SignalManager.edit, signal_manager.py:486).
        assert sig.source == SignalSource.LLM_MODIFIED
        assert sig.account_id == account.id
        assert sig.source_activity_id == activity.id

    def test_an_emptied_quote_is_persisted_empty(
        self, authed_api_a, account, activity, user_a,
    ):
        sig = _competitor(account, activity, user_a)
        row = _all_row(authed_api_a, activity, sig)

        response = _patch(authed_api_a, sig, _form_payload(row, source_quote=''))

        assert response.status_code == status.HTTP_200_OK, response.content
        sig.refresh_from_db()
        assert sig.source_quote == ''
