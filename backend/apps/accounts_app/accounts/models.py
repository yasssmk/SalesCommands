from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from phonenumber_field.modelfields import PhoneNumberField
from core.models import ContactDetailsMixin
from apps.core_apps.models import BaseModelApp, SignalAwareMixin
from core.client_scope import ClientScopeManager
from django.utils.translation import gettext_lazy as _
from end_users.models import User, Team, Organization
from apps.sales_insight.models.qualification_model import QualificationModel
from core.error_messages import AccountErrorMessages
from core.exceptions import StandardizedValidationError, AuthenticationFailed, StandardizedPermissionDenied
from django.utils import timezone


# Personalization: Users could add new choices 
class AccountType(models.TextChoices):
    CLIENT = 'CLIENT', _('Client')
    PROSPECT = 'PROSPECT', _('Prospect')
    PARTNER = 'PARTNER', _('Partner')
    VENDOR = 'VENDOR', _('Vendor')
    OTHER = 'OTHER', _('Other')

class AccountClassification(models.TextChoices):
    SMB = 'SMB', _('Small and Medium Business')
    MIDMARKET = 'MIDMARKET', _('Mid-Market')
    ENTERPRISE = 'ENTERPRISE', _('Enterprise')
    STARTUP = 'STARTUP', _('Startup')
    NONPROFIT = 'NONPROFIT', _('Non-Profit')

class Account(BaseModelApp, ClientScopeManager.ModelMixin, ContactDetailsMixin, QualificationModel, SignalAwareMixin):

    company_name = models.CharField(
        max_length=255, 
        verbose_name=_('Company Name'),
    )

    industry = models.CharField(max_length=100, blank=True, null=True, verbose_name=_('Industry'))

    type = models.CharField(max_length=50, choices=AccountType.choices, blank=True, null=True, verbose_name=_('Account Type'))
    classification = models.CharField(max_length=50, choices=AccountClassification.choices, blank=True, null=True, verbose_name=_('Account Classification'))
    
    company_size = models.CharField(blank=True, null=True, verbose_name=_('Number of Employees'))
    annual_revenue = models.CharField(blank=True, null=True, verbose_name=_('Annual Revenue'))


    #Relationships   
    parent_company = models.ForeignKey('self', on_delete=models.SET_NULL, related_name='direct_child_companies', blank=True, null=True, verbose_name=_('Parent Company'))
    account_owner = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, verbose_name=_('Account Owner'))
    team_owner = models.ForeignKey(Team, on_delete=models.SET_NULL, blank=True, null=True, verbose_name=_('Team Owner'))


    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['company_name', 'city', 'country'],
        index_fields=['company_name']
    )):
        db_table = 'company_accounts'
        verbose_name = _('Account')
        verbose_name_plural = _('Accounts')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account_owner']),
            models.Index(fields=['team_owner']),
        ]
    
    def clean(self):
        """
        Validate the model
        """
        super().clean()
        
        # Ensure account_owner user belongs to team_owner if both are set
        if self.account_owner and self.team_owner:
            if self.account_owner.team != self.team_owner:
                raise StandardizedValidationError(AccountErrorMessages.TEAM_MISMATCH, field_name="account_owner")

    def save(self, *args, **kwargs):
        # If account_owner is set but team isn't, automatically set the team
        if self.account_owner and not self.team_owner:
            self.team_owner= self.account_owner.team
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.company_name} ({self.get_type_display()})"

    def get_full_hierarchy(self):
        """
        Retrieve the full hierarchy of parent and child companies.
        """
        hierarchy = {
            'parents': [],
            'children': list(self.direct_child_companies.all())
        }
        
        current = self
        while current.parent_company:
            hierarchy['parents'].append(current.parent_company)
            current = current.parent_company
        
        return hierarchy
    
    @staticmethod
    def get_account_types():
        return [{'value': choice[0], 'label': choice[1]} for choice in AccountType.choices]

    @staticmethod
    def get_account_classifications():
        return [{'value': choice[0], 'label': choice[1]} for choice in AccountClassification.choices]
    
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
        Get all qualification data for this account with optional signal information
        
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
                # Add signal metadata if available
                signals = self.get_related_signals(field_name=field, include_expired=True)
                
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
        Get profile data for this account with optional signal information
        
        Args:
            include_signal_info (bool): Whether to include signal source information
            
        Returns:
            dict: Profile fields with optional signal metadata
        """
        profile_fields = [
            'company_name', 'industry', 'type', 'classification',
            'company_size', 'annual_revenue'
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
