# app_modules/activities/services/participant_rules.py
"""
THE participant rule of an activity — sprint « Cycle de vie des contacts »,
étape 7. One module, called by every user path:
  * POST   /module-activities/            (ActivityCreateSerializer)
  * PATCH  /module-activities/{id}/       (ActivityUpdateSerializer — also
                                           when only the TYPE changes)
  * POST   /module-activities/create-with-entities/ (ActivityCreationService)

Rules:
  * the FINAL type in PEOPLE_ACTIVITY_TYPES (MEETING / CALL / EMAIL / DEMO)
    => at least one participant (a contact, or a non-converted stakeholder of
    the activity's DC — étape 7 (2)); any other type => no minimum;
  * the stakeholders: only those of the activity's DC whose contact is NULL;
  * the contacts belong to the activity's account (same tenant);
  * Meeting -> Task keeps the participants (nothing here clears them).
System exception: the campaign generation (campaign_execution_service.py
491-512) creates its account-level activities without contact and does not
go through these paths.
"""

from core.error_messages import ActivityErrorMessages
from core.exceptions import StandardizedValidationError

from ..constants import PEOPLE_ACTIVITY_TYPES


def resolve_contacts(contact_ids, *, client_id, account):
    """The Contacts of `contact_ids` (deduplicated, order kept), every one of
    the activity's tenant AND account — else the standard refusal."""
    from app_modules.contacts.models import Contact

    ids = list(dict.fromkeys(str(i) for i in (contact_ids or [])))
    if not ids:
        return []
    contacts = list(Contact.objects.filter(id__in=ids, client_id=client_id, account=account))
    if len(contacts) != len(ids):
        raise StandardizedValidationError(ActivityErrorMessages.PARTICIPANT_CONTACT_INVALID)
    return contacts


def resolve_stakeholders(stakeholder_ids, *, client_id, decision_cycle_id):
    """
    The Stakeholders of `stakeholder_ids` (étape 7 (2)): only the stakeholders
    of the activity's decision cycle that are NOT converted (contact NULL) —
    a converted one is an Activity.contacts entry. No decision cycle, another
    cycle, a converted one, an unknown id -> the standard refusal.
    """
    from app_modules.decision_cycles.models import Stakeholder

    ids = list(dict.fromkeys(str(i) for i in (stakeholder_ids or [])))
    if not ids:
        return []
    if not decision_cycle_id:
        raise StandardizedValidationError(ActivityErrorMessages.PARTICIPANT_STAKEHOLDER_INVALID)
    stakeholders = list(Stakeholder.objects.filter(
        id__in=ids, client_id=client_id, decision_cycle_id=decision_cycle_id,
        contact__isnull=True,
    ))
    if len(stakeholders) != len(ids):
        raise StandardizedValidationError(ActivityErrorMessages.PARTICIPANT_STAKEHOLDER_INVALID)
    return stakeholders


def check_participant_minimum(activity_type, participant_count):
    """The FINAL type with people needs at least one participant."""
    if activity_type in PEOPLE_ACTIVITY_TYPES and participant_count < 1:
        raise StandardizedValidationError(ActivityErrorMessages.PARTICIPANT_REQUIRED)
