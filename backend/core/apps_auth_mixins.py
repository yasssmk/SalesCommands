# core/apps_auth_mixins.py
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from django.utils.translation import gettext_lazy as _

class ClientAuthMixin:
    """
    Mixin to add client authentication and data segregation to API views.
    """
    permission_classes = [IsAuthenticated]

    def get_client_id(self):
        """
        Get client_id from JWT token and ensure it exists for end users
        """
        if not self.request.auth:
            raise AuthenticationFailed(_("Authentication required"))

        origin = self.request.auth.get('origin')
        
        # End users must have a client_account
        if origin == 'end_users':
            client_id = self.request.auth.get('client_account')
            if not client_id:
                raise AuthenticationFailed(_("No client account found in token"))
            return client_id
            
        # Product admin or invalid origin
        raise AuthenticationFailed(_("Please log in with a user account"))

    def filter_queryset_by_client(self, queryset):
        """
        Apply client_id filtering to any queryset
        """
        client_id = self.get_client_id()
        return queryset.filter(client_id=client_id)

    def check_object_permissions(self, request, obj):
        """
        Ensure object belongs to client
        """
        super().check_object_permissions(request, obj)
        
        client_id = self.get_client_id()
        if not hasattr(obj, 'client_id') or obj.client_id != client_id:
            raise PermissionDenied(_("Not found"))

    def perform_create(self, serializer):
        """
        Add client_id when creating new objects
        """
        client_id = self.get_client_id()
        return serializer.save(client_id=client_id)

    def perform_update(self, serializer):
        """
        Verify permissions before update
        """
        client_id = self.get_client_id()
        instance = serializer.instance
        if instance.client_id != client_id:
            raise PermissionDenied(_("Not found"))
        return serializer.save()

    def perform_delete(self, instance):
        """
        Verify permissions before delete
        """
        client_id = self.get_client_id()
        if instance.client_id != client_id:
            raise PermissionDenied(_("Not found"))
        instance.delete()