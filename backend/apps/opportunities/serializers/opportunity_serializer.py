# apps/opportunities/serializers/opportunity_serializer.py

from rest_framework import serializers
from apps.opportunities.models import Opportunity
from apps.accounts.models import Contact, Account
from core.exceptions import StandardizedValidationError
from apps.core_apps.serializers import AccountLinkedSerializerMixin
from core.client_scope import ClientScopeManager


class OpportunitySerializer(AccountLinkedSerializerMixin,ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """Serializer for the core Opportunity model"""
    
    # Read-only fields for display
    account_name = serializers.CharField(source='account.company_name', read_only=True)
    contact_name = serializers.SerializerMethodField(read_only=True)
    deal_owner_name = serializers.SerializerMethodField(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    opportunity_type_display = serializers.CharField(source='get_opportunity_type_display', read_only=True)
    days_open = serializers.SerializerMethodField(read_only=True)
    
    # Write fields that accept IDs
    contact_id = serializers.PrimaryKeyRelatedField(
        queryset=Contact.objects.all(),
        source='contact',
        write_only=True
    )
    
    class Meta:
        model = Opportunity
        fields = [
            'id',
            'title',
            'description',
            
            # Type and Status
            'opportunity_type',
            'opportunity_type_display',
            'status',
            'status_display',
            
            # Relationships - Read
            'account_name',
            'contact_name',
            'deal_owner_name',
            
            # Relationships - Write
            'account',
            'contact_id',
            'deal_owner',
            
            # Dates
            'date_open',
            'expected_close_date',
            'closed_date',
            'days_open',
            
            # Metadata
            'notes',
            'created_at',
            'updated_at',
            'created_by',
            'updated_by'
        ]
        read_only_fields = [
            'id',
            'date_open',
            'closed_date',
            'days_open',
            'created_at',
            'updated_at',
            'created_by',
            'updated_by'
        ]
    
    def get_contact_name(self, obj):
        """Get the full name of the contact"""
        if obj.contact:
            return f"{obj.contact.first_name} {obj.contact.last_name}"
        return None
    
    def get_deal_owner_name(self, obj):
        """Get the full name of the deal owner"""
        if obj.deal_owner:
            return f"{obj.deal_owner.first_name} {obj.deal_owner.last_name}"
        return None
    
    def get_days_open(self, obj):
        """Get the number of days the opportunity has been open"""
        return obj.get_days_open()
    
    def validate(self, data):
        """Validate opportunity data"""
        # Call parent validation first
        data = super().validate(data)
        
        # Check if contact belongs to account
        contact = data.get('contact')
        account = data.get('account', self.instance.account if self.instance else None)
        
        if contact and account and contact.account != account:
            raise StandardizedValidationError(
                "Contact must belong to the specified account",
                field_name="contact_id"
            )
        
        # Validate expected close date against current date
        if 'expected_close_date' in data:
            from django.utils import timezone
            if data['expected_close_date'] < timezone.now().date():
                raise StandardizedValidationError(
                    "Expected close date cannot be in the past",
                    field_name="expected_close_date"
                )
        
        return data
    
    def create(self, validated_data):
        """Create a new opportunity"""
        # Pop the user from context if available
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['created_by'] = request.user
            validated_data['updated_by'] = request.user
        
        opportunity = Opportunity.objects.create(**validated_data)
        
        # Create history entry for opportunity creation
        opportunity.create_history_entry('CREATED', "Opportunity created")
        
        return opportunity
    
    def update(self, instance, validated_data):
        """Update an existing opportunity"""
        # Pop the user from context if available
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['updated_by'] = request.user
        
        # Check for status change
        old_status = instance.status
        new_status = validated_data.get('status', old_status)
        
        # Update the opportunity
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        
        # Create history entry for status change
        if old_status != new_status:
            status_display = dict(Opportunity.OpportunityStatus.choices).get(new_status, new_status)
            instance.create_history_entry(
                'STATUS_CHANGE',
                f"Status changed to {status_display}"
            )
        
        return instance


class OpportunityListSerializer(serializers.ModelSerializer):
    """Simplified serializer for opportunity lists"""
    
    account_name = serializers.CharField(source='account.company_name', read_only=True)
    contact_name = serializers.SerializerMethodField(read_only=True)
    deal_owner_name = serializers.SerializerMethodField(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    days_open = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Opportunity
        fields = [
            'id',
            'title',
            'opportunity_type',
            'status',
            'status_display',
            'account_name',
            'contact_name',
            'deal_owner_name',
            'date_open',
            'expected_close_date',
            'closed_date',
            'days_open',
            'created_at'
        ]
    
    def get_contact_name(self, obj):
        """Get the full name of the contact"""
        if obj.contact:
            return f"{obj.contact.first_name} {obj.contact.last_name}"
        return None
    
    def get_deal_owner_name(self, obj):
        """Get the full name of the deal owner"""
        if obj.deal_owner:
            return f"{obj.deal_owner.first_name} {obj.deal_owner.last_name}"
        return None
    
    def get_days_open(self, obj):
        """Get the number of days the opportunity has been open"""
        return obj.get_days_open()