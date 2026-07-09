# backend/tests/signals/test_techstack_pending_catalog_link.py
"""
API-level coverage for catalog linking on a PENDING TechStack signal.

Product rule: tech_catalog_entry is settable while the signal is
PENDING (so an LLM-extracted signal with no catalog match can be linked
before validation), but immutable once VALIDATED.

Endpoints under test:
  PATCH /module-signals/tech-stack/{id}/           (partial_update)
  POST  /module-signals/tech-stack/{id}/validate/  (validate)

Cases:
  A. PENDING + null catalog → PATCH tech_catalog_entry → 200, FK set
  B. VALIDATED → PATCH tech_catalog_entry (repoint) → 400 LOCKED
  C. PENDING null catalog → validate → 400 (catalog required)
  D. PENDING → attach catalog (PATCH) → validate → 200 VALIDATED
"""

import pytest
from django.urls import reverse
from rest_framework import status

from app_modules.signals.constants import SignalSource, SignalStatus
from app_modules.signals.models import TechStackSignal


pytestmark = pytest.mark.django_db(transaction=True)


# =============================================================================
# URL + FIXTURE HELPERS
# =============================================================================

def _url_detail(pk):
    return reverse('module_signals:tech-stack-detail', kwargs={'pk': pk})


def _url_validate(pk):
    return reverse('module_signals:tech-stack-validate', kwargs={'pk': pk})


def _make_catalog_entry(client_id, user, *, company='Salesforce', product='Sales Cloud'):
    from app_modules.tech_catalog.models import TechCatalog
    entry = TechCatalog(company_name=company, product_name=product)
    entry.save(user=user, client_id=client_id)
    return entry


def _make_pending_unmatched(account, activity, user):
    """A PENDING LLM-extracted TechStack with no catalog match."""
    sig = TechStackSignal(
        account=account,
        source_activity=activity,
        tech_catalog_entry=None,
        source=SignalSource.LLM_EXTRACTED,
        metadata={'pending_tech_name': 'FooTool'},
    )
    sig.save(user=user, client_id=account.client_id)
    return sig


# =============================================================================
# A — PENDING accepts tech_catalog_entry
# =============================================================================

