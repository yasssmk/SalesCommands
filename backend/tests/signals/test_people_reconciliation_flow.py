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

FINDINGS status:
  * full_name not wired into the People serializers — FIXED in sub-step 5.1
    (see TestFullNameSerializer: create persists full_name; List/Detail expose
    full_name + read-only full_name_normalized).
  * contact create response omits the new id — still open (5.3).
  * People PATCH unlink bypasses the model clean() invariant — still open (5.2).
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
    """Create a PeopleSignal via the model manager — a compact way to build a
    NAMED, contact-less signal (the reconciliation entry point) for the flow
    tests. The real POST path is exercised separately in TestFullNameSerializer."""
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
# full_name is wired into the People serializers (sub-step 5.1)
# =============================================================================

class TestFullNameSerializer:

    def _post(self, api, account, activity, decision_cycle, finance, **extra):
        body = {
            'account': str(account.id),
            'source_activity': str(activity.id),
            'decision_cycle': str(decision_cycle.id),
            'role': PeopleRole.DECISION_MAKER,
            'target_department': finance.id,
            'source': SignalSource.MANUAL,
        }
        body.update(extra)
        return api.post(_people_list_url(), body, format='json')

    def test_create_persists_and_read_exposes_full_name(
        self, authed_api_a, account, activity, decision_cycle, finance,
    ):
        resp = self._post(authed_api_a, account, activity, decision_cycle,
                          finance, full_name='Marc Dubois')
        assert resp.status_code == status.HTTP_201_CREATED, resp.data

        # Persisted (Create serializer accepts full_name; save() derives norm).
        sig = PeopleSignal.objects.get(account=account)
        assert sig.full_name == 'Marc Dubois'
        assert sig.full_name_normalized == 'marc dubois'

        # Read surface (Detail) exposes both — normalized is read-only-derived.
        detail = authed_api_a.get(_people_detail_url(sig.id))
        assert detail.status_code == status.HTTP_200_OK
        body = _unwrap(detail)
        assert body['full_name'] == 'Marc Dubois'
        assert body['full_name_normalized'] == 'marc dubois'

    def test_full_name_normalized_is_not_writable(
        self, authed_api_a, account, activity, decision_cycle, finance,
    ):
        # Attempt to author full_name_normalized directly — it must be ignored
        # and stay derived from the raw full_name.
        resp = self._post(authed_api_a, account, activity, decision_cycle,
                          finance, full_name='Marc Dubois',
                          full_name_normalized='HACKED')
        assert resp.status_code == status.HTTP_201_CREATED, resp.data

        sig = PeopleSignal.objects.get(account=account)
        assert sig.full_name_normalized == 'marc dubois'  # derived, not 'HACKED'


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


# =============================================================================
# IDENTITY INVARIANT — at least one of contact / department / full_name,
# enforced on CREATE and UPDATE (sub-step 5.2).
# =============================================================================

class TestPeopleIdentityInvariant:

    def _create_body(self, account, activity, decision_cycle, **extra):
        body = {
            'account': str(account.id),
            'source_activity': str(activity.id),
            'decision_cycle': str(decision_cycle.id),
            'role': PeopleRole.DECISION_MAKER,
            'source': SignalSource.MANUAL,
        }
        body.update(extra)
        return body

    # ---- UNLINK (update) ----

    def test_a_unlink_keeping_name_succeeds(
        self, authed_api_a, account, activity, decision_cycle, user_a, contact,
    ):
        sig = _mk_people(account, activity, decision_cycle, user_a,
                         full_name='Marc Dubois', target_contact=contact)
        resp = authed_api_a.patch(_people_detail_url(sig.id),
                                  {'target_contact': None}, format='json')
        assert resp.status_code == status.HTTP_200_OK, resp.data  # name identifies

    def test_b_unlink_keeping_department_succeeds(
        self, authed_api_a, account, activity, decision_cycle, user_a,
        contact, finance,
    ):
        sig = _mk_people(account, activity, decision_cycle, user_a,
                         target_contact=contact, target_department=finance)
        resp = authed_api_a.patch(_people_detail_url(sig.id),
                                  {'target_contact': None}, format='json')
        assert resp.status_code == status.HTTP_200_OK, resp.data  # dept identifies

    def test_c_unlink_to_nothing_is_a_clean_400(
        self, authed_api_a, account, activity, decision_cycle, user_a, contact,
    ):
        # contact-only signal (no name, no department) → unlink leaves NO
        # identity → clean 400 (standard error handler), never 200, never 500.
        sig = _mk_people(account, activity, decision_cycle, user_a,
                         full_name='', target_contact=contact)
        resp = authed_api_a.patch(_people_detail_url(sig.id),
                                  {'target_contact': None}, format='json')
        assert resp.status_code == status.HTTP_400_BAD_REQUEST, resp.data
        sig.refresh_from_db()
        assert sig.target_contact_id == contact.id  # unchanged

    # ---- CREATE ----

    def test_d_create_without_any_identity_is_400(
        self, authed_api_a, account, activity, decision_cycle,
    ):
        resp = authed_api_a.post(
            _people_list_url(),
            self._create_body(account, activity, decision_cycle),
            format='json',
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST, resp.data

    def test_e_create_with_name_only_succeeds(
        self, authed_api_a, account, activity, decision_cycle,
    ):
        resp = authed_api_a.post(
            _people_list_url(),
            self._create_body(account, activity, decision_cycle,
                              full_name='Marc Dubois'),
            format='json',
        )
        assert resp.status_code == status.HTTP_201_CREATED, resp.data  # name suffices
