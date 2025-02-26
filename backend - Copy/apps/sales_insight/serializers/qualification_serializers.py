from rest_framework import serializers
from apps.sales_insight.models import QualificationChange
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
        """Count pending qualification changes for this entity"""        
        # Determine entity_type based on the model class
        entity_type = 'account'
        if obj.__class__.__name__ == 'AccountOrganizationUnit':
            entity_type = 'org_unit'
        elif obj.__class__.__name__ == 'Contact':
            entity_type = 'contact'
        
        return QualificationChange.objects.filter(
            entity_type=entity_type,
            entity_id=obj.id,
            status='pending'
        ).count()

class QualificationChangeSerializer(serializers.ModelSerializer):
    """
    Serializer for qualification changes
    """
    created_by_name = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField()
    field_display_name = serializers.SerializerMethodField()
    
    class Meta:
        model = QualificationChange
        fields = [
            'id', 'entity_type', 'entity_id', 'field_name', 'field_display_name',
            'old_value', 'new_value', 'status', 'created_at', 'created_by',
            'created_by_name', 'approved_by', 'approved_by_name', 'approved_at',
            'source'
        ]
        read_only_fields = fields
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return f"{obj.created_by.first_name} {obj.created_by.last_name}"
        return None
    
    def get_approved_by_name(self, obj):
        if obj.approved_by:
            return f"{obj.approved_by.first_name} {obj.approved_by.last_name}"
        return None
    
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
        return field_mapping.get(obj.field_name, obj.field_name.replace('_', ' ').title())

class ApproveChangesSerializer(serializers.Serializer):
    """
    Serializer for approving or rejecting qualification changes
    """
    changes = serializers.ListField(child=serializers.DictField())
    
    def validate_changes(self, value):
        """Validate that each change has the required fields"""
        if not value:
            raise serializers.ValidationError(_("No changes provided"))
        
        for i, change in enumerate(value):
            if 'change_id' not in change:
                raise serializers.ValidationError(_(f"Change at index {i} is missing 'change_id'"))
            if 'action' not in change:
                raise serializers.ValidationError(_(f"Change at index {i} is missing 'action'"))
            if change.get('action') not in ['approve', 'reject']:
                raise serializers.ValidationError(_(f"Invalid action '{change.get('action')}' at index {i}"))
        
        return value

class ProcessAIDataSerializer(serializers.Serializer):
    """
    Serializer for processing AI-generated data
    """
    ai_data = serializers.JSONField()
    source = serializers.CharField(required=False, default="ai_analysis")
    
    def validate_ai_data(self, value):
        """Validate that the AI data has the required structure"""
        if not isinstance(value, dict):
            raise serializers.ValidationError(_("AI data must be a JSON object"))
        
        # Check for required top-level keys
        if 'accountInfo' not in value:
            raise serializers.ValidationError(_("AI data is missing 'accountInfo'"))
        if 'insights' not in value:
            raise serializers.ValidationError(_("AI data is missing 'insights'"))
        
        return value