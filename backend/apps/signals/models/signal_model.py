# apps/signals/models/signal_model.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp, AccountLinkedModel
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from ..validators import FieldValidators

class Signal(BaseModelApp, AccountLinkedModel, ClientScopeManager.ModelMixin):
    """
    Signal model that tracks valuable sales insights from AI analysis 
    and other sources to support sales prioritization and action planning.
    """

    class Category(models.TextChoices):
        PROFILE = 'PROFILE', _('Profile Data')
        PROCESS = 'PROCESS', _('Process')
        TECH_STACK = 'TECH_STACK', _('Technology Stack')
        QUALIFICATION = 'QUALIFICATION', _('Qualification')
        PROJECT = 'PROJECT', _('Project')
    
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        APPROVED = 'APPROVED', _('Approved')
        REJECTED = 'REJECTED', _('Rejected')
        APPLIED = 'APPLIED', _('Applied')
        MERGED = 'MERGED', _('Merged')
    
    class EntityType(models.TextChoices):
        ACCOUNT = 'ACCOUNT', _('Account')
        ACCOUNT_PRODUCT = 'ACCOUNT_PRODUCT', _('Account Product Detail')
    
    class Field(models.TextChoices):
        # Account qualification fields (from call transcript analysis)
        COMPANY_SIZE = 'company_size', _('Company Size')
        ANNUAL_REVENUE = 'annual_revenue', _('Annual Revenue')
        OBJECTIVES = 'objectives', _('Objectives')
        MOTIVATIONS = 'motivations', _('Motivations')
        METRICS = 'metrics', _('Metrics')
        PAIN_POINTS = 'pain_points', _('Pain Points')
        IMPLICATIONS = 'implications', _('Implications')
        
        # Tech stack fields (from call transcript analysis)
        PURPOSE = 'purpose', _('Purpose')
        PROS = 'pros', _('Pros')
        CONS = 'cons', _('Cons')
        ANNUAL_COSTS = 'annual_costs', _('Annual Costs')
        RENEWAL_DATE = 'renewal_date', _('Renewal Date')
        START_YEAR_OF_USAGE = 'start_year_of_usage', _('Start year of Usage')
    
    # Define valid field categories (which fields belong to which categories)
    FIELD_CATEGORIES = {
        # Profile fields
        Field.COMPANY_SIZE: Category.PROFILE,
        Field.ANNUAL_REVENUE: Category.PROFILE,
        
        # Qualification fields
        Field.OBJECTIVES: Category.QUALIFICATION,
        Field.MOTIVATIONS: Category.QUALIFICATION,
        Field.METRICS: Category.QUALIFICATION,
        Field.PAIN_POINTS: Category.QUALIFICATION,
        Field.IMPLICATIONS: Category.QUALIFICATION,
        
        # Tech stack fields
        Field.PURPOSE: Category.TECH_STACK,
        Field.PROS: Category.TECH_STACK,
        Field.CONS: Category.TECH_STACK,
        Field.ANNUAL_COSTS: Category.TECH_STACK,
        Field.RENEWAL_DATE: Category.TECH_STACK,
        Field.START_YEAR_OF_USAGE: Category.TECH_STACK,
    }
    
      # Signal classification
    category = models.CharField(
        max_length=20, 
        choices=Category.choices,
        verbose_name=_('Signal Category')
    )
    
    # Field & Value
    entity_type = models.CharField(
        max_length=20, 
        choices=EntityType.choices,
        verbose_name=_('Entity Type')
    )
    
    field_name = models.CharField(
        max_length=100,
        verbose_name=_('Field Name')
    )
    
    value = models.JSONField(
        verbose_name=_('Signal Value')
    )
    
    # Status and lifecycle
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_('Signal Status')
    )

    # Contact attribution (who provided this information)
    source_contact = models.ForeignKey(
        'accounts.Contact',
        on_delete=models.SET_NULL,
        related_name='provided_signals',
        null=True,
        blank=True,
        verbose_name=_('Source Contact')
    )
    
    source_department = models.ForeignKey(
        'core_apps.StandardDepartment',
        on_delete=models.SET_NULL,
        related_name='department_signals',
        null=True,
        blank=True,
        verbose_name=_('Source Department')
    )
    
    # lifecycle management
    confirmation_count = models.PositiveIntegerField(default=1, verbose_name=_('Confirmation Count'))
    last_confirmed_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Last Confirmed At'))
    merged_into = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        related_name='merged_from_signals',
        null=True,
        blank=True,
        verbose_name=_('Merged Into Signal')
    )
    
    #Later to connect with activity
    source = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_('Data Source')
    )
    
    # Dates and timestamps
    revisit_date = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Revisit Date')
    )
    
    applied_date = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Applied Date')
    )
    
    # Product alignment
    product_alignment = models.ForeignKey(
        'products.Product',
        related_name='aligned_signals',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_('Aligned Products')
    )
    
    contact = models.ForeignKey(
        'accounts.Contact',
        on_delete=models.CASCADE,
        related_name='signals',
        null=True,
        blank=True,
        verbose_name=_('Contact')
    )
    
    account_product_relationship = models.ForeignKey(
        'accounts.AccountProductRelationship',
        on_delete=models.CASCADE,
        related_name='signals',
        null=True,
        blank=True,
        verbose_name=_('Account Product relationship')
    )
    
    # Approval tracking
    approved_by = models.ForeignKey(
        'end_users.User',
        on_delete=models.SET_NULL,
        related_name='approved_signals',
        null=True,
        blank=True,
        verbose_name=_('Approved By')
    )
    
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Approved At')
    )
    
    # Parent signal for clustering related signals
    parent_signal = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        related_name='child_signals',
        null=True,
        blank=True,
        verbose_name=_('Parent Signal')
    )

    metadata = models.JSONField(
        verbose_name=_('Metadata'),
        help_text=_('Additional metadata for validations, history, and context'),
        null=True,
        blank=True
    )

    def clean(self):
        """Minimal clean method with basic validations"""
        super().clean()
        
        # Set source department from contact if available and not set
        if self.source_contact and not self.source_department and hasattr(self.source_contact, 'standard_department'):
            self.source_department = self.source_contact.standard_department

    @classmethod
    def get_signals_for_field(cls, account, field_name, status=None, department=None, min_confirmations=None):
        """
        Get signals for a specific field with filtering options.
        
        Args:
            account: Account to get signals for
            field_name: Field name to filter by
            status: Optional status to filter by
            department: Optional department to filter by
            min_confirmations: Minimum number of confirmations
            
        Returns:
            QuerySet of signals matching the criteria
        """
        # Base query for this account and field
        query = cls.objects.filter(
            account=account,
            field_name=field_name
        )
        
        # Add status filter if provided
        if status:
            if isinstance(status, list):
                query = query.filter(status__in=status)
            else:
                query = query.filter(status=status)
        else:
            # Default to approved/applied signals
            query = query.filter(status__in=[cls.Status.APPROVED, cls.Status.APPLIED])
        
        # Add department filter if provided
        if department:
            query = query.filter(source_department=department)
        
        # Add confirmation count filter if provided
        if min_confirmations:
            query = query.filter(confirmation_count__gte=min_confirmations)
        
        return query
    
    def get_effective_status(self):
        """Calculate the effective status based on age and signal type"""
        from ..services.signal_lifecycle_service import SignalLifecycleService
        return SignalLifecycleService.get_effective_status(self)
        
    def is_effectively_expired(self):
        """Check if the signal is effectively expired"""
        return self.get_effective_status() == "EXPIRED"

    def __str__(self):
        return f"{self.get_category_display()}: {self.field_name} [{self.get_status_display()}]"