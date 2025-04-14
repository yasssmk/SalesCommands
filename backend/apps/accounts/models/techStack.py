# apps/accounts_app/accounts/models.py (or in a new file tech_stack.py if you prefer)

from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core_apps.models import BaseModelApp
from core.client_scope import ClientScopeManager
from .accounts import Account
from apps.core_apps.models import AccountLinkedModel
from apps.signals.services import SignalDataService
from apps.signals.models.tech_stack_signal_model import TechStackSignal

class TechStack(BaseModelApp, AccountLinkedModel, ClientScopeManager.ModelMixin):
    """
    Model to track technologies used by an account.
    """
    tech_name = models.CharField(
        max_length=255,
        verbose_name=_('Technology Name')
    )
    
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Notes')
    )
    
    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints()):
        verbose_name = _('Tech Stack')
        verbose_name_plural = _('Tech Stacks')
        ordering = ['tech_name']
    
    def __str__(self):
        return f"{self.tech_name} ({self.account.company_name})"
    
    def get_evaluation_data(self, field_names=None, department=None, 
                          source_contact=None, min_confirmations=None,
                          include_signal_info=False):
        """
        Get tech stack evaluation data from signals.
        
        Args:
            field_names: Optional list of specific fields to retrieve
            department: Optional department to filter by
            source_contact: Optional contact who provided the information
            min_confirmations: Minimum confirmation count
            include_signal_info: Whether to include detailed signal information
            
        Returns:
            dict: Tech stack evaluation data organized by field
        """
        return SignalDataService.get_tech_stack_data(
            account=self.account,
            tech_stack=self,
            field_names=field_names,
            department=department,
            source_contact=source_contact,
            min_confirmations=min_confirmations,
            include_signal_info=include_signal_info
        )
    
    def get_evaluation_by_department(self):
        """
        Get tech stack evaluation data organized by department.
        
        Returns:
            dict: Tech stack evaluation data organized by department
        """
        # First get all tech stack data by department
        department_data = SignalDataService.get_by_department(
            account=self.account,
            signal_type=TechStackSignal
        )
        
        # Then filter to only include data for this tech stack
        result = {}
        for dept_name, dept_info in department_data.items():
            # Check if there's data for this tech stack
            tech_data = {}
            has_data = False
            
            # Get the actual data
            for field_name, field_values in dept_info['data'].items():
                # For each field, check if there's data for this tech stack
                if field_name in field_values and str(self.id) in field_values:
                    tech_data[field_name] = field_values[str(self.id)]
                    has_data = True
            
            if has_data:
                result[dept_name] = {
                    'department_id': dept_info['department_id'],
                    'department_name': dept_info['department_name'],
                    'data': tech_data
                }
        
        return result
    
    def get_purpose(self):
        """
        Get the purpose of this tech stack from signals.
        
        Returns:
            str: Purpose of the tech stack
        """
        data = self.get_evaluation_data(field_names=['purpose'])
        return data.get('purpose', [])
    
    def get_pros_and_cons(self):
        """
        Get pros and cons for this tech stack from signals.
        
        Returns:
            dict: Pros and cons for the tech stack
        """
        data = self.get_evaluation_data(field_names=['pros', 'cons'])
        return {
            'pros': data.get('pros', []),
            'cons': data.get('cons', [])
        }
    
    def get_costs(self):
        """
        Get cost information for this tech stack from signals.
        
        Returns:
            list: Cost information
        """
        data = self.get_evaluation_data(field_names=['costs'])
        return data.get('costs', [])