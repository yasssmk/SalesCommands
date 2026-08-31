# backend/tests/signals/test_people_reconciliation_flow.py
"""
People contact-reconciliation flow — INTEGRATION test.

Proves the reconciliation backend assembles from EXISTING bricks, exercised
through the REAL DRF endpoints (APIClient), not model shortcuts:

  * suggest   : GET  /contacts/?account_id=&standard_department=&search=
  * create    : POST /contacts/           (ContactSerializer)
  * link      : PATCH /module-signals/people/{id}/  {target_contact: <id>}
  * unlink    : PATCH /module-signals/people/{id}/  {target_contact: null}

Cluster transitions are read through the real read-time SignalClusterService
(same pattern as the competitor cluster tests).

FINDING surfaced by this test (see test_create_via_api_silently_drops_full_name):
`full_name` / `full_name_normalized` were added to the PeopleSignal MODEL
(sub-step 1) but wired into NONE of the People serializers — so the real POST
create path cannot SET full_name and the read serializers cannot EXPOSE it.
The name-carrying fixture below is therefore built through the model manager.
"""
import pytest
from django.urls import reverse
from rest_framework import status

from app_modules.signals.constants import PeopleRole, SignalSource
from app_modules.signals.models import PeopleSignal
from app_modules.signals.services import SignalClusterService
from app_modules.contacts.models import Contact


pytestmark = pytest.mark.django_db


# =============================================================================
# HELPERS / FIXTURES
# =============================================================================

@pytest.fixture
def finance(db):
    from app_modules.core_modules.models import StandardDepartment
    d, _ = StandardDepartment.objects.get_or_create(name='Finance')
    return d


def _unwrap(resp):
    """The API wraps writes in a {'data': {...}, 'success': True} envelope."""
    body = resp.data
    if isinstance(body, dict) and 'data' in body and 'success' in body:
        return body['data']
    return body


def _people_key(sig):
    """The cluster's per-person key for one signal, via the real service."""
    return SignalClusterService._people_cluster_key(sig)


def _people_list_url():
    return reverse('module_signals:people-list')


def _people_detail_url(pk):
    return reverse('module_signals:people-detail', args=[pk])


def _contacts_url():
    return reverse('module_contacts:list')


def _mk_people(account, activity, decision_cycle, user_a, *,
               full_name='', role=PeopleRole.DECISION_MAKER,
               target_contact=None, target_department=None):
    """Create a PeopleSignal via the model manager (the create serializer does
    not accept full_name — see the FINDING). Used to build a NAMED, contact-less
    signal, the reconciliation entry point."""
    sig = PeopleSignal(
        account=account,
        source_activity=activity,
        decision_cycle=decision_cycle,
        full_name=full_name,
        role=role,
        target_contact=target_contact,
        target_department=target_department,
        source=SignalSource.MANUAL,
    )
    sig.save(user=user_a, client_id=account.client_id)
    return sig


# =============================================================================
# FINDING — full_name is not wired into the create serializer
# =============================================================================

class TestFullNameSerializerGap:

    def test_create_via_api_silently_drops_full_name(
        self, authed_api_a, account, activity, decision_cycle, finance,
    ):
        resp = authed_api_a.post(
            _people_list_url(),
            {
                'account': str(account.id),
                'source_activity': str(activity.id),
                'decision_cycle': str(decision_cycle.id),
                'role': PeopleRole.DECISION_MAKER,
                'target_department': finance.id,
                'full_name': 'Marc Dubois',
                'source': SignalSource.MANUAL,
            },
            format='json',
        )
        assert resp.status_code == status.HTTP_201_CREATED, resp.data

        sig = PeopleSignal.objects.get(account=account)
        # full_name is NOT in PeopleSignalCreateSerializer.Meta.fields, so DRF
        # drops it: the created signal has an empty name.
        assert sig.full_name == ''
        assert sig.full_name_normalized == ''
        # And the read surface never exposes it either.
        assert 'full_name' not in resp.data


# =============================================================================
# RECONCILIATION FLOW (real endpoints)
# =============================================================================

