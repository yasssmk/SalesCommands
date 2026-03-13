# app_modules/activities/models.py
"""
Activity model for Activities module.

Represents operational execution of sales work:
- Meetings, calls, emails, tasks
- Linked to CompanyAccount, Contact(s), User (owner)
- Optionally linked to DecisionCycle/DecisionStep

Uses UUID primary key for consistency with app_modules.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from app_modules.core_modules.models import ModuleBaseModel
from core.client_scope import ClientScopeManager
from .constants import ActivityType, ActivityStatus, ActivityOutcome


class Activity(ModuleBaseModel, ClientScopeManager.ModelMixin):
    """
    Activity model representing a sales action to be performed.
    
    Features:
        - Linked to CompanyAccount (required)
        - Linked to Contact(s) (optional, M2M)
        - Owned by User (required)
        - Optionally linked to DecisionCycle/DecisionStep
        - Linked-list for sequence navigation (previous/next)
        - Multi-tenant isolation via ClientScopeManager.ModelMixin
    """
    
    # ==========================================================================
    # CORE FIELDS
    # ==========================================================================
    
    title = models.CharField(
        max_length=255,
        verbose_name=_('Title')
    )
    
    activity_type = models.CharField(
        max_length=20,
        choices=ActivityType.choices,
        verbose_name=_('Activity Type')
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Description'),
        help_text=_('Detailed description of the activity')
    )
    
    call_to_action = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name=_('Call to Action'),
        help_text=_('Clear action the salesperson should take (e.g., "Ask about legal review timeline")')
    )
    
    # ==========================================================================
    # STATUS & OUTCOME
    # ==========================================================================
    
    status = models.CharField(
        max_length=20,
        choices=ActivityStatus.choices,
        default=ActivityStatus.PLANNED,
        verbose_name=_('Status')
    )
    
    outcome = models.CharField(
        max_length=30,
        choices=ActivityOutcome.choices,
        blank=True,
        null=True,
        verbose_name=_('Outcome'),
        help_text=_('Result of the activity (only when completed)')
    )
    
    outcome_notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Outcome Notes'),
        help_text=_('Notes about the activity result')
    )

    no_answer_count = models.PositiveSmallIntegerField(
        default=0,
        verbose_name=_('No Answer Count'),
        help_text=_('Number of no-answer attempts recorded on this specific activity.')
    )

    # ==========================================================================
    # NEXT STEP AGREEMENT (Post-Activity)
    # ==========================================================================
    
    next_step_agreed = models.BooleanField(
        null=True,
        blank=True,
        default=None,
        verbose_name=_('Next Step Agreed'),
        help_text=_(
            'True = follow-up activity or step planned, '
            'False = explicitly no next step agreed, '
            'Null = not yet determined'
        )
    )
    
    no_next_step_reason = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('No Next Step Reason'),
        help_text=_('Reason provided when next_step_agreed is False')
    )
    
    # ==========================================================================
    # SCHEDULING
    # ==========================================================================
    
    scheduled_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_('Scheduled Date'),
        help_text=_('Date when the activity is scheduled')
    )
    
    scheduled_time = models.TimeField(
        blank=True,
        null=True,
        verbose_name=_('Scheduled Time'),
        help_text=_('Time when the activity is scheduled')
    )
    
    due_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_('Due Date'),
        help_text=_('Deadline for completing the activity')
    )
    
    completed_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Completed At'),
        help_text=_('When the activity was completed')
    )
    
    # ==========================================================================
    # RELATIONSHIPS - ACCOUNT & CONTACTS
    # ==========================================================================
    
    account = models.ForeignKey(
        'module_accounts.CompanyAccount',
        on_delete=models.CASCADE,
        related_name='activities',
        verbose_name=_('Account'),
        help_text=_('The company account this activity is for')
    )
    
    contacts = models.ManyToManyField(
        'module_contacts.Contact',
        related_name='activities',
        blank=True,
        verbose_name=_('Contacts'),
        help_text=_('Contacts involved in this activity')
    )
    
    # ==========================================================================
    # RELATIONSHIPS - OWNERSHIP
    # ==========================================================================
    
    owner = models.ForeignKey(
        'end_users.User',
        on_delete=models.CASCADE,
        related_name='module_owned_activities',
        verbose_name=_('Owner'),
        help_text=_('User responsible for this activity')
    )

    invited_users = models.ManyToManyField(
        'end_users.User',
        related_name='module_invited_activities',
        blank=True,
        verbose_name=_('Invited Users'),
        help_text=_('Internal users invited to participate in this activity')
    )
    
    # ==========================================================================
    # RELATIONSHIPS - DECISION CYCLE (OPTIONAL)
    # ==========================================================================
    
    decision_cycle = models.ForeignKey(
        'decision_cycles.DecisionCycle',
        on_delete=models.SET_NULL,
        related_name='activities',
        blank=True,
        null=True,
        verbose_name=_('Decision Cycle'),
        help_text=_('Decision cycle this activity contributes to')
    )
    
    decision_step = models.ForeignKey(
        'decision_cycles.DecisionStep',
        on_delete=models.SET_NULL,
        related_name='activities',
        blank=True,
        null=True,
        verbose_name=_('Decision Step'),
        help_text=_('Specific decision step this activity is linked to')
    )

    # ==========================================================================
    # RELATIONSHIPS - CAMPAIGN (OPTIONAL)
    # ==========================================================================

    campaign = models.ForeignKey(
        'module_campaigns.Campaign',
        on_delete=models.SET_NULL,
        related_name='activities',
        blank=True,
        null=True,
        verbose_name=_('Campaign'),
        help_text=_('Campaign that generated this activity')
    )

    campaign_account = models.ForeignKey(
        'module_campaigns.CampaignAccount',
        on_delete=models.SET_NULL,
        related_name='activities',
        blank=True,
        null=True,
        verbose_name=_('Campaign Account'),
        help_text=_('Specific campaign-account pivot this activity belongs to')
    )

    campaign_contact = models.ForeignKey(
        'module_campaigns.CampaignContact',
        on_delete=models.SET_NULL,
        related_name='activities',
        blank=True,
        null=True,
        verbose_name=_('Campaign Contact'),
        help_text=_('Contact-scoped campaign pivot this activity belongs to')
    )

    sequence_position = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        verbose_name=_('Sequence Position'),
        help_text=_('Position in the campaign sequence (1-based)')
    )

    min_delay_days = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        verbose_name=_('Minimum Delay Days'),
        help_text=_('Minimum days to wait after previous activity completion before scheduling this one')
    )

    sequence_variant = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_('Sequence Variant'),
        help_text=_('Variant used to generate this activity (STANDARD, WITHOUT_PHONE, etc.)')
    )

    is_callback_followup = models.BooleanField(
        default=False,
        verbose_name=_('Is Callback Follow-up'),
        help_text=_(
            'True when this activity was created in response to a CALLBACK_REQUESTED outcome. '
            'Used to surface only this activity in the PAUSED playlist section while the '
            'campaign account is in CALLBACK_PENDING status.'
        )
    )

    
    # ==========================================================================
    # LINKED LIST (PREVIOUS/NEXT ACTIVITY)
    # ==========================================================================
    # DEPRECATED: These fields are kept for backward compatibility with
    # standalone activities (not linked to a Decision Cycle).
    # 
    # For activities linked to a Decision Cycle, use the calculated sequence
    # from ActivitySequenceService.get_sequence_context() instead.
    # The sequence is calculated dynamically based on:
    #   1. decision_step.order (pipeline position)
    #   2. COALESCE(scheduled_date, due_date)
    #   3. scheduled_time
    #   4. created_at (fallback)
    #
    # These fields will be removed in a future migration once all activities
    # are migrated to use Decision Cycles.
    # ==========================================================================
    
    previous_activity = models.OneToOneField(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='next_activity_rel',
        verbose_name=_('Previous Activity (DEPRECATED)'),
        help_text=_('DEPRECATED: Use sequence_context for activities in a cycle. '
                    'Manual linking only for standalone activities.')
    )
    
    next_activity = models.OneToOneField(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='previous_activity_rel',
        verbose_name=_('Next Activity (DEPRECATED)'),
        help_text=_('DEPRECATED: Use sequence_context for activities in a cycle. '
                    'Manual linking only for standalone activities.')
    )
    
    # ==========================================================================
    # FUTURE FIELDS (STUBS FOR IA/CAMPAIGN)
    # ==========================================================================
    
    transcript = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Transcript'),
        help_text=_('Call transcript or email content for AI analysis')
    )
    
    preparation_notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Preparation Notes'),
        help_text=_('AI-generated preparation notes (future feature)')
    )
    
    # ==========================================================================
    # META
    # ==========================================================================
    
    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=[],
        index_fields=['title']
    )):
        db_table = 'module_activities'
        verbose_name = _('Activity')
        verbose_name_plural = _('Activities')
        ordering = ['-scheduled_date', '-created_at']
        indexes = [
            models.Index(fields=['account'], name='act_account_idx'),
            models.Index(fields=['owner'], name='act_owner_idx'),
            models.Index(fields=['status'], name='act_status_idx'),
            models.Index(fields=['activity_type'], name='act_type_idx'),
            models.Index(fields=['scheduled_date'], name='act_scheduled_idx'),
            models.Index(fields=['due_date'], name='act_due_date_idx'),
            models.Index(fields=['decision_step'], name='act_step_idx'),
            models.Index(fields=['previous_activity'], name='act_prev_idx'),
            models.Index(fields=['next_activity'], name='act_next_idx'),
            models.Index(fields=['campaign', 'status', 'scheduled_date'], name='act_camp_status_sched_idx'),
            models.Index(
                fields=['decision_cycle', 'decision_step', 'scheduled_date', 'scheduled_time', 'created_at'],
                name='act_sequence_order_idx'
            ),
            models.Index(fields=['campaign'], name='act_campaign_idx'),
            models.Index(fields=['campaign_account'], name='act_camp_account_idx'),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.account.company_name}"
    
    # ==========================================================================
    # PROPERTIES
    # ==========================================================================
    
    @property
    def is_overdue(self):
        """Check if activity is overdue."""
        if self.status in [ActivityStatus.COMPLETED, ActivityStatus.CANCELLED]:
            return False
        if self.due_date:
            return self.due_date < timezone.now().date()
        return False
    
    @property
    def is_scheduled(self):
        """Check if activity has a scheduled date/time."""
        return self.scheduled_date is not None
    
    @property
    def has_previous(self):
        """
        Check if activity has a previous activity in sequence.
        
        DEPRECATED: For activities in a Decision Cycle, use
        ActivitySequenceService.get_sequence_context() instead.
        This property only checks the manual previous_activity field.
        """
        return self.previous_activity is not None
    
    @property
    def has_next(self):
        """
        Check if activity has a next activity in sequence.
        
        DEPRECATED: For activities in a Decision Cycle, use
        ActivitySequenceService.get_sequence_context() instead.
        This property only checks the manual next_activity field.
        """
        return self.next_activity is not None
    
    # ==========================================================================
    # METHODS
    # ==========================================================================
    
    def complete(self, outcome=None, notes=None, user=None):
        """
        Mark activity as completed.

        Step status is NOT updated here — it is derived automatically
        by StepStatusDerivationService from activity data on read.

        Args:
            outcome: ActivityOutcome choice
            notes: Optional outcome notes
            user: User completing the activity
        """
        self.status = ActivityStatus.COMPLETED
        self.completed_at = timezone.now()

        if outcome:
            self.outcome = outcome
        if notes:
            self.outcome_notes = notes

        self.save(user=user)
    
    
    def cancel(self, notes=None, user=None):
        """
        Cancel the activity.
        
        Args:
            notes: Optional cancellation reason
            user: User cancelling the activity
        """
        self.status = ActivityStatus.CANCELLED
        
        if notes:
            self.outcome_notes = notes
        
        self.save(user=user)