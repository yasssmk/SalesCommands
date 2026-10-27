# backend/tests/signals/test_nextstep_cited_contacts.py
"""
Sprint Next steps 5.8d (2/3) -- GET /module-signals/next-steps/{id}/cited-contacts/

The names a next step CITES (its People's names -- full_name, else its
contact's -- then suggested_people_names), each with the contact of the
ACCOUNT it designates WITHOUT ambiguity, or null. Read-only, used by the
activity pre-fill (activityDefaultsFromNextStep: for MEETING / CALL / EMAIL
the matched contacts are pre-selected, the others recalled as "Mentioned").

  * a People linked to a contact (of the account) -> that contact;
  * any other name -> the TD-279 name rule (participant_refs, the same
    _best_unique_match -- not a second algorithm) applied to the contacts
    of the ACCOUNT (same tenant AND account): a tie -> null (never a guess),
    no match -> null;
  * tenant guard: another tenant's next step -> 404;
  * 5.8h (2): a REJECTED People is never used -- neither its name nor its
    contact; the compact People of the next step payload carries its status
    so the front pre-fill can apply the same rule.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from app_modules.activities.constants import ActivityType
from app_modules.signals.constants import PeopleRole, SignalSource, SignalStatus
from app_modules.signals.models import NextStepSignal, PeopleSignal


pytestmark = pytest.mark.django_db


def _url(pk):
    return reverse('module_signals:next-step-cited-contacts', kwargs={'pk': pk})


def _contact(account, user, first, last):
    from app_modules.contacts.models import Contact
    c = Contact(account=account, first_name=first, last_name=last, job_title='')
    c.save(user=user, client_id=account.client_id)
    return c


def _people(account, activity, user, full_name, contact=None):
    p = PeopleSignal(account=account, source_activity=activity, full_name=full_name,
                     role=PeopleRole.UNKNOWN, source=SignalSource.LLM_EXTRACTED,
                     target_contact=contact)
    p.save(user=user, client_id=account.client_id)
    return p


@pytest.fixture
def setup(account, activity, client_account_a, user_a):
    from app_modules.accounts.models import CompanyAccount
    other_account = CompanyAccount(company_name='Other Co', has_buying_decision=True)
    other_account.save(user=user_a, client_id=client_account_a.id)
    contacts = {
        'laurent': _contact(account, user_a, 'Laurent', 'Dubois'),
        'thomas_l': _contact(account, user_a, 'Thomas', 'Lefèvre'),
        'thomas_m': _contact(account, user_a, 'Thomas', 'Martin'),
        'isabelle': _contact(account, user_a, 'Isabelle', 'Roux'),
        # same tenant, ANOTHER account: never matched
        'marc_other': _contact(other_account, user_a, 'Marc', 'Petit'),
    }
    ns = NextStepSignal(
        account=account, source_activity=activity,
        suggested_title='Security review', suggested_activity_type=ActivityType.MEETING,
        suggested_people_names=['Laurent', 'Thomas', 'Marc', 'Thomas Martin'],
        source=SignalSource.LLM_EXTRACTED, confidence=0.8,
    )
    ns.save(user=user_a, client_id=account.client_id)
    ns.suggested_people.set([
        # cited as written, linked to a contact whose name differs: the
        # stored link wins (no name could find it)
        _people(account, activity, user_a, 'the CFO', contacts['isabelle']),
        _people(account, activity, user_a, 'Karim Benali'),
    ])
    return {'ns': ns, **contacts}


def _cited(response):
    assert response.status_code == status.HTTP_200_OK, response.content
    return [(c['name'], (c['contact'] or {}).get('id')) for c in response.json()['data']['cited']]


def test_each_cited_name_with_the_account_contact_it_designates(authed_api_a, setup):
    assert _cited(authed_api_a.get(_url(setup['ns'].id))) == [
        # its People, in their order (the detail's: newest first)
        ('Karim Benali', None),                         # a People without contact, no match
        ('the CFO', str(setup['isabelle'].id)),         # a People linked to a contact
        # then suggested_people_names, as written
        ('Laurent', str(setup['laurent'].id)),          # the TD-279 rule, unique
        ('Thomas', None),                               # two Thomas: a tie, never a guess
        ('Marc', None),                                 # only on ANOTHER account
        ('Thomas Martin', str(setup['thomas_m'].id)),   # full name: unique
    ]


def test_the_contact_shape_is_the_activity_contacts_one(authed_api_a, setup):
    cited = authed_api_a.get(_url(setup['ns'].id)).json()['data']['cited']
    laurent = next(c for c in cited if c['name'] == 'Laurent')['contact']
    assert {'id', 'first_name', 'last_name', 'full_name', 'job_title'} <= set(laurent)
    assert laurent['full_name'] == 'Laurent Dubois'


def test_another_tenant_cannot_read_it(authed_api_b, setup):
    assert authed_api_b.get(_url(setup['ns'].id)).status_code == status.HTTP_404_NOT_FOUND


def test_the_rule_is_the_td279_one():
    """One algorithm: the account-contact match IS resolve_contact_by_name,
    the participant rule of TD-279 (resolve_participant_by_name uses it)."""
    import inspect
    from app_modules.ai_pipelines.services import participant_refs
    assert 'resolve_contact_by_name(' in inspect.getsource(participant_refs.resolve_participant_by_name)


# =============================================================================
# 5.8h (2) -- a REJECTED People is never used
# =============================================================================

def _reject(people, user):
    people.status = SignalStatus.REJECTED
    people.save(user=user, client_id=people.client_id)
    return people


def test_a_rejected_people_is_never_cited(authed_api_a, setup, account, activity, user_a):
    """A REJECTED People linked to a contact: neither its name nor its
    contact (the others unchanged)."""
    rejected = _reject(
        _people(account, activity, user_a, 'Laurent Dubois', setup['laurent']), user_a,
    )
    setup['ns'].suggested_people.add(rejected)
    cited = _cited(authed_api_a.get(_url(setup['ns'].id)))
    assert ('Laurent Dubois', str(setup['laurent'].id)) not in cited
    assert 'Laurent Dubois' not in [name for name, _ in cited]
    # The non-rejected People are still cited.
    assert ('the CFO', str(setup['isabelle'].id)) in cited
    assert ('Karim Benali', None) in cited


def test_the_compact_people_carries_its_status(authed_api_a, setup, account, activity, user_a):
    rejected = _reject(_people(account, activity, user_a, 'Paul Rejected'), user_a)
    setup['ns'].suggested_people.add(rejected)
    for url in (reverse('module_signals:next-step-detail', kwargs={'pk': setup['ns'].id}),
                reverse('module_signals:next-step-list')):
        ns = _next_step_in(authed_api_a.get(url).json(), setup['ns'].id)
        statuses = {p['full_name']: p['status'] for p in ns['suggested_people']}
        assert statuses['Paul Rejected'] == SignalStatus.REJECTED
        assert statuses['Karim Benali'] == SignalStatus.PENDING


def _next_step_in(body, pk):
    """The next step in a detail (bare) or list (wrapped / paginated) body."""
    body = body.get('data', body) if isinstance(body, dict) else body
    if isinstance(body, dict) and body.get('id') == str(pk):
        return body
    rows = body.get('results', body) if isinstance(body, dict) else body
    return next(n for n in rows if n['id'] == str(pk))

