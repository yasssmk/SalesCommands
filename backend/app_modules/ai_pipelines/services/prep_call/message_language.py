# app_modules/ai_pipelines/services/prep_call/message_language.py
"""
The recipients of a Game Plan message and their language — sprint 2 Game
Plan, G11 (PO decisions Q2 / Q3 / Q7).

  * recipients (Q2): the participants of the activity's roster (G4,
    llm_people.activity_roster) that have a contact — their own, or their
    stakeholder's; a stakeholder without contact gets no message. In the
    roster's order, at most PREP_CALL_MESSAGE_RECIPIENTS_MAX (Q7).
  * language (Q3): resolve_message_language(participant) reads the
    stakeholder profile's communication_language that already exists — no
    new detector:
      - a manual value (MANUAL, or an AI value a user edited —
        LLM_MODIFIED) -> PROFILE;
      - an AI value (LLM_EXTRACTED) -> EXCHANGES;
      - otherwise (no stakeholder, no value) -> 'en', DEFAULT.
  * overrides: the language chosen in the UI for this generation, per
    recipient (its ref = its roster label). The recipient is resolved server
    side; an unknown one — not a recipient of THIS activity, whatever it is —
    is a standard 400, never guessed. The tag itself is validated by the
    decision_cycles validator (stakeholder_service.validate_language_tag).
"""

from app_modules.ai_pipelines.constants import (
    PREP_CALL_DEFAULT_MESSAGE_LANGUAGE,
    PREP_CALL_MESSAGE_RECIPIENTS_MAX,
    PrepCallLanguageSource,
)
from app_modules.signals.constants import SignalSource


__all__ = ['message_recipients', 'resolve_message_language']

_MANUAL_SOURCES = frozenset({SignalSource.MANUAL, SignalSource.LLM_MODIFIED})
_AI_SOURCES = frozenset({SignalSource.LLM_EXTRACTED})


def resolve_message_language(participant):
    """{'language', 'source'} of a roster participant's message (Q3)."""
    entry = participant.get('language_entry') or {}
    value = entry.get('value')
    if isinstance(value, str) and value.strip():
        if entry.get('source') in _MANUAL_SOURCES:
            return {'language': value, 'source': PrepCallLanguageSource.PROFILE.value}
        if entry.get('source') in _AI_SOURCES:
            return {'language': value, 'source': PrepCallLanguageSource.EXCHANGES.value}
    return {'language': PREP_CALL_DEFAULT_MESSAGE_LANGUAGE,
            'source': PrepCallLanguageSource.DEFAULT.value}


def message_recipients(people, overrides=None):
    """
    The recipients of the activity's message.

    Args:
        people:    ActivityRoster (PrepInputPackAssembler.people).
        overrides: [{'ref', 'language'}] — languages already validated as
                   tags; each ref must be a recipient.

    Returns:
        (recipients, omitted) — recipients: [{'ref', 'first_name',
        'contact_id', 'language', 'source'}] ('contact_id' server side only);
        omitted: how many participants with a contact were left out by the
        cap.

    Raises:
        StandardizedValidationError — an override for an unknown recipient.
    """
    with_contact = [p for p in people.participants if p.get('recipient_contact_id')]
    kept = with_contact[:PREP_CALL_MESSAGE_RECIPIENTS_MAX]
    recipients = [
        {
            'ref': p['label'],
            'first_name': people.roster.first_name_for(p['identity']) or '',
            'contact_id': p['recipient_contact_id'],
            **resolve_message_language(p),
        }
        for p in kept
    ]
    by_ref = {r['ref']: r for r in recipients}
    for override in overrides or []:
        recipient = by_ref.get(override['ref'])
        if recipient is None:
            from core.error_messages import AIPipelineErrorMessages
            from core.exceptions import StandardizedValidationError
            raise StandardizedValidationError(
                AIPipelineErrorMessages.PREP_CALL_UNKNOWN_RECIPIENT.format(ref=override['ref'])
            )
        recipient['language'] = override['language']
        recipient['source'] = PrepCallLanguageSource.OVERRIDE.value
    return recipients, len(with_contact) - len(kept)
