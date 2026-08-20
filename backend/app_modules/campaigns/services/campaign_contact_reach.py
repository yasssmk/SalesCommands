# app_modules/campaigns/services/campaign_contact_reach.py
"""
CONTACTS_REACHED — how many people the campaign actually got through to.

THE RULE (PO, final): a campaign contact is REACHED when the campaign carries at
least one COMPLETED activity on them whose outcome says a conversation happened.
The outcome set is ``campaign_execution_service.REACHED_OUTCOMES``, declared
beside the two the campaign state machine already uses rather than re-listed
here.

REACHED IS NOT SUCCESSFUL. A refusal is a contact: NOT_INTERESTED and
UNSUBSCRIBE_OPTOUT both mean somebody picked up and answered. What is excluded is
everything where nobody spoke to the person — NO_ANSWER, WRONG_CONTACT,
WRONG_EMAIL, INVALID_PHONE_NUMBER — plus CALLBACK_REQUESTED (a gatekeeper or a
voicemail promising a call back is not the person) and OTHER (no information to
decide on).

WHAT THIS REPLACES
------------------
"distinct contacts with at least one COMPLETED activity", with no outcome filter
at all. A dial that hit voicemail counted as reaching the contact, so the number
measured dialling effort and not conversations — and it only ever went up, since
no outcome could take a contact back out of it.

ONE DECLARATION, TWO CALLERS
----------------------------
The campaign DETAIL path (CampaignAnalyticsService._count_contacts_reached) and
the campaign LIST batch (campaign_objective_progress) both call in here, the same
way both money surfaces call ``campaign_dc_attribution.campaign_money``. They had
a calculation each, and the two did not agree: the detail used
``.values('contacts').distinct().count()`` while the list used
``Count('contacts', distinct=True)``. Those differ by one whenever a campaign
activity has no contact attached — a plain ``distinct()`` counts the NULL group
as a value, ``Count(distinct=True)`` drops it — so the detail page could read one
higher than the card for the same campaign.

WHICH LINK IDENTIFIES THE PERSON
--------------------------------
``Activity.campaign_contact`` — the FK to the CampaignContact pivot
(activities/models.py:240-248), not the ``contacts`` M2M. Three reasons:

* it is the CAMPAIGN's notion of a contact, which is what the objective is set
  on. The same person enrolled in two campaigns is two campaign contacts, and
  reaching them in one says nothing about the other;
* it is to-ONE, so ``Count(distinct=True)`` over it needs no join to a to-many
  table and cannot fan out;
* every campaign activity-creation path sets it — the sequence generator
  (campaign_execution_service) and the contact views alike — so nothing real is
  lost by reading it.

``Count(<fk>, distinct=True)`` ignores NULL rows by definition, so an activity
with no campaign contact contributes nothing rather than a phantom +1.
"""

from __future__ import annotations

from django.db.models import Count

from app_modules.activities.constants import ActivityStatus
from app_modules.activities.models import Activity

from .campaign_execution_service import REACHED_OUTCOMES


__all__ = [
    'REACHED_OUTCOMES',
    'reached_activities',
    'contacts_reached_count',
    'contacts_reached_by_campaign',
]


def reached_activities(queryset):
    """Narrow an Activity queryset to the rows that PROVE a contact was reached.

    ``status=COMPLETED`` is not decoration: ``Activity.outcome`` is documented as
    meaningful only once completed, so a PLANNED row carrying a stray outcome
    must not reach anybody — and a CANCELLED call never happened, which is why it
    needs no exclusion of its own.
    """
    return queryset.filter(
        status=ActivityStatus.COMPLETED,
        outcome__in=REACHED_OUTCOMES,
    )


def contacts_reached_count(campaign_id):
    """How many distinct campaign contacts ``campaign_id`` has reached. ONE query.

    Counted per CONTACT: three completed successful calls on one person is one
    contact reached, not three.
    """
    return reached_activities(
        Activity.objects.filter(campaign_id=campaign_id)
    ).aggregate(
        reached=Count('campaign_contact', distinct=True)
    )['reached']


def contacts_reached_by_campaign(campaign_ids):
    """``{campaign_id: count}`` for a whole page, in ONE grouped query.

    The same predicate as ``contacts_reached_count``, applied with a GROUP BY
    instead of once per campaign — the list page renders many campaigns and must
    not run a query each. Campaigns with nothing to show still get a key, with 0,
    so callers can index the result without a missing-key branch.
    """
    campaign_ids = list(campaign_ids)
    grouped = dict(
        reached_activities(
            Activity.objects.filter(campaign_id__in=campaign_ids)
        )
        .values_list('campaign_id')
        .annotate(reached=Count('campaign_contact', distinct=True))
    )
    return {campaign_id: grouped.get(campaign_id, 0) for campaign_id in campaign_ids}
