# app_modules/decision_cycles/models.py
"""
Decision Cycle models for sales execution.

DecisionCycle: Container for a buyer-seller decision process
DecisionStep: Individual decision/validation step within a cycle
"""

from decimal import Decimal

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from app_modules.core_modules.models import ModuleBaseModel
from core.client_scope import ClientScopeManager
from .constants import PipelineStep, DecisionStepStatus, CycleOutcome, PIPELINE_STEPS_CONFIG, ACTIVITY_OPTIONAL_STEPS


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
    # OWNERSHIP
    # ==========================================================================
    
    owner = models.ForeignKey(
        'end_users.User',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='owned_decision_cycles',
        verbose_name=_('Owner'),
        help_text=_('User who owns this decision cycle (defaults to creator)')
    )
    
    
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

    source_campaign = models.ForeignKey(
        'module_campaigns.Campaign',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_cycles',
        verbose_name=_('Source Campaign'),
        help_text=_(
            'Campaign that triggered the creation of this decision cycle. '
            'Set during campaign-to-cycle conversion flow.'
        )
    )

    # ==========================================================================
    # FINANCIAL
    # ==========================================================================

    estimated_value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name=_('Estimated Value'),
        help_text=_('Estimated deal value for pipeline/revenue tracking in campaigns')
    )
    
    # ==========================================================================
    # CYCLE OUTCOME (two-layer architecture)
    # ==========================================================================
    
    outcome = models.CharField(
        max_length=20,
        choices=CycleOutcome.choices,
        blank=True,
        null=True,
        verbose_name=_('Outcome'),
        help_text=_(
            'Explicit cycle-level strategic decision. '
            'WON/LOST/NOT_QUALIFIED = terminal (PLANNED cancelled). '
            'ON_HOLD = paused (PLANNED kept). '
            'null = cycle still open, status derived from steps.'
        )
    )
    
    outcome_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_('Outcome Date'),
        help_text=_('Date when the outcome decision was made (auto-set on close)')
    )
    
    outcome_notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Outcome Notes'),
        help_text=_('Reason or context for the outcome. Required for ON_HOLD.')
    )
    
    hold_until = models.DateField(
        blank=True,
        null=True,
        verbose_name=_('Hold Until'),
        help_text=_('Resume date when cycle is ON_HOLD. Required for ON_HOLD only.')
    )

    # READINESS
    readiness_score = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        default=None,
        verbose_name=_('Readiness Score'),
        help_text=_('Auto-computed score (0-100) from validated signals and deal evidence.')
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
            # C5 perf — DC counts by outcome + won-value in a period. outcome
            # first (equality/group-by), outcome_date second (range window).
            models.Index(fields=['outcome', 'outcome_date'], name='dc_outcome_date_idx'),
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
    def total_deal_value(self):
        """The cycle's deal amount: Σ of its DealProduct lines.

        THE single source of truth for a DC amount. The formula lives once, in
        SQL, in services/deal_value_sql.py — this accessor never re-implements
        it, so a single-cycle read and a mass roll-up can never disagree.

        Cost: FREE on a queryset annotated with ``annotate_deal_value()`` (the
        annotation is read straight off the instance); ONE query otherwise.
        Never read this in a loop over many cycles — annotate instead.

        Distinct from ``estimated_value``, which is a manual, independent field
        (its reconciliation with this roll-up is TD-75).
        """
        from .services.deal_value_sql import DEAL_VALUE_ALIAS, deal_value_for

        annotated = getattr(self, DEAL_VALUE_ALIAS, None)
        if annotated is not None:
            return annotated
        return deal_value_for(self)

    @property
    def steps_count(self):
        """Return total number of steps in this cycle."""
        return self.steps.count()
    
    @property
    def validated_steps_count(self):
        """Number of VALIDATED steps, from the DERIVED status (step status is
        computed from activity data, never stored).

        Costs ~2 queries per cycle (steps + activities prefetch) so derive_bulk
        reads activities from cache; bounded per paginated page.
        """
        from .services.step_status_derivation_service import StepStatusDerivationService

        steps = list(self.steps.prefetch_related('activities').all())
        if not steps:
            return 0
        derived = StepStatusDerivationService().derive_bulk(steps)
        return sum(
            1 for st in derived.values()
            if st.get('status') == DecisionStepStatus.VALIDATED
        )
    
    # ==========================================================================
    # METHODS
    # ==========================================================================
    
    def save(self, *args, **kwargs):
        """
        Override save to enforce two invariants:
          1. a DecisionCycle is never persisted ownerless — if no owner is set,
             fall back to the creator (the ``save(user=)`` actor, else the
             already-set ``created_by``). This is a creation-time safety net;
             ``owner`` stays freely reassignable afterwards. No account-owner
             default: owner is always the creator, never the account owner.
          2. only one active cycle per account.
        """
        # 1. Owner safety net (no DB query: resolve via ids where possible).
        if self.owner_id is None:
            actor = kwargs.get('user')
            if actor is not None and not getattr(actor, 'is_anonymous', False):
                self.owner = actor
            elif self.created_by_id is not None:
                self.owner_id = self.created_by_id

        # 2. Single active cycle per account.
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
    
    # Step status is DERIVED on read from activity data (see
    # services/step_status_derivation_service.py and services/derivation_sql.py);
    # there is no stored status column.

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
        blank=True,
        null=True,
        verbose_name=_('Expected End'),
        help_text=_('Expected date for step completion - set by user after cycle creation')
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
        Whether this step is the cycle's CURRENT step: the first step (by order)
        whose DERIVED status is not VALIDATED.

        This is the single definition shared with annotate_cycle_state
        (services/derivation_sql.py) and CycleAggregationService._compute_progress
        — is_current CONSUMES that service instead of re-deriving the rule, so
        there is one source of truth (Voie A). The stored `status` column is
        never updated and must not be read here.

        Derived on read from activity data; triggers queries (acceptable for the
        detail view) and never writes (Q6). Returns False when the cycle has no
        steps or every step is VALIDATED (no current step).
        """
        if not self.cycle_id:
            return False

        from .services import CycleAggregationService, StepStatusDerivationService

        steps = list(
            DecisionStep.objects.filter(cycle_id=self.cycle_id).prefetch_related('activities')
        )
        if not steps:
            return False

        derived = StepStatusDerivationService().derive_bulk(steps)
        current_order = CycleAggregationService._compute_progress(
            steps, derived
        ).get('current_step_order')
        return current_order is not None and current_order == self.order
    
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
    # STALLED DETECTION & STATUS DERIVATION
    # ==========================================================================
    # Step status is DERIVED automatically — never written manually.
    # See: services/step_status_derivation_service.py (status from activities)
    # See: services/stalled_detection_service.py (stalled diagnostics)
    #
    # These services are called by serializers at read time.
    # No @property on the model — avoids N+1 queries in list views.
    # ==========================================================================
    
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
        """Check if there are any planned future activities.
        
        A PLANNED activity is by definition a future activity,
        regardless of its scheduled_date. Activities without
        a scheduled_date or with a past scheduled_date but still
        in PLANNED status are still pending execution.
        """
        from app_modules.activities.constants import ActivityStatus
        
        return self.activities.filter(
            status=ActivityStatus.PLANNED
        ).exists()
    

    # ==========================================================================
    # AGGREGATION PROPERTIES (Computed from linked Activities)
    # ==========================================================================
    # These properties derive data automatically from activities.
    # They trigger DB queries — acceptable for detail view (single instance).
    # For list/timeline views, use annotations & prefetch (see views.py).
    # ==========================================================================

    @property
    def aggregated_contacts(self):
        """
        Union of all contacts from linked activities.
        Returns QuerySet of Contact objects involved in this step's activities.
        READ-ONLY / computed — not stored in DecisionStepContact.
        """
        from app_modules.contacts.models import Contact

        return Contact.objects.filter(
            activities__decision_step=self
        ).distinct()

    @property
    def aggregated_departments(self):
        """
        Union of departments from all activity contacts' standard_department.
        Derived automatically from contacts linked to this step's activities.
        """
        from app_modules.core_modules.models import StandardDepartment

        return StandardDepartment.objects.filter(
            module_contacts__activities__decision_step=self
        ).distinct()

    @property
    def effective_start_date(self):
        """
        Date of the FIRST completed activity linked to this step.
        Uses completed_at date, fallback to scheduled_date.
        Different from start_date which is set on status change.
        This is the REAL observed start.
        """
        from app_modules.activities.constants import ActivityStatus

        first_completed = self.activities.filter(
            status=ActivityStatus.COMPLETED
        ).order_by('completed_at').first()

        if first_completed:
            if first_completed.completed_at:
                return first_completed.completed_at.date()
            return first_completed.scheduled_date

        # Fallback: first activity by scheduled_date (even if not completed)
        first_activity = self.activities.order_by('scheduled_date').exclude(
            scheduled_date__isnull=True
        ).first()

        if first_activity:
            return first_activity.scheduled_date

        return None

    @property
    def effective_end_date(self):
        """
        Expected end derived from activities:
        - If PLANNED activities exist: scheduled_date or due_date of the LAST planned activity
        - If no planned activities: completed_at of the LAST completed activity
        This complements the manual expected_end field.
        """
        from app_modules.activities.constants import ActivityStatus
        from django.db.models.functions import Coalesce
        from django.db.models import F

        # Priority 1: Last planned activity date
        last_planned = self.activities.filter(
            status=ActivityStatus.PLANNED
        ).exclude(
            scheduled_date__isnull=True, due_date__isnull=True
        ).order_by(
            Coalesce('due_date', 'scheduled_date').desc()
        ).first()

        if last_planned:
            return last_planned.due_date or last_planned.scheduled_date

        # Priority 2: Last completed activity date
        last_completed = self.activities.filter(
            status=ActivityStatus.COMPLETED,
            completed_at__isnull=False
        ).order_by('-completed_at').first()

        if last_completed:
            return last_completed.completed_at.date()

        return None

    @property
    def all_contacts(self):
        """
        Merged view: manually-added step contacts + aggregated activity contacts.
        Deduplicated by contact.id.
        Returns QuerySet of Contact objects — this is what the frontend
        should display as "Stakeholders".
        """
        from app_modules.contacts.models import Contact
        from django.db.models import Q

        manual_contact_ids = self.step_contacts.values_list('contact_id', flat=True)
        activity_contact_ids = Contact.objects.filter(
            activities__decision_step=self
        ).values_list('id', flat=True)

        all_ids = set(manual_contact_ids) | set(activity_contact_ids)

        if not all_ids:
            return Contact.objects.none()

        return Contact.objects.filter(id__in=all_ids).select_related('standard_department')

    @property
    def all_departments(self):
        """
        Merged view: manually-added step departments + aggregated activity contact departments.
        Deduplicated by department.id.
        """
        from app_modules.core_modules.models import StandardDepartment

        manual_dept_ids = self.step_departments.values_list('department_id', flat=True)
        activity_dept_ids = StandardDepartment.objects.filter(
            module_contacts__activities__decision_step=self
        ).values_list('id', flat=True)

        all_ids = set(manual_dept_ids) | set(activity_dept_ids)

        if not all_ids:
            return StandardDepartment.objects.none()

        return StandardDepartment.objects.filter(id__in=all_ids)

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


class DealHealthSnapshot(ModuleBaseModel, ClientScopeManager.ModelMixin):
    """
    Point-in-time diagnostic snapshot produced by the deal-health
    AI pipeline. Stores the structured LLM output (7 dimensions,
    gaps, levers, themes) for a given DecisionCycle.
    """

    decision_cycle = models.ForeignKey(
        DecisionCycle,
        on_delete=models.CASCADE,
        related_name='health_snapshots',
        verbose_name=_('Decision Cycle'),
    )

    diagnostic = models.JSONField(
        verbose_name=_('Diagnostic'),
        help_text=_(
            'Structured JSON output: dimensions, gaps, levers, themes.'
        ),
    )

    snapshot_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Snapshot Date'),
    )

    pipeline_run = models.ForeignKey(
        'module_ai_pipelines.AIPipelineRun',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deal_health_snapshots',
        verbose_name=_('Pipeline Run'),
    )

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        index_fields=[],
    )):
        db_table = 'deal_health_snapshots'
        verbose_name = _('Deal Health Snapshot')
        verbose_name_plural = _('Deal Health Snapshots')
        ordering = ['-snapshot_date']
        indexes = [
            models.Index(
                fields=['decision_cycle', '-snapshot_date'],
                name='dhs_cycle_date_idx',
            ),
        ]

    def __str__(self):
        return f"Snapshot {self.snapshot_date} — {self.decision_cycle.name}"


class DealProduct(ModuleBaseModel, ClientScopeManager.ModelMixin):
    """
    Line item linking a ProductCatalog entry to a DecisionCycle
    with quantity and optional price override.
    """

    decision_cycle = models.ForeignKey(
        DecisionCycle,
        on_delete=models.CASCADE,
        related_name='deal_products',
        verbose_name=_('Decision Cycle'),
    )

    product_catalog_entry = models.ForeignKey(
        'product_catalog.ProductCatalog',
        on_delete=models.PROTECT,
        related_name='deal_products',
        verbose_name=_('Product Catalog Entry'),
    )

    quantity = models.IntegerField(
        default=1,
        verbose_name=_('Quantity'),
    )

    unit_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name=_('Unit Price Override'),
        help_text=_('Overrides the catalog default_unit_price when set.'),
    )

    discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name=_('Discount %'),
        help_text=_('Percentage discount applied to this line (0–100).'),
    )

    notes = models.TextField(
        blank=True,
        default='',
        verbose_name=_('Notes'),
    )

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['decision_cycle', 'product_catalog_entry'],
    )):
        db_table = 'deal_products'
        verbose_name = _('Deal Product')
        verbose_name_plural = _('Deal Products')

    def __str__(self):
        return (
            f"{self.product_catalog_entry.name} x{self.quantity}"
            f" — {self.decision_cycle.name}"
        )

    @property
    def line_total(self):
        price = self.unit_price
        if price is None and self.product_catalog_entry_id:
            price = self.product_catalog_entry.default_unit_price
        if price is None:
            return 0
        # Decimal arithmetic throughout — note Decimal('0.00') is falsy, so
        # guard with an explicit Decimal to avoid float contamination.
        discount = self.discount_percent if self.discount_percent is not None else Decimal('0')
        discount_factor = Decimal('1') - discount / Decimal('100')
        return self.quantity * price * discount_factor


class ManagerNote(ModuleBaseModel, ClientScopeManager.ModelMixin):
    """
    Manager note attached to a DecisionCycle.

    Forms a chronological thread of notes authored by managers/admins.
    Author is tracked via ModuleBaseModel.created_by (auto-set by save(user=)).
    """

    decision_cycle = models.ForeignKey(
        DecisionCycle,
        on_delete=models.CASCADE,
        related_name='manager_notes',
        verbose_name=_('Decision Cycle'),
    )

    content = models.TextField(
        verbose_name=_('Content'),
    )

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        index_fields=[],
    )):
        db_table = 'manager_notes'
        verbose_name = _('Manager Note')
        verbose_name_plural = _('Manager Notes')
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['decision_cycle', '-created_at'],
                name='mn_cycle_date_idx',
            ),
        ]

    def __str__(self):
        return f"Note by {self.created_by_id} — {self.decision_cycle.name}"