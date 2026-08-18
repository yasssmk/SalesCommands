from rest_framework import serializers
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.password_validation import validate_password
from ..models import ClientAccount


class ClientAccountSerializer(serializers.ModelSerializer):
    """
    Serializer pour ClientAccount - reste simple car c'est le point d'entrée multi-tenant
    """
    users_count = serializers.SerializerMethodField(read_only=True)
    organizations_count = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = ClientAccount
        fields = [
            'id', 'name', 'is_b2b', 'max_users',
            # The tenant's single currency: the unit EVERY amount it owns is
            # expressed in. Read-only here — choosing it belongs to the Admin
            # Client sprint, this only exposes it.
            'currency',
            'users_count', 'organizations_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'users_count',
                            'organizations_count', 'currency']
    
    def get_users_count(self, obj):
        """Number of active users.

        Reads the queryset annotation set by the list/retrieve viewset
        (avoids the per-row COUNT). Falls back to a direct count for callers
        that serialize an un-annotated instance (e.g. the create path in
        product_admin, which serializes a freshly saved account).
        """
        annotated = getattr(obj, 'users_count_annotated', None)
        if annotated is not None:
            return annotated
        return obj.users.filter(is_active=True).count()

    def get_organizations_count(self, obj):
        """Number of organizations. Reads the annotation when present,
        else counts directly (un-annotated callers)."""
        annotated = getattr(obj, 'organizations_count_annotated', None)
        if annotated is not None:
            return annotated
        return obj.organizations.count()