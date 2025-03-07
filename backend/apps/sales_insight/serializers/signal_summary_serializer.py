# apps/sales_insight/serializers/signal_summary_serializer.py
from rest_framework import serializers
from ..models import Signal
from apps.core_apps.serializers import AccountLinkedSerializerMixin

class SignalSummarySerializer(AccountLinkedSerializerMixin, serializers.ModelSerializer):
    """
    Simplified serializer for signal summary in analysis response.
    """
    category_label = serializers.SerializerMethodField()
    entity_type_label = serializers.SerializerMethodField()
    field_display_name = serializers.SerializerMethodField()
    
    # Entity summaries
    org_unit_summary = serializers.SerializerMethodField()
    contact_summary = serializers.SerializerMethodField()
    account_product_detail_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = Signal
        fields = [
            'id', 'account', 'category', 'category_label', 
            'entity_type', 'entity_type_label',
            'field_name', 'field_display_name',
            'value', 'org_unit_summary', 'contact_summary',
            'account_product_detail_summary'
        ]
    
    def get_category_label(self, obj):
        return obj.get_category_display()
    
    def get_entity_type_label(self, obj):
        return obj.get_entity_type_display()
    
    def get_field_display_name(self, obj):
        """Convert field_name to a user-friendly display name"""
        field_mapping = {
            'type': 'Account Type',
            'classification': 'Account Classification',
            'company_size': 'Company Size',
            'annual_revenue': 'Annual Revenue',
            'objectives': 'Business Objectives',
            'compelling_events': 'Compelling Events',
            'motivations': 'Motivations',
            'key_kpis': 'Key KPIs',
            'criteria': 'Decision Criteria',
            'pain_points': 'Pain Points',
            'implications': 'Implications',
            'current_tech_stack': 'Current Technology',
            'buying_process': 'Buying Process',
            'partners': 'Partners',
            'budget': 'Budget',
            'new_budget_start_date': 'Budget Start Date',
            'projects': 'Projects',
            'budget_authority': 'Budget Authority'
        }
        return field_mapping.get(obj.field_name, obj.field_name.replace('_', ' ').title())
    
    def get_org_unit_summary(self, obj):
        if obj.org_unit:
            return {
                'id': obj.org_unit.id,
                'organization_name': obj.org_unit.organization_name,
                'unit_type': obj.org_unit.unit_type
            }
        return None
    
    def get_contact_summary(self, obj):
        if obj.contact:
            return {
                'id': obj.contact.id,
                'name': f"{getattr(obj.contact, 'first_name', '')} {getattr(obj.contact, 'last_name', '')}".strip(),
                'role': getattr(obj.contact, 'job_title', None)
            }
        return None
    
    def get_account_product_detail_summary(self, obj):
        if obj.account_product_detail:
            apd = obj.account_product_detail
            return {
                'id': apd.id,
                'product_name': apd.product.product_name if apd.product else None,
                'estimated_units': apd.estimated_units,
                'potential_revenue': str(apd.potential_revenue)
            }
        return None