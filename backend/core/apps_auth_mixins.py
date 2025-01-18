# core/apps_auth_mixins.py
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import AuthenticationFailed
from django.utils.translation import gettext_lazy as _

class ClientAuthMixin:
    """
    Mixin to add client authentication and data segregation to API views.
    """
    permission_classes = [IsAuthenticated]

    def get_client_id(self):
        """Get client_id from JWT token"""
        if not self.request.auth:
            raise AuthenticationFailed(_("Authentication required"))
            
        client_id = self.request.auth.get('client_account')
        if not client_id:
            raise AuthenticationFailed(_("No client account found in token"))
            
        return client_id

    def get_queryset(self):
        """Add client_id filter to queryset"""
        queryset = super().get_queryset()
        client_id = self.get_client_id()
        return queryset.filter(client_id=client_id)

    def perform_create(self, serializer):
        """Add client_id to new records"""
        client_id = self.get_client_id()
        instance = super().perform_create(serializer)
        if not instance.client_id:
            instance.client_id = client_id
            instance.save(update_fields=['client_id'])
        return instance

    def check_object_permissions(self, request, obj):
        """Ensure object belongs to client"""
        super().check_object_permissions(request, obj)
        if hasattr(obj, 'client_id') and obj.client_id != self.get_client_id():
            self.permission_denied(request, message=_("Not found"))