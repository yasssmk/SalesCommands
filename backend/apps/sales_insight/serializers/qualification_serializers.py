from rest_framework import serializers
from django.utils.translation import gettext_lazy as _

class QualificationFieldsSerializer(serializers.Serializer):
    """
    Serializer for qualification fields shared across entities
    """
    objectives = serializers.JSONField(required=False, allow_null=True)
    compelling_events = serializers.JSONField(required=False, allow_null=True)
    motivations = serializers.JSONField(required=False, allow_null=True)
    key_kpis = serializers.JSONField(required=False, allow_null=True)
    criteria = serializers.JSONField(required=False, allow_null=True)
    pain_points = serializers.JSONField(required=False, allow_null=True)
    implications = serializers.JSONField(required=False, allow_null=True)
    current_tech_stack = serializers.JSONField(required=False, allow_null=True)
    partners = serializers.JSONField(required=False, allow_null=True)
    buying_process = serializers.JSONField(required=False, allow_null=True)
    projects = serializers.JSONField(required=False, allow_null=True)
    budget = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    new_budget_start_date = serializers.DateField(required=False, allow_null=True)

    has_qualification_data = serializers.SerializerMethodField(read_only=True)
    pending_changes_count = serializers.SerializerMethodField(read_only=True)

    def get_has_qualification_data(self, obj):
        """Check if this entity has any qualification data set"""
        qualification_fields = [
            'objectives', 'compelling_events', 'motivations', 'key_kpis',
            'criteria', 'pain_points', 'implications', 'current_tech_stack',
            'partners', 'buying_process', 'projects', 'budget', 
            'new_budget_start_date'
        ]
        
        for field in qualification_fields:
            if getattr(obj, field) not in (None, [], {}):
                return True
        
        return False
    
    def get_pending_changes_count(self, obj):
        """Count pending signals for this entity"""
        from apps.sales_insight.models import Signal
        
        # Determine entity type for filtering
        entity_type = None
        
        if obj.__class__.__name__ == 'Account':
            # For accounts, count all signals related to the account
            return Signal.objects.filter(
                account=obj,
                status='PENDING'
            ).count()
        elif obj.__class__.__name__ == 'AccountOrganizationUnit':
            # For org units, count signals specifically for this org unit
            return Signal.objects.filter(
                org_unit=obj,
                status='PENDING'
            ).count()
        elif obj.__class__.__name__ == 'Contact':
            # For contacts, count signals specifically for this contact
            return Signal.objects.filter(
                contact=obj,
                status='PENDING'
            ).count()
        
        # Default return 0 if entity type is not recognized
        return 0

class QualificationChangeSerializer(serializers.Serializer):
    """
    Simple serializer for displaying field names with user-friendly display names.
    """
    field_name = serializers.CharField()
    field_display_name = serializers.SerializerMethodField()
    
    def get_field_display_name(self, obj):
        """Convert field_name to a user-friendly display name"""
        field_mapping = {
            'objectives': _('Objectives'),
            'compelling_events': _('Compelling Events'),
            'motivations': _('Motivations'),
            'key_kpis': _('Key KPIs'),
            'criteria': _('Decision Criteria'),
            'pain_points': _('Pain Points'),
            'implications': _('Implications'),
            'current_tech_stack': _('Current Tech Stack'),
            'partners': _('Partners'),
            'buying_process': _('Buying Process'),
            'projects': _('Projects'),
            'budget': _('Budget'),
            'new_budget_start_date': _('Budget Start Date'),
            'company_size': _('Company Size'),
            'annual_revenue': _('Annual Revenue'),
            'classification': _('Classification'),
            'type': _('Account Type'),
            'unit_type': _('Unit Type'),
            'job_title': _('Job Title'),
            'influence_level': _('Influence Level'),
        }
        field_name = obj.get('field_name', '')
        return field_mapping.get(field_name, field_name.replace('_', ' ').title())