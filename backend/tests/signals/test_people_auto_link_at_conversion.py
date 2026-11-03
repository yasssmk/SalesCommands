# backend/tests/signals/test_people_auto_link_at_conversion.py
"""
Sprint « Cycle de vie des contacts », 8c-0 (PO) — at the PASSAGE campaign ->
DC (« Start Decision Cycle »: a DC born from a campaign activity), every
VALIDATED People of the sequence (étape 2 attachment) is linked
AUTOMATICALLY to a stakeholder of the DC, without confirmation:
  * the same contact, OR the same normalised name as a stakeholder of the DC
    (THE match rule of resolution_candidates) -> attach_signal to it;
  * else a new stakeholder (its contact if the signal has one, else its name
    and/or department) + attach_signal.
PENDING People keep their normal path (✓ -> resolve). Outside the passage
(an activity linked to a DC later): unchanged, no automatic link.
Real paths; helpers reused from test_signal_cycle_attachment.py.
"""

import pytest

from app_modules.signals.constants import SignalStatus
from tests.signals.test_signal_cycle_attachment import (
    _campaign_account,
    _cycle,
    _patch_cycle,
    _people,
    _plain_activity,
    _prospect_activity,
    _start_decision_cycle,
)


pytestmark = pytest.mark.django_db


def _with(ps, **fields):
    from app_modules.signals.models import PeopleSignal
    PeopleSignal.objects.filter(pk=ps.pk).update(**fields)
    ps.refresh_from_db()
    return ps


def test_start_decision_cycle_links_every_validated_people_of_the_sequence(
    authed_api_a, account, user_a,
):
    from app_modules.contacts.models import Contact
    from app_modules.core_modules.models import StandardDepartment
    from app_modules.decision_cycles.models import Stakeholder
    from app_modules.signals.models import PeopleSignal
    finance, _ = StandardDepartment.objects.get_or_create(name='Finance')
    paul = Contact(account=account, first_name='Paul', last_name='X')
    paul.save(user=user_a, client_id=account.client_id)

    ca = _campaign_account(account, user_a)
    first = _prospect_activity(ca, user_a, 'Lea', outcome='SUCCESSFUL')
    second = _prospect_activity(ca, user_a, 'Hugo')
    v = SignalStatus.VALIDATED
    p_paul = _with(_people(first, user_a, 'Paul X', status=v), target_contact=paul)
    p_marc = _people(first, user_a, 'Marc', status=v)
    p_marc_again = _people(second, user_a, 'marc ', status=v)           # same normalised name
    p_paul_again = _with(_people(second, user_a, 'P. X', status=v), target_contact=paul)  # same contact
    p_finance = _with(_people(second, user_a, '', status=v), target_department=finance)
    p_pending = _people(second, user_a, 'Zoé')                         # PENDING: normal path

    dc = _start_decision_cycle(authed_api_a, first)

    rows = {p.pk: p for p in PeopleSignal.objects.filter(
        pk__in=[p_paul.pk, p_marc.pk, p_marc_again.pk, p_paul_again.pk, p_finance.pk, p_pending.pk])}
    for p in rows.values():
        assert p.decision_cycle_id == dc.id
    paul_st = Stakeholder.objects.get(decision_cycle=dc, contact=paul)
    marc_st = Stakeholder.objects.get(decision_cycle=dc, full_name_normalized='marc')
    fin_st = Stakeholder.objects.get(decision_cycle=dc, department=finance, contact__isnull=True)
    assert rows[p_paul.pk].stakeholder_id == rows[p_paul_again.pk].stakeholder_id == paul_st.id
    assert rows[p_marc.pk].stakeholder_id == rows[p_marc_again.pk].stakeholder_id == marc_st.id
    assert rows[p_finance.pk].stakeholder_id == fin_st.id
    assert Stakeholder.objects.filter(decision_cycle=dc).count() == 3     # no duplicate
    for pk in (p_paul.pk, p_marc.pk, p_marc_again.pk, p_paul_again.pk, p_finance.pk):
        assert rows[pk].status == SignalStatus.VALIDATED                 # status untouched
    assert rows[p_pending.pk].stakeholder_id is None                     # resolve, as before
    assert rows[p_pending.pk].status == SignalStatus.PENDING


def test_an_existing_stakeholder_of_the_same_name_is_reused(authed_api_a, account, user_a):
    """The match also reads the stakeholders already in the DC (here one the
    conversion activity's own People brought in first, same name)."""
    from app_modules.decision_cycles.models import Stakeholder
    ca = _campaign_account(account, user_a)
    call = _prospect_activity(ca, user_a, 'Lea', outcome='SUCCESSFUL')
    a = _people(call, user_a, 'Marc Durand', status=SignalStatus.VALIDATED)
    b = _people(call, user_a, 'MARC  DURAND', status=SignalStatus.VALIDATED)
    dc = _start_decision_cycle(authed_api_a, call)
    a.refresh_from_db(); b.refresh_from_db()
    assert a.stakeholder_id == b.stakeholder_id
    assert Stakeholder.objects.filter(decision_cycle=dc).count() == 1


def test_an_activity_linked_to_a_dc_later_links_nobody(authed_api_a, account, user_a):
    """Outside the campaign -> DC passage: unchanged (resolve, « Link to the
    deal »)."""
    from app_modules.decision_cycles.models import Stakeholder
    activity = _plain_activity(account, user_a)
    ps = _people(activity, user_a, 'Marc', status=SignalStatus.VALIDATED)
    cycle = _cycle(account, user_a)
    _patch_cycle(authed_api_a, activity, cycle)
    ps.refresh_from_db()
    assert ps.decision_cycle_id == cycle.id
    assert ps.stakeholder_id is None
    assert not Stakeholder.objects.filter(decision_cycle=cycle).exists()


def test_the_contact_wins_over_the_name(authed_api_a, account, user_a):
    """A person whose contact and name designate two different stakeholders
    joins its CONTACT's (the contact is the reliable identity)."""
    from app_modules.contacts.models import Contact
    from app_modules.decision_cycles.models import Stakeholder
    paul = Contact(account=account, first_name='Paul', last_name='X')
    paul.save(user=user_a, client_id=account.client_id)
    ca = _campaign_account(account, user_a)
    call = _prospect_activity(ca, user_a, 'Lea', outcome='SUCCESSFUL')
    v = SignalStatus.VALIDATED
    _with(_people(call, user_a, 'Paul X', status=v), target_contact=paul)
    _people(call, user_a, 'Marc', status=v)
    tricky = _with(_people(call, user_a, 'Marc', status=v), target_contact=paul)
    dc = _start_decision_cycle(authed_api_a, call)
    tricky.refresh_from_db()
    assert tricky.stakeholder_id == Stakeholder.objects.get(decision_cycle=dc, contact=paul).id
