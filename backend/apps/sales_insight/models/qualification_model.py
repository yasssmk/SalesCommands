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
        Update a qualification field and record change history.
        
        For absolute fields (like revenue, employee count), the new value replaces the old one.
        For cumulative fields (like objectives, pain points), the new value is merged with existing values.
        
        Args:
            field_name (str): Field name to update
            new_value: New value for the field
            user (User): User making the update
        """
        from django.utils import timezone
        
        # Define which fields are absolute (replace old value) vs cumulative (add to existing)
        absolute_fields = ['budget', 'new_budget_start_date', 'company_size', 'annual_revenue', 'estimated_employee_count']
        cumulative_fields = ['objectives', 'compelling_events', 'motivations', 'key_kpis', 
                            'criteria', 'pain_points', 'implications', 'projects', 'partners']
        
        # Get current value
        current_value = getattr(self, field_name)
        
        # Determine how to update the field based on its type
        if field_name in absolute_fields:
            # For absolute fields, simply replace the old value
            final_value = new_value
        elif field_name in cumulative_fields:
            # For cumulative fields (lists), merge with existing values
            if current_value is None:
                # If no current value, just use the new value
                final_value = new_value
            else:
                # Merge lists without duplicates
                if isinstance(current_value, list) and isinstance(new_value, list):
                    # Convert everything to strings for comparison
                    current_str_set = set(str(item) for item in current_value)
                    new_items = [item for item in new_value if str(item) not in current_str_set]
                    final_value = current_value + new_items
                else:
                    # If not a list, handle as absolute field
                    final_value = new_value
        else:
            # Complex fields like current_tech_stack, buying_process handled as absolute
            final_value = new_value
        
        # Initialize historical_data if it doesn't exist
        if not self.historical_data:
            self.historical_data = {}
        
        # Initialize field history if it doesn't exist
        if field_name not in self.historical_data:
            self.historical_data[field_name] = []
        
        # Only record history if the value actually changed
        if current_value != final_value:
            # Add to historical data
            self.historical_data[field_name].append({
                'old_value': current_value,
                'new_value': final_value,
                'changed_at': timezone.now().isoformat(),
                'changed_by': str(user.id) if user else None
            })
            
            # Update the field
            setattr(self, field_name, final_value)
            
            # Save the model
            self.save(user=user)
            
            return True
        
        return False
