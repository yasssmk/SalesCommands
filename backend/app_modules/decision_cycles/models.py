# app_modules/decision_cycles/models.py
"""
Decision Cycle models for sales execution.

DecisionCycle: Container for a buyer-seller decision process
DecisionStep: Individual decision/validation step within a cycle
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from app_modules.core_modules.models import ModuleBaseModel
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from .constants import DecisionStage, DecisionStepStatus


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
    Decision Step model representing a single decision/validation.
    
    Each step belongs to a DecisionCycle and is assigned to one
    of the 5 fixed stages. Steps use a linked-list model for
    ordering and parallelism support.
    
    Parallelism convention:
        If multiple steps share the SAME previous_step AND next_step,
        they are considered parallel steps.
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
        choices=DecisionStage.choices,
        verbose_name=_('Stage'),
        help_text=_('Fixed stage this step belongs to')
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