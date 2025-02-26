from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core_apps.models import BaseModelApp
from core.client_scope import ClientScopeManager

class QualificationModel(models.Model):
    """
    Abstract model that contains common qualification fields
    used across Account, OrgUnit, and Contact models.
    """
    # List fields (typically strings)
    objectives = models.JSONField(blank=True, null=True, verbose_name=_('Objectives'))
    compelling_events = models.JSONField(blank=True, null=True, verbose_name=_('Compelling Events'))
    motivations = models.JSONField(blank=True, null=True, verbose_name=_('Motivations'))
    key_kpis = models.JSONField(blank=True, null=True, verbose_name=_('Key KPIs'))
    criteria = models.JSONField(blank=True, null=True, verbose_name=_('Criteria'))
    pain_points = models.JSONField(blank=True, null=True, verbose_name=_('Pain Points'))
    implications = models.JSONField(blank=True, null=True, verbose_name=_('Implications'))
    
    # Complex structures
    current_tech_stack = models.JSONField(blank=True, null=True, verbose_name=_('Current Tech Stack'))
    partners = models.JSONField(blank=True, null=True, verbose_name=_('Partners'))
    buying_process = models.JSONField(blank=True, null=True, verbose_name=_('Buying Process'))
    projects = models.JSONField(blank=True, null=True, verbose_name=_('Projects'))
    
    # Numeric fields
    budget = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True, default=0, verbose_name=_('Budget'))
    new_budget_start_date = models.DateField(blank=True, null=True, verbose_name=_('New Budget Start Date'))
    
    # Historical data tracking
    historical_data = models.JSONField(blank=True, null=True, verbose_name=_('Historical Data'))
    
    class Meta:
        abstract = True
        
    def update_qualification_field(self, field_name, new_value, user):
        """
        Update a qualification field and record change history
        
        Args:
            field_name (str): Field name to update
            new_value: New value for the field
            user (User): User making the update
        """
        from django.utils import timezone
        
        # Get current value
        current_value = getattr(self, field_name)
        
        # Update the field
        setattr(self, field_name, new_value)
        
        # Initialize historical_data if it doesn't exist
        if not self.historical_data:
            self.historical_data = {}
        
        # Initialize field history if it doesn't exist
        if field_name not in self.historical_data:
            self.historical_data[field_name] = []
        
        # Add to historical data
        self.historical_data[field_name].append({
            'old_value': current_value,
            'new_value': new_value,
            'changed_at': timezone.now().isoformat(),
            'changed_by': str(user.id) if user else None
        })
        
        # Save the model
        self.save(user=user)

class QualificationChange(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Model to track changes to qualification fields and their approval status.
    """
    ENTITY_TYPES = (
        ('account', _('Account')),
        ('org_unit', _('Organization Unit')),
        ('contact', _('Contact')),
    )
    
    STATUS_CHOICES = (
        ('pending', _('Pending')),
        ('approved', _('Approved')),
        ('rejected', _('Rejected')),
    )
    
    entity_type = models.CharField(max_length=20, choices=ENTITY_TYPES, verbose_name=_('Entity Type'))
    entity_id = models.UUIDField(verbose_name=_('Entity ID'))
    field_name = models.CharField(max_length=50, verbose_name=_('Field Name'))
    old_value = models.JSONField(blank=True, null=True, verbose_name=_('Old Value'))
    new_value = models.JSONField(blank=True, null=True, verbose_name=_('New Value'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name=_('Status'))
    approved_by = models.ForeignKey(
        'end_users.User', 
        on_delete=models.SET_NULL, 
        related_name='approved_qualification_changes', 
        blank=True, 
        null=True, 
        verbose_name=_('Approved By')
    )
    approved_at = models.DateTimeField(blank=True, null=True, verbose_name=_('Approved At'))
    source = models.CharField(max_length=50, blank=True, null=True, verbose_name=_('Data Source'))
    
    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints()):
        verbose_name = _('Qualification Change')
        verbose_name_plural = _('Qualification Changes')
        db_table = 'qualification_changes'
        ordering = ['-created_at']