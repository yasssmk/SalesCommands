# app_modules/ai_pipelines/prompts/prep_call/message_v2.py
"""
Request layer v2 of the Game Plan's AI message — sprint 2 Game Plan, G11
(PO decisions Q2 / Q3 / Q7).

ONE call writes one message per recipient (the pack's `recipients`: the
roster's participants with a contact, capped), each in its recipient's
language. The strict Structured Outputs schema PREP_CALL_MESSAGE_SCHEMA (the
plan's pattern, outline_v2.py): per message {ref, language, subject, body} —
subject is the email's subject, null for a LinkedIn message.

Validated server side by services/prep_call/plan_validator.validate_messages
(refs against the recipients, language, the plan's label / last-name
refusals).
"""

from app_modules.activities.constants import ActivityType

from ..deal_health.diagnostic_v2 import _STR, _arr, _obj  # the strict-schema helpers


__all__ = [
    'MESSAGE_PROMPT_VERSION',
    'MESSAGE_TASK_HEADER',
    'PREP_CALL_MESSAGE_SCHEMA',
    'build_message_request',
]

MESSAGE_PROMPT_VERSION = 'v2'

MESSAGE_TASK_HEADER = 'TASK: Write the messages of the upcoming exchange, one per recipient.'


PREP_CALL_MESSAGE_SCHEMA = {
    'name': 'prep_call_messages_v2',
    'schema': _obj({
        'messages': _arr(_obj({
            'ref': _STR,
            'language': _STR,
            'subject': {'type': ['string', 'null']},
            'body': _STR,
        })),
    }),
}


def build_message_request(input_pack):
    """
    The request layer of the AI message: the task, the recipients with
    their language, the field rules. The schema itself is sent as the strict
    response schema (PREP_CALL_MESSAGE_SCHEMA).

    Args:
        input_pack: dict returned by PrepInputPackAssembler.build() — its
                    `recipients` block.

    Returns:
        str
    """
    activity = input_pack.get('activity') or {}
    is_email = activity.get('type') == ActivityType.EMAIL
    recipients = input_pack.get('recipients') or []
    lines = [
        MESSAGE_TASK_HEADER,
        f"Channel: {'an email' if is_email else 'a LinkedIn message'}.",
        '',
        'RECIPIENTS (one message each — ref exactly as written, in its language):',
        *[f"  {r['ref']} — language: {r['language']}" for r in recipients],
        '',
        'FIELD RULES:',
        '1. messages: exactly one per recipient above, in that order; ref = the '
        "recipient's label, language = the tag given for that recipient.",
        (
            "2. subject: the email's subject line, short and specific."
            if is_email else
            '2. subject: null (a LinkedIn message has no subject).'
        ),
        '3. body: the message itself, written to that recipient by their first '
        'name only — what they said, the value for them, one clear next step. '
        'No placeholder, no signature block.',
        '',
        'Return ONLY the JSON object of the response schema.',
    ]
    return '\n'.join(lines)
