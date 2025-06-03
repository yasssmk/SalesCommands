# apps/campaign/serializers/campaign_serializer.py

from rest_framework import serializers
from apps.campaign.models.campaign import Campaign
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages


class CampaignSerializer(serializers.ModelSerializer):
    """Serializer for Campaign model"""
    
    # Read-only fields
    owner_name = serializers.SerializerMethodField(read_only=True)
    campaign_type_display = serializers.CharField(source='get_campaign_type_display', read_only=True)
    sequence_type_display = serializers.SerializerMethodField(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    # Computed fields
    has_sequence = serializers.SerializerMethodField(read_only=True)
    is_call_list = serializers.SerializerMethodField(read_only=True)
    target_summary = serializers.SerializerMethodField(read_only=True)
    has_mixed_targets = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Campaign
        fields = [
            'id',
            'name',
            'description',
            
            # Campaign configuration
            'campaign_type',
            'campaign_type_display',
            'sequence_type',
            'sequence_type_display',
            'has_sequence',
            'is_call_list',
            
            # Ownership
            'owner',
            'owner_name',
            
            # Dates
            'start_date',
            'end_date',
            
            # Status
            'status',
            'status_display',
            
            # Target information
            'target_summary',
            'has_mixed_targets',
            
            # Metadata
            'created_at',
            'updated_at',
            'created_by',
            'updated_by'
        ]
        read_only_fields = [
            'owner_name',
            'campaign_type_display',
            'sequence_type_display',
            'status_display',
            'has_sequence',
            'is_call_list',
            'target_summary',
            'has_mixed_targets',
            'created_at',
            'updated_at',
            'created_by',
            'updated_by'
        ]
    
    def get_owner_name(self, obj):
        """Get the full name of the campaign owner"""
        if obj.owner:
            return f"{obj.owner.first_name} {obj.owner.last_name}"
        return None
    
    def get_sequence_type_display(self, obj):
        """Get display name for sequence type"""
        if obj.sequence_type:
            # Get the display value from choices
            from apps.sequence.sequences.sequence_dispatcher import SequenceDisptacher
            for choice in SequenceDisptacher.SEQUENCE_CHOICES:
                if choice[0] == obj.sequence_type:
                    return choice[1]
            return obj.sequence_type
        return "No Sequence (Call List)"
    
    def get_has_sequence(self, obj):
        """Check if campaign has automated sequences"""
        return obj.has_sequence()
    
    def get_is_call_list(self, obj):
        """Check if campaign is a simple call list"""
        return obj.is_call_list()
    
    def get_target_summary(self, obj):
        """Get summary of targets in the campaign"""
        return obj.get_target_summary()
    
    def get_has_mixed_targets(self, obj):
        """Check if campaign has multiple target types"""
        return obj.has_mixed_targets()
    
    def validate(self, data):
        """Validate campaign data"""
        # Validate dates
        start_date = data.get('start_date', self.instance.start_date if self.instance else None)
        end_date = data.get('end_date', self.instance.end_date if self.instance else None)
        
        if start_date and end_date and end_date < start_date:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATE_RANGE.format(
                    start_date=start_date,
                    end_date=end_date
                )
            )
        
        # Validate sequence_type with campaign_type
        campaign_type = data.get('campaign_type', self.instance.campaign_type if self.instance else None)
        sequence_type = data.get('sequence_type', self.instance.sequence_type if self.instance else None)
        
        # Call list campaigns should not have a sequence
        if campaign_type == Campaign.CampaignType.CALL_LIST and sequence_type is not None:
            raise StandardizedValidationError(
                "Call List campaigns cannot have automated sequences"
            )
        
        return data
    
    def create(self, validated_data):
        """Create a new campaign"""
        # Pop the user from context if available
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['created_by'] = request.user
            validated_data['updated_by'] = request.user
            if 'owner' not in validated_data:
                validated_data['owner'] = request.user
        
        return Campaign.objects.create(**validated_data)
    
    def update(self, instance, validated_data):
        """Update a campaign"""
        # Pop the user from context if available
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['updated_by'] = request.user
        
        # Update the instance
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance


class CampaignListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing campaigns"""
    
    owner_name = serializers.SerializerMethodField(read_only=True)
    campaign_type_display = serializers.CharField(source='get_campaign_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    has_sequence = serializers.SerializerMethodField(read_only=True)
    target_counts = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Campaign
        fields = [
            'id',
            'name',
            'campaign_type',
            'campaign_type_display',
            'has_sequence',
            'owner',
            'owner_name',
            'start_date',
            'end_date',
            'status',
            'status_display',
            'target_counts',
            'created_at'
        ]
    
    def get_owner_name(self, obj):
        """Get the full name of the campaign owner"""
        if obj.owner:
            return f"{obj.owner.first_name} {obj.owner.last_name}"
        return None
    
    def get_has_sequence(self, obj):
        """Check if campaign has automated sequences"""
        return obj.has_sequence()
    
    def get_target_counts(self, obj):
        """Get simplified target counts"""
        summary = obj.get_target_summary()
        return {
            'total': summary['total'],
            'accounts': summary['accounts'],
            'contacts': summary['contacts'],
            'leads': summary['leads']
        }


# Export serializers
__all__ = [
    'CampaignSerializer',
    'CampaignListSerializer'
]