class TestPeopleReconciliationFlow:

    def test_full_flow_suggest_create_link_unlink(
        self, authed_api_a, account, activity, decision_cycle, user_a, finance,
    ):
        # 1.1 — a NAMED, contact-less People signal (model manager; see FINDING).
        sig = _mk_people(
            account, activity, decision_cycle, user_a,
            full_name='Marc Dubois', target_department=finance,
        )

        # 1.2 — CLUSTER BEFORE: keyed on name+department (no contact).
        assert _people_key(sig) == f'name:marc dubois|dept:{finance.id}'
        clusters = SignalClusterService.list_clusters_for_account(
            account_id=account.id, signal_type='people',
            decision_cycle_id=decision_cycle.id,
        )
        assert any(c['canonical_key'] == f'name:marc dubois|dept:{finance.id}'
                   for c in clusters)

        # 1.3 — SUGGEST: bounded to account + department + name. Empty is OK
        #        (no directory contact yet); we prove the call is valid + scoped.
        resp = authed_api_a.get(
            _contacts_url(),
            {'account_id': str(account.id),
             'standard_department': str(finance.id),
             'search': 'Marc'},
        )
        assert resp.status_code == status.HTTP_200_OK

        # 1.4 — CREATE a contact from the signal (name split + department).
        resp = authed_api_a.post(
            _contacts_url(),
            {'first_name': 'Marc', 'last_name': 'Dubois',
             'account_id': str(account.id),
             'standard_department_id': finance.id},
            format='json',
        )
        assert resp.status_code == status.HTTP_201_CREATED, resp.data
        # FINDING: the create response does NOT return the new contact's id
        # (nor full_name / account / standard_department) — only the plain
        # write fields. A client cannot chain create -> link from the response
        # alone; it must re-query. We fetch from the DB to continue the flow.
        assert 'id' not in _unwrap(resp)
        contact = Contact.objects.get(account=account, first_name='Marc',
                                      last_name='Dubois')
        contact_id = contact.id
        # client_id auto-injected from the account (multi-tenant); email absent OK.
        assert str(contact.client_id) == str(account.client_id)
        assert contact.email is None
        assert contact.standard_department_id == finance.id

        # 1.5 — LINK: PATCH the signal's target_contact.
        resp = authed_api_a.patch(
            _people_detail_url(sig.id),
            {'target_contact': str(contact_id)},
            format='json',
        )
        assert resp.status_code == status.HTTP_200_OK, resp.data
        sig.refresh_from_db()
        assert str(sig.target_contact_id) == str(contact_id)

        # 1.6 — CLUSTER AFTER: the key flips to contact:<id>.
        assert _people_key(sig) == f'contact:{contact_id}'

        # 1.7 — UNLINK with a department still present → clean() satisfied → 200.
        resp = authed_api_a.patch(
            _people_detail_url(sig.id),
            {'target_contact': None},
            format='json',
        )
        assert resp.status_code == status.HTTP_200_OK, resp.data
        sig.refresh_from_db()
        assert sig.target_contact_id is None
        assert sig.target_department_id == finance.id

    def test_unlink_without_department_real_behavior(
        self, authed_api_a, account, activity, decision_cycle, user_a, contact,
    ):
        # 1.8 — a signal with ONLY a contact (no department). Unlinking removes
        #        the last identity. The MODEL clean() invariant forbids a signal
        #        with neither target_contact nor target_department.
        #
        # REAL BEHAVIOR (characterised, not endorsed): the PATCH returns 200 and
        # the signal is left with NO contact AND NO department — the update
        # serializer does NOT run the model clean() invariant. This is the
        # FINDING reported to the PO; the test pins the current behaviour rather
        # than asserting the audit's assumed 400. NB: not a 500 either.
        sig = _mk_people(
            account, activity, decision_cycle, user_a,
            full_name='', target_contact=contact,
        )
        resp = authed_api_a.patch(
            _people_detail_url(sig.id),
            {'target_contact': None},
            format='json',
        )
        assert resp.status_code == status.HTTP_200_OK, resp.data
        sig.refresh_from_db()
        assert sig.target_contact_id is None
        assert sig.target_department_id is None  # clean() invariant bypassed