class TestPendingAcceptsCatalogEntry:

    def test_patch_catalog_on_pending_succeeds(
        self, authed_api_a, account, activity, user_a, client_account_a,
    ):
        sig = _make_pending_unmatched(account, activity, user_a)
        assert sig.status == SignalStatus.PENDING
        assert sig.tech_catalog_entry_id is None

        entry = _make_catalog_entry(client_account_a.id, user_a)

        response = authed_api_a.patch(
            _url_detail(sig.id),
            {'tech_catalog_entry': str(entry.id)},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK

        sig.refresh_from_db()
        assert sig.tech_catalog_entry_id == entry.id
        # Still PENDING — attaching the FK does not validate.
        assert sig.status == SignalStatus.PENDING


# =============================================================================
# B — VALIDATED rejects a repoint (LOCKED)
# =============================================================================

class TestValidatedCatalogLocked:

    def test_patch_catalog_on_validated_returns_400_locked(
        self, authed_api_a, account, activity, user_a, client_account_a,
    ):
        entry_a = _make_catalog_entry(client_account_a.id, user_a)
        entry_b = _make_catalog_entry(
            client_account_a.id, user_a,
            company='HubSpot', product='CRM',
        )

        # MANUAL source → forced VALIDATED at save.
        sig = TechStackSignal(
            account=account,
            source_activity=activity,
            tech_catalog_entry=entry_a,
            source=SignalSource.MANUAL,
        )
        sig.save(user=user_a, client_id=account.client_id)
        assert sig.status == SignalStatus.VALIDATED

        response = authed_api_a.patch(
            _url_detail(sig.id),
            {'tech_catalog_entry': str(entry_b.id)},
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'cannot be changed' in response.content.decode().lower()

        # Unchanged in the DB.
        sig.refresh_from_db()
        assert sig.tech_catalog_entry_id == entry_a.id

    def test_patch_same_catalog_on_validated_is_noop_allowed(
        self, authed_api_a, account, activity, user_a, client_account_a,
    ):
        # The edit form always re-emits tech_catalog_entry, even on an
        # unrelated notes edit. Re-sending the SAME entry must not trip
        # the lock on a VALIDATED signal.
        entry_a = _make_catalog_entry(client_account_a.id, user_a)
        sig = TechStackSignal(
            account=account,
            source_activity=activity,
            tech_catalog_entry=entry_a,
            source=SignalSource.MANUAL,
        )
        sig.save(user=user_a, client_id=account.client_id)
        assert sig.status == SignalStatus.VALIDATED

        response = authed_api_a.patch(
            _url_detail(sig.id),
            {'tech_catalog_entry': str(entry_a.id), 'notes': 'edited note'},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK

        sig.refresh_from_db()
        assert sig.tech_catalog_entry_id == entry_a.id
        assert sig.notes == 'edited note'


# =============================================================================
# REGRESSION — validated edit that does NOT touch the catalog anchor
# =============================================================================
# The edit form emits tech_catalog_entry as a UUID and OMITS it entirely
# when unchanged (mirror of the backend lock-on-change). These tests pin
# the real payload shape: a scope/notes edit of a validated signal omits
# the FK and must return 200. Before the frontend fix the form re-emitted
# the compact catalog OBJECT, which the writable FK rejected as an invalid
# UUID (400) — regression guard below.


class TestValidatedNonCatalogEdit:

    def _make_validated(self, account, activity, user, client_id):
        entry = _make_catalog_entry(client_id, user)
        sig = TechStackSignal(
            account=account,
            source_activity=activity,
            tech_catalog_entry=entry,
            source=SignalSource.MANUAL,
        )
        sig.save(user=user, client_id=account.client_id)
        assert sig.status == SignalStatus.VALIDATED
        return sig, entry

    def test_scope_edit_omitting_catalog_returns_200(
        self, authed_api_a, account, activity, user_a, client_account_a,
    ):
        # This is the payload the fixed form sends for a scope-only edit
        # of a validated signal: tech_catalog_entry is omitted entirely.
        sig, entry = self._make_validated(
            account, activity, user_a, client_account_a.id,
        )

        response = authed_api_a.patch(
            _url_detail(sig.id),
            {'usage_scope': 'COMPANY'},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK

        sig.refresh_from_db()
        assert sig.usage_scope == 'COMPANY'
        # Anchor untouched.
        assert sig.tech_catalog_entry_id == entry.id

    def test_notes_edit_omitting_catalog_returns_200(
        self, authed_api_a, account, activity, user_a, client_account_a,
    ):
        sig, entry = self._make_validated(
            account, activity, user_a, client_account_a.id,
        )

        response = authed_api_a.patch(
            _url_detail(sig.id),
            {'notes': 'just a note'},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK

        sig.refresh_from_db()
        assert sig.notes == 'just a note'
        assert sig.tech_catalog_entry_id == entry.id

    def test_catalog_sent_as_object_is_rejected(
        self, authed_api_a, account, activity, user_a, client_account_a,
    ):
        # Contract guard: the backend FK expects a UUID and must NOT be
        # loosened to swallow the compact catalog object. Sending the
        # object (the pre-fix frontend shape) is a 400.
        sig, entry = self._make_validated(
            account, activity, user_a, client_account_a.id,
        )

        response = authed_api_a.patch(
            _url_detail(sig.id),
            {
                'tech_catalog_entry': {
                    'id': str(entry.id),
                    'company_name': entry.company_name,
                    'product_name': entry.product_name,
                },
            },
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        sig.refresh_from_db()
        assert sig.tech_catalog_entry_id == entry.id


# =============================================================================
# C / D — validate() flow against the catalog anchor
# =============================================================================

class TestValidateFlow:

    def test_validate_pending_without_catalog_returns_400(
        self, authed_api_a, account, activity, user_a,
    ):
        sig = _make_pending_unmatched(account, activity, user_a)

        response = authed_api_a.post(_url_validate(sig.id), {}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        sig.refresh_from_db()
        assert sig.status == SignalStatus.PENDING

    def test_attach_then_validate_succeeds(
        self, authed_api_a, account, activity, user_a, client_account_a,
    ):
        sig = _make_pending_unmatched(account, activity, user_a)
        entry = _make_catalog_entry(client_account_a.id, user_a)

        patch_resp = authed_api_a.patch(
            _url_detail(sig.id),
            {'tech_catalog_entry': str(entry.id)},
            format='json',
        )
        assert patch_resp.status_code == status.HTTP_200_OK

        validate_resp = authed_api_a.post(
            _url_validate(sig.id), {}, format='json',
        )
        assert validate_resp.status_code == status.HTTP_200_OK

        sig.refresh_from_db()
        assert sig.status == SignalStatus.VALIDATED
        assert sig.tech_catalog_entry_id == entry.id


# =============================================================================
# DETECTED ACTION — GET /tech-stack/detected/
# =============================================================================

def _url_detected():
    return reverse('module_signals:tech-stack-detected')


def _extract_items(response):
    """Return the list of serialized signals regardless of pagination shape."""
    body = response.json()
    if isinstance(body, dict):
        if 'results' in body:
            return body['results']
        if 'data' in body:
            return body['data']
    return body


class TestDetectedAction:

    def test_detected_returns_only_pending_unmatched(
        self, authed_api_a, account, activity, user_a, client_account_a,
    ):
        # (1) PENDING, unmatched → should appear
        unmatched = _make_pending_unmatched(account, activity, user_a)

        # (2) PENDING, matched (has catalog entry) → should NOT appear
        entry = _make_catalog_entry(client_account_a.id, user_a)
        matched = TechStackSignal(
            account=account,
            source_activity=activity,
            tech_catalog_entry=entry,
            source=SignalSource.LLM_EXTRACTED,
        )
        matched.save(user=user_a, client_id=account.client_id)

        # (3) VALIDATED (MANUAL, with entry) → should NOT appear
        validated = TechStackSignal(
            account=account,
            source_activity=activity,
            tech_catalog_entry=_make_catalog_entry(
                client_account_a.id, user_a, company='Notion', product='Notion',
            ),
            source=SignalSource.MANUAL,
        )
        validated.save(user=user_a, client_id=account.client_id)

        response = authed_api_a.get(_url_detected())
        assert response.status_code == status.HTTP_200_OK

        ids = {item['id'] for item in _extract_items(response)}
        assert str(unmatched.id) in ids
        assert str(matched.id) not in ids
        assert str(validated.id) not in ids

    def test_detected_is_tenant_scoped(
        self, authed_api_b, account, activity, user_a,
    ):
        # A tenant-A unmatched signal must not surface for tenant B.
        _make_pending_unmatched(account, activity, user_a)

        response = authed_api_b.get(_url_detected())
        assert response.status_code == status.HTTP_200_OK
        assert _extract_items(response) == []
