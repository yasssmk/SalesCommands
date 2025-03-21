# apps/account/serializers/apr_serializer.py

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from apps.core_apps.serializers import AccountLinkedSerializerMixin, HistoricalTrackingSerializerMixin
from apps.accounts.models import Contact, AccountProductRelationship, RevenueType
from apps.accounts.serializers.contact_serializer import ContactSerializer
from apps.products.models import Product, Pricing
from apps.products.serializers import ProductSerializer, PricingSerializer


class AccountProductRelationshipSerializer(AccountLinkedSerializerMixin, HistoricalTrackingSerializerMixin, 
                                          ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for AccountProductRelationship with nested relations and calculated fields.
    """

    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        source='product',
        queryset=Product.objects.all(),
        write_only=True
    )
    
    selected_pricing = PricingSerializer(read_only=True)
    selected_pricing_id = serializers.PrimaryKeyRelatedField(
        source='selected_pricing',
        queryset=Pricing.objects.all(),
        write_only=True,
        required=False,
        allow_null=True
    )
    
    target_contacts = ContactSerializer(many=True, read_only=True)
    target_contact_ids = serializers.PrimaryKeyRelatedField(
        source='target_contacts',
        queryset=Contact.objects.all(),
        write_only=True,
        many=True,
        required=False
    )

    # Analysis data fields
    objectives_alignment = serializers.JSONField(required=False, allow_null=True)
    pain_points_coverage = serializers.JSONField(required=False, allow_null=True)
    economic_impact = serializers.JSONField(required=False, allow_null=True)
    contribution_to_coverage = serializers.JSONField(required=False, allow_null=True)
    
    # Analysis summary fields
    objectives_coverage_percent = serializers.SerializerMethodField()
    pain_points_coverage_percent = serializers.SerializerMethodField()
    overall_coverage_percent = serializers.SerializerMethodField()
    has_analysis_data = serializers.SerializerMethodField()

    # Calculated fields
    potential_revenue_formatted = serializers.SerializerMethodField()
    revenue_label = serializers.SerializerMethodField()

    class Meta:
        model = AccountProductRelationship
        fields = [
            'id',
            'account',
            'product',
            'product_id',
            'selected_pricing',
            'selected_pricing_id',
            'target_contacts',
            'target_contact_ids',
            'estimated_units',
            'potential_revenue',
            'potential_revenue_formatted',
            'revenue_type',
            'revenue_label',
            'ai_relevance_score',
            'objectives_alignment',
            'pain_points_coverage',
            'economic_impact',
            'contribution_to_coverage',
            'objectives_coverage_percent',
            'pain_points_coverage_percent',
            'overall_coverage_percent',
            'has_analysis_data',
            'last_analysis_date',
            'notes',
            'historical_data',
            'buying_process',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id', 
            'potential_revenue',
            'historical_data',
            'created_at',
            'updated_at',
            'last_analysis_date'
        ]

    def validate(self, data):
        """Custom validation for the serializer."""
        data = super().validate(data) 
        
        # Additional product and pricing validations
        client_id = self._get_client_id_from_context()
        
        # Validate client scoping for product
        product = data.get('product')
        if product and str(product.client_id) != str(client_id):
            raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
        
        # Validate selected pricing belongs to product
        pricing = data.get('selected_pricing')
        if pricing:
            if not product:
                product = self.instance.product if self.instance else None
                
            if not product or pricing.product_id != product.id:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field="Selected pricing must belong to the selected product"
                    )
                )
            
            if str(pricing.client_id) != str(client_id):
                raise StandardizedValidationError(CoreErrorMessages.CLIENT_MISMATCH)
        
        if 'target_contacts' in data:
            account = data.get('account') or self.instance.account
            contacts = data['target_contacts']
            invalid_contacts = [
                contact for contact in contacts 
                if contact.account_id != account.id
            ]
            if invalid_contacts:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field="Target contacts must belong to the account"
                    )
                )
    
        return data
    
    def _assign_default_pricing_if_needed(self, instance=None, validated_data=None):
        """
        If no 'selected_pricing' is provided but 'estimated_units' > 0,
        fetch the first Pricing model from the product and assign it.
        """
        product = validated_data.get('product')
        if not product and instance:
            # If product wasn't updated, use the existing
            product = instance.product

        # If the user didn't explicitly pass a new selected_pricing,
        # see if we currently have one (instance) or not
        new_selected_pricing = validated_data.get('selected_pricing')
        current_pricing = instance.selected_pricing if instance else None
        
        # Determine final selected_pricing after update (or create)
        final_pricing = new_selected_pricing if (new_selected_pricing is not None) else current_pricing
        
        # Determine final estimated_units
        new_estimated_units = validated_data.get('estimated_units')
        final_estimated_units = new_estimated_units if (new_estimated_units is not None) else (
            instance.estimated_units if instance else 0
        )

        # If we STILL don't have a pricing but we do have a positive estimated_units,
        # we attempt to set the first pricing in the product
        if not final_pricing and final_estimated_units > 0:
            pricing_qs = product.pricing_models.filter(client_id=product.client_id)
            default_pricing = pricing_qs.first()
            if not default_pricing:
                # No pricing found for this product
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field=f"No pricing found for product '{product}'"
                    )
                )
            validated_data['selected_pricing'] = default_pricing

    def create(self, validated_data):
        """
        1. Possibly auto-assign default pricing.
        2. Create instance.
        3. Handle M2M target org units.
        """
        
        # Attempt to assign default pricing if none given
        self._assign_default_pricing_if_needed(instance=None, validated_data=validated_data)
        
        instance = super().create(validated_data)

        return instance
    
    def update(self, instance, validated_data):
        """
        1. Possibly auto-assign default pricing if user has removed pricing or changed product.
        2. Track changes before updating.
        3. Update instance.
        4. Handle M2M target org units.
        """

        # Retrieve user from request context
        user = self.context['request'].user if 'request' in self.context else None

        # Track changes for specific fields before updating instance
        for field in ['estimated_units', 'selected_pricing', 'potential_revenue', 'ai_relevance_score']:
            if field in validated_data:
                old_value = getattr(instance, field)
                new_value = validated_data[field]
                if old_value != new_value:
                    instance.track_field_change(field, old_value, new_value, user)

        # Attempt to assign default pricing if none given
        self._assign_default_pricing_if_needed(instance=instance, validated_data=validated_data)

        # Update instance
        instance = super().update(instance, validated_data)

        return instance


    # Method fields for coverage statistics
    # def get_objectives_coverage_percent(self, obj):
    #     """Calculate objectives coverage percentage from stored coverage stats"""
    #     if obj.coverage_stats and 'objectives_coverage_percent' in obj.coverage_stats:
    #         return obj.coverage_stats['objectives_coverage_percent']
    #     return 0
    
    # def get_pain_points_coverage_percent(self, obj):
    #     """Calculate pain points coverage percentage from stored coverage stats"""
    #     if obj.coverage_stats and 'pain_points_coverage_percent' in obj.coverage_stats:
    #         return obj.coverage_stats['pain_points_coverage_percent']
    #     return 0
    
    # def get_overall_coverage_percent(self, obj):
    #     """Calculate overall coverage percentage from stored coverage stats"""
    #     if obj.coverage_stats and 'overall_coverage_percent' in obj.coverage_stats:
    #         return obj.coverage_stats['overall_coverage_percent']
    #     return 0
    
    # def get_has_analysis_data(self, obj):
    #     """Check if APD has any analysis data"""
    #     return bool(obj.objectives_alignment or obj.pain_points_coverage or obj.economic_impact)

    # # Revenue formatting methods
    def get_potential_revenue_formatted(self, obj):
        if obj.selected_pricing:
            return f"{obj.selected_pricing.currency} {obj.potential_revenue:,.2f}"
        return None

    def get_revenue_label(self, obj):
        return obj.get_revenue_type_display()

    def get_objectives_coverage_percent(self, obj):
        try:
            return obj.coverage_stats.get('objectives_coverage_percent', 0) if hasattr(obj, 'coverage_stats') else 0
        except Exception:
            return 0

    def get_pain_points_coverage_percent(self, obj):
        try:
            return obj.coverage_stats.get('pain_points_coverage_percent', 0) if hasattr(obj, 'coverage_stats') else 0
        except Exception:
            return 0

    def get_overall_coverage_percent(self, obj):
        try:
            return obj.coverage_stats.get('overall_coverage_percent', 0) if hasattr(obj, 'coverage_stats') else 0
        except Exception:
            return 0

    def get_has_analysis_data(self, obj):
        try:
            return bool(
                obj.objectives_alignment or 
                obj.pain_points_coverage or 
                obj.economic_impact
            )
        except Exception:
            return False
        
