# backend/tests/signals/test_signals_tenant_isolation.py
"""
Tenant isolation of the signals module — WRITE path (FK ownership) and the
CLUSTER read/archive path (S1 repros, fix/signals-tenant-scope).

Locked contract:
  * FK pointing to ANOTHER TENANT (incl. a cluster's `account`)
      → 400 + CoreErrorMessages.OBJECT_NOT_FOUND, nothing written.
  * FK of the SAME tenant but ANOTHER ACCOUNT than the signal's account
      → 400 + ContactErrorMessages.INVALID_ACCOUNT, nothing written.
  * Errors go through StandardizedValidationError → custom_exception_handler.

Pattern: TestBlockerAPIMultiTenant (test_blocker_api.py) — real API path,
`authed_api_a` / `authed_api_b` from conftest.py. Every negative test asserts
the HTTP code, the contract message AND the DB state (nothing created /
value unchanged). Positive controls (C1–C3) guard against over-blocking.

NOTE: `authed_api_a` and `authed_api_b` share the SAME `api` instance
(conftest.py `api` / `authed_api_a` / `authed_api_b`). A test that needs to
switch tenant mid-way re-authenticates through the existing `authenticate`
helper fixture.

Payload provenance (existing passing API tests):
  * Blocker   — test_blocker_api.py::test_create_manual_blocker_forces_validated_status
  * People    — test_people_signal_api.py::test_create_manual_people_signal and
                ::test_create_manual_dc_level_without_source_activity
  * NextStep  — test_nextstep_api.py::test_create_manual_next_step_forces_validated_status
  * Objective — no API create test exists; payload built from
                ObjectiveSignalCreateSerializer.Meta (objective_serializer.py)
                with the PERSONAL scope rule, axes cloned from
                test_pain_impact_departments_m2m.py::_mk_objective.
Cluster members: `_pain` cloned from test_cluster_member_filters.py::_pain.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from app_modules.activities.constants import ActivityType
from app_modules.signals.constants import (
    InfluenceLevel,
    PeopleRole,
    ScopeLevel,
    SignalDimension,
    SignalSource,
    SignalStatus,
    SignalWhat,
)
from app_modules.signals.models import (
    BlockerSignal,
    NextStepSignal,
    ObjectiveSignal,
    PainSignal,
    PeopleSignal,
)
from core.error_messages import ContactErrorMessages, CoreErrorMessages

pytestmark = pytest.mark.django_db(transaction=True)


OBJECT_NOT_FOUND = str(CoreErrorMessages.OBJECT_NOT_FOUND)
INVALID_ACCOUNT = str(ContactErrorMessages.INVALID_ACCOUNT)


# =============================================================================
# HELPERS
# =============================================================================

def _assert_400(response, message):
    """400 + the exact contract message somewhere in the standardized body."""
    assert response.status_code == status.HTTP_400_BAD_REQUEST, (
        response.status_code, response.content,
    )
    assert message in response.content.decode(), response.content


def _blocker_payload(account, activity, **overrides):
    payload = {
        'account': str(account.id),
        'source_activity': str(activity.id),
        'summary': 'Budget non confirmé pour Q3',
        'source': SignalSource.MANUAL,
    }
    payload.update(overrides)
    return payload


def _mk_blocker(account, activity, user, contact=None):
    b = BlockerSignal(
        account=account, source_activity=activity,
        summary='original summary', source=SignalSource.MANUAL,
        contact=contact,
    )
    b.save(user=user, client_id=account.client_id)
    return b


def _objective_payload(account, activity, target_contact):
    return {
        'account': str(account.id),
        'source_activity': str(activity.id),
        'what': SignalWhat.GROWTH,
        'dimension': SignalDimension.TIME,
        'scope_level': ScopeLevel.PERSONAL,
        'summary': 'Grow the pipeline',
        'source': SignalSource.MANUAL,
        'target_contact': str(target_contact.id),
    }


def _mk_objective(account, activity, user, target_contact):
    o = ObjectiveSignal(
        account=account, source_activity=activity,
        what=SignalWhat.GROWTH, dimension=SignalDimension.TIME,
        scope_level=ScopeLevel.PERSONAL, summary='Grow', source_quote='q',
        source=SignalSource.MANUAL, target_contact=target_contact,
    )
    o.save(user=user, client_id=account.client_id)
    return o


def _people_payload(account, activity, target_contact):
    return {
        'signal_type': 'people',
        'source': 'MANUAL',
        'account': str(account.id),
        'source_activity': str(activity.id),
        'role': PeopleRole.CHAMPION,
        'influence': InfluenceLevel.HIGH,
        'target_contact': str(target_contact.id),
        'notes': 'Key champion identified during discovery',
    }


def _mk_people(account, activity, user, target_contact):
    p = PeopleSignal(
        account=account, source_activity=activity,
        role=PeopleRole.CHAMPION, target_contact=target_contact,
        source=SignalSource.MANUAL,
    )
    p.save(user=user, client_id=account.client_id)
    return p


def _nextstep_payload(account, activity, contacts):
    return {
        'account': str(account.id),
        'source_activity': str(activity.id),
        'suggested_title': 'Envoyer récap chiffré sous 48h',
        'suggested_activity_type': ActivityType.EMAIL,
        'suggested_due_date': '2026-12-15',
        'suggested_contacts': [str(c.id) for c in contacts],
        'source': SignalSource.MANUAL,
    }


def _mk_nextstep(account, activity, user, contacts):
    ns = NextStepSignal(
        account=account, source_activity=activity,
        suggested_title='evolving',
        suggested_activity_type=ActivityType.EMAIL,
        source=SignalSource.MANUAL,
    )
    ns.save(user=user, client_id=account.client_id)
    ns.suggested_contacts.set(contacts)
    return ns


def _pain(account, activity, user, *, scope=ScopeLevel.BUSINESS,
          status=SignalStatus.VALIDATED, quote='q'):
    """Clone of test_cluster_member_filters.py::_pain (OPS x TIME cluster)."""
    is_validated = status == SignalStatus.VALIDATED
    p = PainSignal(
        account=account, source_activity=activity,
        what=SignalWhat.OPS, dimension=SignalDimension.TIME,
        summary='Reporting is slow', source_quote=quote,
        source=SignalSource.MANUAL if is_validated else SignalSource.LLM_EXTRACTED,
        status=SignalStatus.VALIDATED if is_validated else SignalStatus.PENDING,
        scope_level=scope,
    )
    p.save(user=user, client_id=account.client_id)
    return p


def _cluster_keys(response):
    data = response.json()['data']
    return {c['canonical_key'] for c in data}


# URL helpers ----------------------------------------------------------------

def _blocker_list():
    return reverse('module_signals:blocker-list')


def _blocker_detail(pk):
    return reverse('module_signals:blocker-detail', kwargs={'pk': pk})


def _objective_list():
    return reverse('module_signals:objective-list')


def _objective_detail(pk):
    return reverse('module_signals:objective-detail', kwargs={'pk': pk})


def _people_list():
    return reverse('module_signals:people-list')


def _people_detail(pk):
    return reverse('module_signals:people-detail', kwargs={'pk': pk})


def _nextstep_list():
    return reverse('module_signals:next-step-list')


def _nextstep_detail(pk):
    return reverse('module_signals:next-step-detail', kwargs={'pk': pk})


def _cluster_list():
    return reverse('module_signals:cluster-list')


def _cluster_detail(canonical_key):
    return reverse('module_signals:cluster-detail', kwargs={'canonical_key': canonical_key})


def _cluster_archive():
    return reverse('module_signals:cluster-archive')


# =============================================================================
# WRITE — base FKs (account / source_activity) on create
# =============================================================================

class TestWriteBaseFKs:

    def test_r1_post_account_of_other_tenant_is_400_object_not_found(
        self, authed_api_a, activity, other_tenant_account,
    ):
        response = authed_api_a.post(
            _blocker_list(),
            _blocker_payload(other_tenant_account, activity),
            format='json',
        )
        _assert_400(response, OBJECT_NOT_FOUND)
        assert BlockerSignal.objects.count() == 0

    def test_r2_post_source_activity_of_other_tenant_is_400_object_not_found(
        self, authed_api_a, account, other_tenant_activity,
    ):
        response = authed_api_a.post(
            _blocker_list(),
            _blocker_payload(account, other_tenant_activity),
            format='json',
        )
        _assert_400(response, OBJECT_NOT_FOUND)
        assert BlockerSignal.objects.count() == 0

    def test_r3_post_source_activity_of_other_account_is_400_invalid_account(
        self, authed_api_a, account, other_account_activity,
    ):
        response = authed_api_a.post(
            _blocker_list(),
            _blocker_payload(account, other_account_activity),
            format='json',
        )
        _assert_400(response, INVALID_ACCOUNT)
        assert BlockerSignal.objects.count() == 0


# =============================================================================
# WRITE — Blocker.contact
# =============================================================================

class TestWriteBlockerContact:

    def test_r4_post_contact_of_other_tenant_is_400_object_not_found(
        self, authed_api_a, account, activity, other_tenant_contact,
    ):
        response = authed_api_a.post(
            _blocker_list(),
            _blocker_payload(account, activity, contact=str(other_tenant_contact.id)),
            format='json',
        )
        _assert_400(response, OBJECT_NOT_FOUND)
        assert BlockerSignal.objects.count() == 0

    def test_r4_patch_contact_of_other_tenant_is_400_object_not_found(
        self, authed_api_a, account, activity, contact, other_tenant_contact, user_a,
    ):
        b = _mk_blocker(account, activity, user_a, contact=contact)
        response = authed_api_a.patch(
            _blocker_detail(b.id),
            {'contact': str(other_tenant_contact.id)},
            format='json',
        )
        _assert_400(response, OBJECT_NOT_FOUND)
        b.refresh_from_db()
        assert b.contact_id == contact.id

    def test_r5_post_contact_of_other_account_is_400_invalid_account(
        self, authed_api_a, account, activity, other_account_contact,
    ):
        response = authed_api_a.post(
            _blocker_list(),
            _blocker_payload(account, activity, contact=str(other_account_contact.id)),
            format='json',
        )
        _assert_400(response, INVALID_ACCOUNT)
        assert BlockerSignal.objects.count() == 0

    def test_r5_patch_contact_of_other_account_is_400_invalid_account(
        self, authed_api_a, account, activity, contact, other_account_contact, user_a,
    ):
        b = _mk_blocker(account, activity, user_a, contact=contact)
        response = authed_api_a.patch(
            _blocker_detail(b.id),
            {'contact': str(other_account_contact.id)},
            format='json',
        )
        _assert_400(response, INVALID_ACCOUNT)
        b.refresh_from_db()
        assert b.contact_id == contact.id


# =============================================================================
# WRITE — Objective.target_contact
# =============================================================================

class TestWriteObjectiveTargetContact:

    def test_r6_post_target_contact_of_other_tenant_is_400_object_not_found(
        self, authed_api_a, account, activity, other_tenant_contact,
    ):
        response = authed_api_a.post(
            _objective_list(),
            _objective_payload(account, activity, other_tenant_contact),
            format='json',
        )
        _assert_400(response, OBJECT_NOT_FOUND)
        assert ObjectiveSignal.objects.count() == 0

    def test_r6_post_target_contact_of_other_account_is_400_invalid_account(
        self, authed_api_a, account, activity, other_account_contact,
    ):
        response = authed_api_a.post(
            _objective_list(),
            _objective_payload(account, activity, other_account_contact),
            format='json',
        )
        _assert_400(response, INVALID_ACCOUNT)
        assert ObjectiveSignal.objects.count() == 0

    def test_r6_patch_target_contact_of_other_tenant_is_400_object_not_found(
        self, authed_api_a, account, activity, contact, other_tenant_contact, user_a,
    ):
        o = _mk_objective(account, activity, user_a, contact)
        response = authed_api_a.patch(
            _objective_detail(o.id),
            {'target_contact': str(other_tenant_contact.id)},
            format='json',
        )
        _assert_400(response, OBJECT_NOT_FOUND)
        o.refresh_from_db()
        assert o.target_contact_id == contact.id

    def test_r6_patch_target_contact_of_other_account_is_400_invalid_account(
        self, authed_api_a, account, activity, contact, other_account_contact, user_a,
    ):
        o = _mk_objective(account, activity, user_a, contact)
        response = authed_api_a.patch(
            _objective_detail(o.id),
            {'target_contact': str(other_account_contact.id)},
            format='json',
        )
        _assert_400(response, INVALID_ACCOUNT)
        o.refresh_from_db()
        assert o.target_contact_id == contact.id


# =============================================================================
# WRITE — People.target_contact / People.decision_cycle
# =============================================================================

class TestWritePeople:

    def test_r7_post_target_contact_of_other_tenant_is_400_object_not_found(
        self, authed_api_a, account, activity, other_tenant_contact,
    ):
        response = authed_api_a.post(
            _people_list(),
            _people_payload(account, activity, other_tenant_contact),
            format='json',
        )
        _assert_400(response, OBJECT_NOT_FOUND)
        assert PeopleSignal.objects.count() == 0

    def test_r7_post_target_contact_of_other_account_is_400_invalid_account(
        self, authed_api_a, account, activity, other_account_contact,
    ):
        response = authed_api_a.post(
            _people_list(),
            _people_payload(account, activity, other_account_contact),
            format='json',
        )
        _assert_400(response, INVALID_ACCOUNT)
        assert PeopleSignal.objects.count() == 0

    def test_r7_patch_target_contact_of_other_tenant_is_400_object_not_found(
        self, authed_api_a, account, activity, contact, other_tenant_contact, user_a,
    ):
        p = _mk_people(account, activity, user_a, contact)
        response = authed_api_a.patch(
            _people_detail(p.id),
            {'target_contact': str(other_tenant_contact.id)},
            format='json',
        )
        _assert_400(response, OBJECT_NOT_FOUND)
        p.refresh_from_db()
        assert p.target_contact_id == contact.id

    def test_r7_patch_target_contact_of_other_account_is_400_invalid_account(
        self, authed_api_a, account, activity, contact, other_account_contact, user_a,
    ):
        p = _mk_people(account, activity, user_a, contact)
        response = authed_api_a.patch(
            _people_detail(p.id),
            {'target_contact': str(other_account_contact.id)},
            format='json',
        )
        _assert_400(response, INVALID_ACCOUNT)
        p.refresh_from_db()
        assert p.target_contact_id == contact.id

    def test_r7_post_decision_cycle_of_other_tenant_is_400_object_not_found(
        self, authed_api_a, account, contact, other_tenant_decision_cycle,
    ):
        # DC-level manual qualification (no source_activity) — payload cloned
        # from test_people_signal_api.py::test_create_manual_dc_level_without_source_activity.
        payload = {
            'signal_type': 'people',
            'source': 'MANUAL',
            'account': str(account.id),
            'decision_cycle': str(other_tenant_decision_cycle.id),
            'role': PeopleRole.CHAMPION,
            'influence': InfluenceLevel.HIGH,
            'target_contact': str(contact.id),
            'notes': 'Qualified from DC workspace',
        }
        response = authed_api_a.post(_people_list(), payload, format='json')
        _assert_400(response, OBJECT_NOT_FOUND)
        assert PeopleSignal.objects.count() == 0


# =============================================================================
# WRITE — NextStep.suggested_contacts (M2M)
# =============================================================================

class TestWriteNextStepSuggestedContacts:

    def test_r8_post_contact_of_other_tenant_is_400_object_not_found(
        self, authed_api_a, account, activity, other_tenant_contact,
    ):
        response = authed_api_a.post(
            _nextstep_list(),
            _nextstep_payload(account, activity, [other_tenant_contact]),
            format='json',
        )
        _assert_400(response, OBJECT_NOT_FOUND)
        assert NextStepSignal.objects.count() == 0

    def test_r8_post_contact_of_other_account_is_400_invalid_account(
        self, authed_api_a, account, activity, other_account_contact,
    ):
        response = authed_api_a.post(
            _nextstep_list(),
            _nextstep_payload(account, activity, [other_account_contact]),
            format='json',
        )
        _assert_400(response, INVALID_ACCOUNT)
        assert NextStepSignal.objects.count() == 0

    def test_r8_patch_contact_of_other_tenant_is_400_object_not_found(
        self, authed_api_a, account, activity, contact, other_tenant_contact, user_a,
    ):
        ns = _mk_nextstep(account, activity, user_a, [contact])
        response = authed_api_a.patch(
            _nextstep_detail(ns.id),
            {'suggested_contacts': [str(other_tenant_contact.id)]},
            format='json',
        )
        _assert_400(response, OBJECT_NOT_FOUND)
        assert set(ns.suggested_contacts.values_list('id', flat=True)) == {contact.id}

    def test_r8_patch_contact_of_other_account_is_400_invalid_account(
        self, authed_api_a, account, activity, contact, other_account_contact, user_a,
    ):
        ns = _mk_nextstep(account, activity, user_a, [contact])
        response = authed_api_a.patch(
            _nextstep_detail(ns.id),
            {'suggested_contacts': [str(other_account_contact.id)]},
            format='json',
        )
        _assert_400(response, INVALID_ACCOUNT)
        assert set(ns.suggested_contacts.values_list('id', flat=True)) == {contact.id}


# =============================================================================
# WRITE — guard: provenance FKs are not writable via PATCH
# =============================================================================

class TestWriteProvenanceImmutableGuard:

    def test_r9_patch_account_and_source_activity_are_ignored(
        self, authed_api_a, account, activity, other_tenant_account,
        other_tenant_activity, user_a,
    ):
        b = _mk_blocker(account, activity, user_a)
        response = authed_api_a.patch(
            _blocker_detail(b.id),
            {
                'account': str(other_tenant_account.id),
                'source_activity': str(other_tenant_activity.id),
            },
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK, response.content
        b.refresh_from_db()
        assert b.account_id == account.id
        assert b.source_activity_id == activity.id


# =============================================================================
# CLUSTERS — read / archive across tenants
# =============================================================================

class TestClusterTenantIsolation:

    def test_r11_list_clusters_of_other_tenant_account_is_400_object_not_found(
        self, authed_api_b, account, activity, user_a,
    ):
        _pain(account, activity, user_a)
        response = authed_api_b.get(_cluster_list(), {'account': str(account.id)})
        _assert_400(response, OBJECT_NOT_FOUND)

    def test_r11_cluster_detail_of_other_tenant_account_is_400_object_not_found(
        self, authed_api_b, account, activity, user_a,
    ):
        p = _pain(account, activity, user_a)
        assert p.canonical_key  # precondition: the member really clusters
        response = authed_api_b.get(
            _cluster_detail(p.canonical_key),
            {'account': str(account.id), 'signal_type': 'pain'},
        )
        _assert_400(response, OBJECT_NOT_FOUND)

    def test_r12_archive_cluster_of_other_tenant_is_400_and_cluster_stays_visible(
        self, authed_api_b, authenticate, user_a, client_account_a,
        account, activity,
    ):
        from app_modules.signals.models import SignalClusterArchival

        p = _pain(account, activity, user_a)
        assert p.canonical_key

        response = authed_api_b.post(
            _cluster_archive(),
            {
                'account': str(account.id),
                'signal_type': 'pain',
                'canonical_key': p.canonical_key,
            },
            format='json',
        )
        _assert_400(response, OBJECT_NOT_FOUND)
        assert SignalClusterArchival.objects.count() == 0

        # Same APIClient instance (conftest `api`) — switch to tenant A.
        authenticate(authed_api_b, user_a, client_account_a.id)
        listing = authed_api_b.get(_cluster_list(), {'account': str(account.id)})
        assert listing.status_code == status.HTTP_200_OK, listing.content
        assert p.canonical_key in _cluster_keys(listing)


# =============================================================================
# POSITIVE CONTROLS — no over-blocking
# =============================================================================

class TestPositiveControls:

    def test_c1_post_and_patch_blocker_same_tenant_same_account(
        self, authed_api_a, account, activity, contact, contact_extra,
    ):
        response = authed_api_a.post(
            _blocker_list(),
            _blocker_payload(account, activity, contact=str(contact.id)),
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED, response.content
        pk = response.json()['data']['id']

        response = authed_api_a.patch(
            _blocker_detail(pk),
            {'contact': str(contact_extra.id)},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK, response.content
        assert BlockerSignal.objects.get(pk=pk).contact_id == contact_extra.id

    def test_c2_list_own_clusters_is_200(
        self, authed_api_a, account, activity, user_a,
    ):
        p = _pain(account, activity, user_a)
        response = authed_api_a.get(_cluster_list(), {'account': str(account.id)})
        assert response.status_code == status.HTTP_200_OK, response.content
        assert p.canonical_key in _cluster_keys(response)

    def test_c3_other_tenant_lists_its_own_clusters_is_200(
        self, authed_api_b, other_tenant_account, other_tenant_activity, user_b,
    ):
        p = _pain(other_tenant_account, other_tenant_activity, user_b)
        response = authed_api_b.get(
            _cluster_list(), {'account': str(other_tenant_account.id)},
        )
        assert response.status_code == status.HTTP_200_OK, response.content
        assert p.canonical_key in _cluster_keys(response)
