from django.db import models
from django.conf import settings
from apps.core_apps.models import BaseModelApp,AccountLinkedModel, SignalAwareMixin
from core.client_scope import ClientScopeManager
from apps.sales_insight.models  import QualificationModel
from django.utils.translation import gettext_lazy as _
from apps.core_apps.models import StandardDepartment
from django.utils import timezone


class AccountOrganizationUnit(BaseModelApp, ClientScopeManager.ModelMixin, AccountLinkedModel, QualificationModel, SignalAwareMixin):
    class UnitType(models.TextChoices):
        DEPARTMENT = 'DEPARTMENT', _('Department')
        DIVISION = 'DIVISION', _('Division')
        TEAM = 'TEAM', _('Team')

    organization_name = models.CharField(
        max_length=255, 
        verbose_name=_('Organization Name'),
    )
    
    unit_type = models.CharField(
        max_length=50,
        choices=UnitType.choices,
        verbose_name=_('Unit Type'),
    )

    standard_department = models.ForeignKey(
        StandardDepartment,
        on_delete=models.PROTECT,
        default=1,
        related_name='organization_units',
        verbose_name=_('Standard Department')
    )

    parent_organization_unit = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        related_name='child_organization_units', 
        blank=True, 
        null=True
    )
    
    estimated_employee_count = models.IntegerField(
        blank=True, 
        null=True
    )

    metadata = models.JSONField(
        blank=True, 
        null=True
    )

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['account', 'organization_name'],
        index_fields=['organization_name']
    )):
        verbose_name = _('Organization Unit')
        db_table = 'Organization_Unit'
        ordering = ['-created_at', 'organization_name']
        indexes = [
            models.Index(fields=['account']),
            models.Index(fields=['parent_organization_unit'])
        ]

    def update_qualification_field(self, field_name, new_value, user, signal=None):
        """
        Enhanced update method for qualification fields that tracks signal information
        
        Args:
            field_name (str): Field name to update
            new_value: New value for the field
            user (User): User making the update
            signal (Signal, optional): Signal driving this update
        """
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
        
        # Create history entry
        history_entry = {
            'old_value': current_value,
            'new_value': new_value,
            'changed_at': timezone.now().isoformat(),
            'changed_by': str(user.id) if user else None,
        }
        
        # Add signal data if provided
        if signal:
            history_entry.update({
                'source': 'signal',
                'signal_id': str(signal.id),
                'signal_category': signal.category,
                'signal_confidence': signal.confidence,
                'confirmation_count': signal.confirmation_count
            })
            
            # Also track in signal_metadata
            self.track_signal_update(signal, field_name, current_value, new_value)
        
        # Add to historical data
        self.historical_data[field_name].append(history_entry)
        
        # Save the model
        self.save(user=user)
        
        return True
    
    def get_qualification_data(self, include_signal_info=False):
        """
        Get all qualification data for this org unit with optional signal information
        
        Args:
            include_signal_info (bool): Whether to include signal source information
            
        Returns:
            dict: All qualification fields with optional signal metadata
        """
        qualification_fields = [
            'objectives', 'compelling_events', 'motivations', 'key_kpis',
            'criteria', 'pain_points', 'implications', 'current_tech_stack',
            'partners', 'buying_process', 'projects', 'budget', 'new_budget_start_date'
        ]
        
        result = {}
        
        for field in qualification_fields:
            value = getattr(self, field)
            result[field] = value
            
            if include_signal_info and value is not None:
                # Add signal information if available
                signals = self.get_related_signals(
                    field_name=field,
                    include_expired=True
                )
                
                # Only include if we have signals
                if any(s.exists() for s in signals.values()):
                    signal_info = {}
                    
                    for status, queryset in signals.items():
                        if queryset.exists():
                            signal_info[status] = [{
                                'id': s.id,
                                'category': s.category,
                                'source': s.source,
                                'created_at': s.created_at,
                                'confirmation_count': s.confirmation_count,
                                'confidence': s.confidence,
                                'potential_value': s.potential_value
                            } for s in queryset]
                            
                    result[f"{field}_signals"] = signal_info
                    
                # Add signal metadata from the model
                metadata = self.get_field_signal_metadata(field)
                if metadata:
                    result[f"{field}_metadata"] = metadata
                    
        return result
    
    def get_profile_data(self, include_signal_info=False):
        """
        Get profile data for this org unit with optional signal information
        
        Args:
            include_signal_info (bool): Whether to include signal source information
            
        Returns:
            dict: Profile fields with optional signal metadata
        """
        profile_fields = [
            'organization_name', 'unit_type', 'estimated_employee_count'
        ]
        
        result = {}
        
        for field in profile_fields:
            value = getattr(self, field)
            result[field] = value
            
            if include_signal_info:
                # Add signal information if available
                signals = self.get_related_signals(
                    field_name=field,
                    category='PROFILE',
                    include_expired=True
                )
                
                # Only include if we have signals
                if any(s.exists() for s in signals.values()):
                    signal_info = {}
                    
                    for status, queryset in signals.items():
                        if queryset.exists():
                            signal_info[status] = [{
                                'id': s.id,
                                'category': s.category,
                                'source': s.source,
                                'created_at': s.created_at,
                                'confirmation_count': s.confirmation_count
                            } for s in queryset]
                            
                    result[f"{field}_signals"] = signal_info
                    
        return result
    
