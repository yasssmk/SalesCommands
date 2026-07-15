# app_modules/notifications/serializers.py
"""
Serializers for the Notifications module.
"""

from rest_framework import serializers

from core.client_scope import ClientScopeManager

from .models import Notification


class NotificationSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Read-only serializer for Notification list/detail output.
    """

    class Meta:
        model = Notification
        fields = [
            'id',
            'category',
            'title',
            'body',
            'related_object_type',
            'related_object_id',
            'payload',
            'read_at',
            'response_status',
            'created_at',
        ]
        read_only_fields = fields
