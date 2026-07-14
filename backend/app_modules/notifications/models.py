# app_modules/notifications/models.py
"""
Notification model for Notifications module.

Represents a single in-app notification targeting one recipient user
within a client (tenant). Uses UUID primary key and follows
ModuleBaseModel patterns.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from app_modules.core_modules.models.moduleBaseModels import ModuleBaseModel
from core.client_scope import ClientScopeManager
from end_users.models import User


class NotificationCategory(models.TextChoices):
    """Category (machine key) driving frontend icon and deep-link routing."""
    MANAGER_NOTE = 'MANAGER_NOTE', _('Manager note added')                 # E1
    ACTIVITY_INVITATION = 'ACTIVITY_INVITATION', _('Activity invitation')   # E2
    DECISION_CYCLE_CREATED = 'DECISION_CYCLE_CREATED', _('Decision cycle created')  # E3
    UNKNOWN_TECH_DETECTED = 'UNKNOWN_TECH_DETECTED', _('Unknown technology detected')  # E4


class NotificationResponseStatus(models.TextChoices):
    """Response state for ACTIONABLE notifications (E2 invitation, E3 handoff).

    null (no value) marks an INFORMATIVE notification (E1 manager note,
    E4 unknown tech) that carries no action. A non-null value marks an
    actionable notification and tracks the recipient's response.
    """
    PENDING = 'PENDING', _('Pending')
    ACCEPTED = 'ACCEPTED', _('Accepted')
    DECLINED = 'DECLINED', _('Declined')


class Notification(ModuleBaseModel, ClientScopeManager.ModelMixin):
    """
    In-app notification for Notifications module.

    Targets a single recipient user within a client. Read state is tracked
    by read_at (null = unread). Deep-linking to the source object is done
    through related_object_type + related_object_id (+ payload for extra
    context), avoiding a cross-tenant generic relation.

    Features:
        - Single recipient user (no broadcast fan-out at the model level)
        - Category machine key for frontend routing
        - Deep-link references to the originating object
        - Multi-tenant isolation via ClientScopeManager.ModelMixin
    """

    # ==========================================================================
    # RECIPIENT
    # ==========================================================================

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name=_('Recipient'),
        help_text=_('User who should see this notification')
    )

    # ==========================================================================
    # CORE FIELDS
    # ==========================================================================

    category = models.CharField(
        max_length=50,
        choices=NotificationCategory.choices,
        verbose_name=_('Category')
    )

    title = models.CharField(
        max_length=255,
        verbose_name=_('Title')
    )

    body = models.TextField(
        blank=True,
        default='',
        verbose_name=_('Body')
    )

    # ==========================================================================
    # DEEP-LINK REFERENCES
    # ==========================================================================

    related_object_type = models.CharField(
        max_length=50,
        blank=True,
        default='',
        verbose_name=_('Related Object Type'),
        help_text=_('Type of the originating object, e.g. decision_cycle')
    )

    related_object_id = models.UUIDField(
        blank=True,
        null=True,
        verbose_name=_('Related Object ID')
    )

    payload = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Payload'),
        help_text=_('Extra context for deep-linking and display')
    )

    # ==========================================================================
    # READ STATE
    # ==========================================================================

    read_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Read At'),
        help_text=_('Timestamp the recipient read this notification; null = unread')
    )

    # ==========================================================================
    # RESPONSE STATE (actionable notifications only)
    # ==========================================================================

    response_status = models.CharField(
        max_length=10,
        choices=NotificationResponseStatus.choices,
        blank=True,
        null=True,
        default=None,
        verbose_name=_('Response Status'),
        help_text=_(
            'Response state for actionable notifications. null = informative '
            '(E1/E4, no action); PENDING/ACCEPTED/DECLINED = actionable (E2/E3)'
        )
    )

    # Categories whose notifications are ACTIONABLE — emitted as PENDING and
    # tracked through the recipient's response. Declared here (not in the
    # service) so adding an actionable category is a one-line change.
    ACTIONABLE_CATEGORIES = frozenset({
        NotificationCategory.ACTIVITY_INVITATION,      # E2 — invitation
        NotificationCategory.DECISION_CYCLE_CREATED,   # E3 — DC handoff
    })

    # ==========================================================================
    # META & METHODS
    # ==========================================================================

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        index_fields=['recipient']
    )):
        db_table = 'module_notifications'
        verbose_name = _('Notification')
        verbose_name_plural = _('Notifications')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client_id'], name='module_notif_client_idx'),
            models.Index(fields=['recipient_id', 'client_id'], name='module_notif_recip_cli_idx'),
            models.Index(fields=['recipient_id', 'read_at'], name='module_notif_recip_read_idx'),
        ]

    def __str__(self):
        return f"{self.get_category_display()} -> {self.recipient_id}"
