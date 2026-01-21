# app_modules/decision_cycles/models.py
"""
Decision Cycle models for sales execution.

DecisionCycle: Container for a buyer-seller decision process
DecisionStep: Individual decision/validation step within a cycle
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from app_modules.core_modules.models import ModuleBaseModel
from core.client_scope import ClientScopeManager
from .constants import PipelineStep, DecisionStepStatus, StalledReason, PIPELINE_STEPS_CONFIG, ACTIVITY_OPTIONAL_STEPS


class DecisionCycle(ModuleBaseModel, ClientScopeManager.ModelMixin):
    """
    Decision Cycle model for orchestrating buyer-seller decisions.
    
    A DecisionCycle belongs to a CompanyAccount and contains
    multiple DecisionSteps organized by stages.
    
    Features:
        - Multiple cycles per account supported
        - is_active flag to track displayed cycle
        - Multi-tenant isolation via ClientScopeManager.ModelMixin
    """
    
    # ==========================================================================
    # ACCOUNT RELATIONSHIP
    # ==========================================================================
    
    account = models.ForeignKey(
        'module_accounts.CompanyAccount',
        on_delete=models.CASCADE,
        related_name='decision_cycles',
        verbose_name=_('Account'),
        help_text=_('The company account this decision cycle belongs to')
    )
    
    # ==========================================================================
    # CORE FIELDS
    # ==========================================================================
    
    name = models.CharField(
        max_length=255,
        verbose_name=_('Cycle Name')
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Description')
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is Active'),
        help_text=_('Whether this is the currently displayed cycle for the account')
    )
    
    # ==========================================================================
    # META
    # ==========================================================================
    
    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['account', 'name'],
        index_fields=['name']
    )):
        db_table = 'decision_cycles'
        verbose_name = _('Decision Cycle')
        verbose_name_plural = _('Decision Cycles')
        ordering = ['-is_active', '-updated_at']
        indexes = [
            models.Index(fields=['account'], name='dc_account_idx'),
            models.Index(fields=['is_active'], name='dc_active_idx'),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.account.company_name}"
    
    # ==========================================================================
    # PROPERTIES
    # ==========================================================================
    
    @property
    def estimated_timeline_days(self):
        """
        Calculate estimated remaining days based on expected_end fields.
        
        Returns the number of days from today to the furthest expected_end.
        Returns None if no steps have expected_end set.
        """
        from django.utils import timezone
        
        steps = self.steps.all()
        
        if not steps.exists():
            return 0
        
        # Get the furthest expected_end
        furthest = steps.filter(expected_end__isnull=False).order_by('-expected_end').first()
        
        if not furthest or not furthest.expected_end:
            return None
        
        # Calculate days from today
        today = timezone.now().date()
        delta = (furthest.expected_end - today).days
        return max(0, delta)
    
    @property
    def steps_count(self):
        """Return total number of steps in this cycle."""
        return self.steps.count()
    
    @property
    def validated_steps_count(self):
        """Return number of validated steps."""
        return self.steps.filter(status=DecisionStepStatus.VALIDATED).count()
    
    # ==========================================================================
    # METHODS
    # ==========================================================================
    
    def save(self, *args, **kwargs):
        """
        Override save to ensure only one active cycle per account.
        """
        if self.is_active:
            # Deactivate other cycles for this account
            DecisionCycle.objects.filter(
                account=self.account,
                client_id=self.client_id,
                is_active=True
            ).exclude(pk=self.pk).update(is_active=False)
        
        super().save(*args, **kwargs)


class DecisionStep(ModuleBaseModel, ClientScopeManager.ModelMixin):
    """
    Pipeline Step within a Decision Cycle.
    
    IMPORTANT: Steps are AUTO-CREATED when a Decision Cycle is created.
    Users CANNOT create, delete, or reorder steps manually.
    
    Each step represents a fixed stage in the sales pipeline:
    - Qualification → Technical Fit → Solution Validation → Business Case → Closing → Implementation → Go Live
    
    Steps are AGGREGATORS that derive their data from linked Activities:
    - stakeholders: union of activity contacts
    - start_date: date of first activity
    - expected_end: manually set, but can be auto-adjusted
    - status: inferred from activity outcomes
    - stalled: detected when no activity/next action
    
    Activities are the EXECUTION UNIT - Steps are OBSERVERS.
    """
    
    # ==========================================================================
    # CYCLE RELATIONSHIP
    # ==========================================================================
    
    cycle = models.ForeignKey(
        DecisionCycle,
        on_delete=models.CASCADE,
        related_name='steps',
        verbose_name=_('Decision Cycle')
    )
    
    # ==========================================================================
    # CORE FIELDS (NEW)
    # ==========================================================================
    
    name = models.CharField(
        max_length=255,
        verbose_name=_('Step Name'),
        help_text=_('Name of this decision step')
    )
    
    stage = models.CharField(
        max_length=30,
        choices=PipelineStep.choices,
        verbose_name=_('Pipeline Step'),
        help_text=_('Fixed pipeline step - auto-assigned, cannot be changed by user')
    )

    order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name=_('Display Order'),
        help_text=_('Order in pipeline (1-7), auto-set from PipelineStep config')
    )
    
    status = models.CharField(
        max_length=20,
        choices=DecisionStepStatus.choices,
        default=DecisionStepStatus.NOT_STARTED,
        verbose_name=_('Status')
    )
    
    # ==========================================================================
    # LINKED-LIST FOR ORDERING
    # ==========================================================================
    
    previous_step = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        related_name='next_steps',
        blank=True,
        null=True,
        verbose_name=_('Previous Step'),
        help_text=_('The step that must be completed before this one')
    )

    # ==========================================================================
    # DEAL TEMPORALITY
    # ==========================================================================
    
    start_date = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Start Date'),
        help_text=_('When this step actually started (inferred from first activity)')
    )
    
    expected_end = models.DateField(
        verbose_name=_('Expected End'),
        help_text=_('Expected date for step validation/completion - MANDATORY for timeline')
    )
    
    completed_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Completed At'),
        help_text=_('When this step was validated or rejected')
    )
    
    
    # ==========================================================================
    # LEGACY FIELDS (from BuyingProcessStep)
    # ==========================================================================
    
    stakeholder = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Stakeholder'),
        help_text=_('Role of the person responsible for this step')
    )
    
    standard_department = models.ForeignKey(
        'core_modules.StandardDepartment',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name=_('Department')
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Step Description'),
        help_text=_('What will be done in this step')
    )
    
    goal = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Step Goal'),
        help_text=_('What this step aims to achieve')
    )
    
    influence_score = models.PositiveSmallIntegerField(
        default=0,
        verbose_name=_('Influence Score'),
        help_text=_('Score from 0-100 indicating importance level')
    )
    
    criterias = models.JSONField(
        blank=True,
        null=True,
        default=list,
        verbose_name=_('Criterias'),
        help_text=_('What they will be looking for')
    )
    
    metrics = models.JSONField(
        blank=True,
        null=True,
        default=list,
        verbose_name=_('Metrics'),
        help_text=_('KPIs to measure success')
    )

    # ==========================================================================
    # MANAGER FIELDS
    # ==========================================================================
    
    manager_notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Manager Notes'),
        help_text=_('Internal notes visible only to managers')
    )

    # ==========================================================================
    # DEPARTMENTS RELATIONSHIP (M2M)
    # ==========================================================================
    
    departments = models.ManyToManyField(
        'core_modules.StandardDepartment',
        through='DecisionStepDepartment',
        related_name='decision_steps',
        verbose_name=_('Departments'),
        blank=True
    )
    
    # ==========================================================================
    # CONTACTS RELATIONSHIP
    # ==========================================================================
    
    contacts = models.ManyToManyField(
        'module_contacts.Contact',
        through='DecisionStepContact',
        related_name='decision_steps',
        verbose_name=_('Contacts'),
        blank=True
    )
    
    # ==========================================================================
    # META
    # ==========================================================================
    
    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        index_fields=['name']
    )):
        db_table = 'decision_steps'
        verbose_name = _('Decision Step')
        verbose_name_plural = _('Decision Steps')
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['cycle'], name='ds_cycle_idx'),
            models.Index(fields=['stage'], name='ds_stage_idx'),
            models.Index(fields=['status'], name='ds_status_idx'),
            models.Index(fields=['previous_step'], name='ds_prev_step_idx'),
            models.Index(fields=['expected_end'], name='ds_expected_end_idx'),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_stage_display()})"
    
    # ==========================================================================
    # PROPERTIES
    # ==========================================================================
    
    @property
    def next_step(self):
        """Get the first next step in the chain."""
        return self.next_steps.first()
    
    @property
    def is_current(self):
        """
        Check if this is the current step.
        Current = not VALIDATED/REJECTED and previous_step is VALIDATED (if any).
        """
        if self.status in [DecisionStepStatus.VALIDATED, DecisionStepStatus.REJECTED]:
            return False
        
        if self.previous_step is None:
            return True
        
        return self.previous_step.status == DecisionStepStatus.VALIDATED
    
    @property
    def has_parallel_steps(self):
        """Check if this step has parallel siblings."""
        if not self.previous_step:
            return False
        
        siblings = DecisionStep.objects.filter(
            cycle=self.cycle,
            previous_step=self.previous_step
        ).exclude(pk=self.pk)
        
        return siblings.exists()
    
    # ==========================================================================
    # PIPELINE STEP PROPERTIES
    # ==========================================================================
    
    @property
    def is_activity_optional(self) -> bool:
        """
        Check if this step allows no activities (e.g., Implementation, Go Live).
        
        Activity-optional steps won't trigger stalled detection just because
        they have no activities - they may be client-side or external.
        """
        return self.stage in ACTIVITY_OPTIONAL_STEPS
    
    @property
    def pipeline_step_config(self) -> dict:
        """Get the configuration for this pipeline step."""
        for cfg in PIPELINE_STEPS_CONFIG:
            if cfg['step'] == self.stage:
                return cfg
        return {}
    
    @property
    def step_description(self) -> str:
        """Get the description for this pipeline step from config."""
        return self.pipeline_step_config.get('description', '')
    
    # ==========================================================================
    # STALLED DETECTION (Computed Properties)
    # ==========================================================================
    
    STALLED_THRESHOLD_DAYS = 7
    
    @property
    def is_stalled(self) -> bool:
        """Check if step has no forward momentum."""
        from .constants import StalledReason
        return self.stalled_reason != StalledReason.NONE
    
    @property
    def stalled_reason(self) -> str:
        """
        Determine why this step is stalled (if at all).
        
        Priority order:
        1. EXPECTED_END_PASSED - deadline missed
        2. NO_NEXT_STEP - last activity explicitly marked no next step
        3. NO_ACTIVITY - no activities at all
        4. NO_FUTURE_ACTIVITY - no planned activities
        5. WAITING_TOO_LONG - no activity in 7+ days
        
        Returns StalledReason.NONE if not stalled.
        """
        
        # Terminal statuses are never stalled
        if self.status in [DecisionStepStatus.VALIDATED, DecisionStepStatus.REJECTED]:
            return StalledReason.NONE
        
        today = timezone.now().date()
        
       # Check 1: No activities at all (skip for activity-optional steps)
        if not self.activities.exists():
            if self.is_activity_optional:
                return StalledReason.NONE  # Normal for Implementation/Go Live
            return StalledReason.NO_ACTIVITY
        
        # Get activities for this step
        activities = self.activities.all()
        
        # 2. No activities at all
        if not activities.exists():
            return StalledReason.NO_ACTIVITY
        
        # 3. Check if last completed activity marked no next step
        from app_modules.activities.constants import ActivityStatus
        last_completed = activities.filter(
            status=ActivityStatus.COMPLETED
        ).order_by('-completed_at').first()
        
        if last_completed and last_completed.next_step_agreed is False:
            return StalledReason.NO_NEXT_STEP
        
        # 4. No future activities planned
        if not self.has_future_activity:
            # 5. Check if waiting too long
            if self.days_since_last_activity and self.days_since_last_activity >= self.STALLED_THRESHOLD_DAYS:
                return StalledReason.WAITING_TOO_LONG
            return StalledReason.NO_FUTURE_ACTIVITY
        
        return StalledReason.NONE
    
    @property
    def last_activity_date(self):
        """Get the date of the most recent activity."""
        from django.utils import timezone
        
        last_activity = self.activities.order_by('-updated_at').first()
        if not last_activity:
            return None
        
        # Use completed_at if available, otherwise scheduled_date, otherwise updated_at
        if last_activity.completed_at:
            return last_activity.completed_at.date()
        elif last_activity.scheduled_date:
            return last_activity.scheduled_date
        return last_activity.updated_at.date()
    
    @property
    def days_since_last_activity(self):
        """Calculate days since the last activity."""
        from django.utils import timezone
        
        last_date = self.last_activity_date
        if not last_date:
            return None
        
        today = timezone.now().date()
        return (today - last_date).days
    
    @property
    def has_future_activity(self) -> bool:
        """Check if there are any planned future activities."""
        from django.utils import timezone
        from app_modules.activities.constants import ActivityStatus
        
        today = timezone.now().date()
        
        return self.activities.filter(
            status=ActivityStatus.PLANNED,
            scheduled_date__gte=today
        ).exists()


class DecisionStepContact(ModuleBaseModel, ClientScopeManager.ModelMixin):
    """
    Junction table linking Decision Steps to Contacts.
    
    Allows tracking which contacts are involved in each step.
    """
    
    step = models.ForeignKey(
        DecisionStep,
        on_delete=models.CASCADE,
        related_name='step_contacts',
        verbose_name=_('Step')
    )
    
    contact = models.ForeignKey(
        'module_contacts.Contact',
        on_delete=models.CASCADE,
        related_name='contact_decision_steps',
        verbose_name=_('Contact')
    )
    
    class Meta:
        db_table = 'decision_step_contacts'
        verbose_name = _('Decision Step Contact')
        verbose_name_plural = _('Decision Step Contacts')
        unique_together = ('step', 'contact')
    
    def __str__(self):
        return f"{self.step.name} - {self.contact}"

class DecisionStepDepartment(ModuleBaseModel, ClientScopeManager.ModelMixin):
    """
    Junction table linking Decision Steps to Departments.
    
    Allows multiple departments per step (e.g., IT + Finance in same meeting).
    """
    
    step = models.ForeignKey(
        DecisionStep,
        on_delete=models.CASCADE,
        related_name='step_departments',
        verbose_name=_('Step')
    )
    
    department = models.ForeignKey(
        'core_modules.StandardDepartment',
        on_delete=models.CASCADE,
        related_name='department_decision_steps',
        verbose_name=_('Department')
    )
    
    class Meta:
        db_table = 'decision_step_departments'
        verbose_name = _('Decision Step Department')
        verbose_name_plural = _('Decision Step Departments')
        unique_together = ('step', 'department')
    
    def __str__(self):
        return f"{self.step.name} - {self.department.get_name_display()}"