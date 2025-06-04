from rest_framework import serializers
from apps.campaign.models import CampaignStakeholder
from end_users.serializers import UserSerializer


class CampaignStakeholderSerializer(serializers.ModelSerializer):
    """
    Serializer for campaign stakeholders
    """
    user_name = serializers.SerializerMethodField(read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    added_by_name = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = CampaignStakeholder
        fields = [
            'id', 
            'campaign', 
            'user', 
            'user_name',
            'role', 
            'role_display', 
            'added_at', 
            'added_by', 
            'added_by_name'
        ]
        read_only_fields = ['added_at', 'added_by_name', 'user_name', 'role_display']
    
    def get_user_name(self, obj):
        """Get the name of the stakeholder"""
        if obj.user:
            return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.username
        return None
    
    def get_added_by_name(self, obj):
        """Get the name of the user who added this stakeholder"""
        if obj.added_by:
            return f"{obj.added_by.first_name} {obj.added_by.last_name}".strip() or obj.added_by.username
        return None
