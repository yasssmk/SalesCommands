# # apps/sales_insight/serializers/signal_summary_serializer.py
# from rest_framework import serializers
# from ..models import Signal
# from apps.core_apps.serializers import AccountLinkedSerializerMixin

# class SignalSummarySerializer(AccountLinkedSerializerMixin, serializers.ModelSerializer):
#     """
#     Simplified serializer for signal summary in analysis response.
#     """
#     category_label = serializers.SerializerMethodField()
#     entity_type_label = serializers.SerializerMethodField()
#     field_display_name = serializers.SerializerMethodField()
    
#     class Meta:
#         model = Signal
#         fields = [
#             'id', 'account', 'category', 'category_label', 
#             'entity_type', 'entity_type_label',
#             'field_name', 'field_display_name',
#             'value'
#         ]
    
#     def get_category_label(self, obj):
#         return obj.get_category_display()
    
#     def get_entity_type_label(self, obj):
#         return obj.get_entity_type_display()
    
#     def get_field_display_name(self, obj):
#         """Convert field_name to a user-friendly display name"""
#         field_mapping = {
#             'type': 'Account Type',
#             'classification': 'Account Classification',
#             'company_size': 'Company Size',
#             'annual_revenue': 'Annual Revenue',
#             'objectives': 'Business Objectives',
#             'motivations': 'Motivations',
#             'metrics': 'Key Metrics',
#             'pain_points': 'Pain Points',
#             'implications': 'Implications',
#             'tech_stack': 'Technology Stack',
#             'budget_authority': 'Budget Authority'
#         }
#         return field_mapping.get(obj.field_name, obj.field_name.replace('_', ' ').title())
    