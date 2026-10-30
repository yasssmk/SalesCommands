# app_modules/activities/services/activity_invitations.py
"""
The invited teammates of an activity (Activity.invited_users) — ONE validation
and ONE notification, shared by every creation path: POST /module-activities/
(ActivityCreateSerializer), the update (ActivityUpdateSerializer, notify only)
and POST /module-activities/create-with-entities/ (ActivityCreationService,
Sprint Next steps 5.8h — it used to ignore invited_user_ids).
"""

from django.db import transaction

from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from end_users.models import User

from app_modules.notifications.models import NotificationCategory
from app_modules.notifications.services import NotificationService


def resolve_invited_users(invited_user_ids, client_id):
    """
    The invited User instances for these ids — users of the tenant only.

    Raises:
        StandardizedValidationError when an id is not a user of the tenant
        (the standard create path's refusal).
    """
    invited_users = User.objects.filter(
        id__in=invited_user_ids,
        client_account_id=client_id,
    )
    if invited_users.count() != len(invited_user_ids):
        raise StandardizedValidationError(
            CoreErrorMessages.INVALID_FIELD.format(field='Some invited users not found')
        )
    return list(invited_users)


def notify_invited_users(activity, users, actor):
    """
    Emit an activity-invitation notification to each newly invited user.

    Runs on transaction commit so invitations are only sent once the
    activity (and its M2M) are persisted. The self-notify guard in
    NotificationService.emit() skips the inviter (actor).

    Args:
        activity: The saved Activity instance.
        users:    Iterable of newly invited User instances.
        actor:    The user performing the invitation.
    """
    recipient_ids = [u.id for u in users]
    if not recipient_ids:
        return

    # Primitives captured outside the commit closure for the rich title
    # and the routing payload the frontend deep-links with.
    client_id = activity.client_id
    activity_id = activity.id
    actor_name = actor.get_full_name() or actor.email
    account_name = activity.account.company_name
    title = f"{actor_name} invited you to {activity.title} · {account_name}"

    def _emit():
        for recipient_id in recipient_ids:
            NotificationService.emit(
                client_id=client_id,
                recipient=recipient_id,
                actor=actor,
                category=NotificationCategory.ACTIVITY_INVITATION,
                title=title,
                related_object_type='activity',
                related_object_id=activity_id,
                payload={'activity_id': str(activity_id)},
            )

    transaction.on_commit(_emit)
