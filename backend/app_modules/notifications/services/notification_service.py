# app_modules/notifications/services/notification_service.py
"""
NotificationService — single entry point for emitting notifications.

Emitters never build Notification rows inline; they call emit(), which
centralises the recipient resolution, the self-notification guard, and
the tenant-scoped write. Targets a single recipient user — callers that
need to notify several users call emit() once per recipient.
"""

import logging

from ..models import Notification, NotificationResponseStatus

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Stateless service class for notification emission.

    All public methods are classmethods — no instance needed. The write
    goes through model.save(user=, client_id=) so ModuleBaseModel audit
    fields and client scoping are always enforced.
    """

    @classmethod
    def emit(
        cls,
        *,
        client_id,
        recipient,
        category,
        title,
        body='',
        related_object_type='',
        related_object_id=None,
        payload=None,
        actor=None,
    ):
        """
        Create a single notification for one recipient within a client.

        Args:
            client_id:           Tenant ID the notification belongs to.
            recipient:           Target user — User instance or its id.
            category:            NotificationCategory value.
            title:               Short headline shown in the bell/menu.
            body:                Optional longer text.
            related_object_type: Type of the originating object (deep-link).
            related_object_id:   Id of the originating object (deep-link).
            payload:             Extra context dict for display/deep-linking.
            actor:               User triggering the event — User instance
                                 or id. Used for the self-notification guard
                                 and the created_by audit field.

        Returns:
            The saved Notification, or None when the emission is skipped
            (no recipient, or recipient is the actor).
        """
        recipient_id = getattr(recipient, 'pk', recipient)
        if recipient_id is None:
            return None

        actor_id = getattr(actor, 'pk', actor)
        if actor_id is not None and str(recipient_id) == str(actor_id):
            return None

        # Actionable categories (E2 invitation, E3 handoff) start PENDING;
        # informative ones (E1/E4) stay null. Driven by the model's declared
        # ACTIONABLE_CATEGORIES so this needs no change per new category.
        response_status = (
            NotificationResponseStatus.PENDING
            if category in Notification.ACTIONABLE_CATEGORIES
            else None
        )

        notification = Notification(
            recipient_id=recipient_id,
            category=category,
            title=title,
            body=body,
            related_object_type=related_object_type,
            related_object_id=related_object_id,
            payload=payload if payload is not None else {},
            response_status=response_status,
        )
        # Only a real user instance can set the created_by audit field;
        # an actor passed as a bare id is used solely for the guard above.
        save_user = actor if hasattr(actor, 'pk') else None
        notification.save(client_id=client_id, user=save_user)
        return notification
