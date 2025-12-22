# app_modules/contacts/views/views.py
"""
ViewSet for Contact module.

Follows CompanyAccountViewSet patterns for consistency.
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction

from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, ContactErrorMessages
from core.jwt_helpers import CustomJWTAuthentication
from core.apps_shared_methods import BaseAPIView
from core.logging import get_logger, ctx_from_request
from core.logging.audit import audit_log
from core.cache_utils import invalidate_tag

from permissions.mixins import ScopedPermission, ScopedQuerysetMixin
from permissions.owner_scope import OwnerScopeMixin

from app_modules.core_modules.models import StandardDepartment

from ..models import Contact, InfluenceLevel
from ..serializers import (
    ContactSerializer,
    ContactListSerializer,
    ContactCreateSerializer,
)
from ..filters import ContactFilter

logger = get_logger(__name__)


class ContactViewSet(OwnerScopeMixin, ScopedQuerysetMixin, BaseAPIView, viewsets.ModelViewSet):
    """
    API endpoints for managing contacts with client scoping.
    
    Follows CompanyAccountViewSet patterns for consistency.
    """
    
    queryset = Contact.objects.all()
    serializer_class = ContactSerializer
    entity_name = 'contact'
    
    # Filtering
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ContactFilter
    search_fields = ['first_name', 'last_name', 'email', 'job_title', 'account__company_name']
    ordering_fields = [
        'first_name',
        'last_name',
        'email',
        'job_title',
        'influence_level',
        'created_at',
        'updated_at',
    ]
    ordering = ['-created_at']
    
    # Security
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, ScopedPermission]
    module = 'contacts'
    
    # Allowed fields for mass update
    mass_update_allowed_fields = {
        'influence_level', 'has_buying_authority', 'standard_department_id', 'opted_out'
    }
    
    # Action policies
    action_policies = {
        'mark_email_invalid': {
            'crud': 'update',
            'scope': 'client'
        },
        'mark_phone_invalid': {
            'crud': 'update',
            'scope': 'client'
        },
        'mark_opted_out': {
            'crud': 'update',
            'scope': 'client'
        },
        'bulk_create': {
            'crud': 'create',
            'tier': 'admin',
            'scope': 'client'
        },
        'bulk_update': {
            'crud': 'update',
            'tier': 'admin',
            'scope': 'client'
        },
        'bulk_delete': {
            'crud': 'delete',
            'tier': 'admin',
            'scope': 'client'
        },
    }
    
    def get_serializer_class(self):
        """Choose serializer based on action."""
        if self.action == 'list':
            return ContactListSerializer
        elif self.action == 'create':
            return ContactCreateSerializer
        return ContactSerializer
    
    def get_queryset(self):
        """Get contacts with optimized queries and filtering."""
        logger.debug("get_queryset_called", extra={
            'action': self.action,
            'view': 'ContactViewSet'
        })
        
        queryset = super().get_queryset()
        
        # Optimize based on action
        if self.action == 'list':
            queryset = queryset.select_related(
                'account',
                'standard_department'
            )
        elif self.action == 'retrieve':
            queryset = queryset.select_related(
                'account',
                'standard_department',
                'created_by',
                'updated_by'
            )
        else:
            queryset = queryset.select_related(
                'account',
                'standard_department'
            )
        
        # Apply owner scope filter (mine/team/all)
        queryset = self.apply_owner_scope_filter(queryset)
        
        return queryset
    
    def perform_create(self, serializer):
        """Create contact with audit logging."""
        user = self.request.user
        client_id = self.get_client_id()
        
        instance = serializer.save()
        
        # Audit log
        audit_log(
            event='contact_create_success',
            action='create',
            actor_id=str(user.id),
            client_id=str(client_id),
            target_type='contact',
            target_id=str(instance.id),
            outcome='success'
        )
        
        # Invalidate cache
        invalidate_tag(str(client_id), 'contacts')
        invalidate_tag(str(client_id), 'accounts') 
        
        logger.info("contact_created", extra={
            **ctx_from_request(self.request),
            'contact_id': str(instance.id),
            'account_id': str(instance.account_id),
        })
    
    def perform_update(self, serializer):
        """Update contact with audit logging."""
        user = self.request.user
        client_id = self.get_client_id()
        instance = serializer.instance
        
        # Track changed fields
        changed_fields = list(serializer.validated_data.keys())
        
        serializer.save()
        
        # Audit log
        audit_log(
            event='contact_update_success',
            action='update',
            actor_id=str(user.id),
            client_id=str(client_id),
            target_type='contact',
            target_id=str(instance.id),
            fields_changed=changed_fields,
            outcome='success'
        )
        
        # Invalidate cache
        invalidate_tag(str(client_id), 'contacts')
        invalidate_tag(str(client_id), 'accounts') 
        
        logger.info("contact_updated", extra={
            **ctx_from_request(self.request),
            'contact_id': str(instance.id),
            'fields_changed': changed_fields,
        })
    
    def perform_destroy(self, instance):
        """Delete contact with audit logging."""
        user = self.request.user
        client_id = self.get_client_id()
        contact_id = str(instance.id)
        account_id = str(instance.account_id)
        
        instance.delete()
        
        # Audit log
        audit_log(
            event='contact_delete_success',
            action='delete',
            actor_id=str(user.id),
            client_id=str(client_id),
            target_type='contact',
            target_id=contact_id,
            outcome='success'
        )
        
        # Invalidate cache
        invalidate_tag(str(client_id), 'contacts')
        invalidate_tag(str(client_id), 'accounts') 
        
        logger.info("contact_deleted", extra={
            **ctx_from_request(self.request),
            'contact_id': contact_id,
            'account_id': account_id,
        })
    
    # =========================================================================
    # CUSTOM ACTIONS
    # =========================================================================
    
    @action(detail=True, methods=['post'], url_path='mark-email-invalid')
    def mark_email_invalid(self, request, pk=None):
        """Mark contact's email as invalid."""
        contact = self.get_object()
        contact.mark_email_invalid(user=request.user)
        
        audit_log(
            event='contact_email_marked_invalid',
            action='update',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type='contact',
            target_id=str(contact.id),
            fields_changed=['email_is_valid'],
            outcome='success'
        )
        
        return Response({
            'message': 'Email marked as invalid',
            'email_is_valid': contact.email_is_valid
        })
    
    @action(detail=True, methods=['post'], url_path='mark-phone-invalid')
    def mark_phone_invalid(self, request, pk=None):
        """Mark contact's phone as invalid."""
        contact = self.get_object()
        contact.mark_phone_invalid(user=request.user)
        
        audit_log(
            event='contact_phone_marked_invalid',
            action='update',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type='contact',
            target_id=str(contact.id),
            fields_changed=['phone_is_valid'],
            outcome='success'
        )
        
        return Response({
            'message': 'Phone marked as invalid',
            'phone_is_valid': contact.phone_is_valid
        })
    
    @action(detail=True, methods=['post'], url_path='mark-opted-out')
    def mark_opted_out(self, request, pk=None):
        """Mark contact as opted out of communications."""
        contact = self.get_object()
        contact.mark_opted_out(user=request.user)
        
        audit_log(
            event='contact_opted_out',
            action='update',
            actor_id=str(request.user.id),
            client_id=str(self.get_client_id()),
            target_type='contact',
            target_id=str(contact.id),
            fields_changed=['opted_out'],
            outcome='success'
        )
        
        return Response({
            'message': 'Contact marked as opted out',
            'opted_out': contact.opted_out
        })


class ContactChoicesView(APIView):
    """
    API endpoint for retrieving contact-related choices.
    """
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get all available choices for contact fields."""
        return Response({
            'influence_levels': [
                {'value': choice[0], 'label': choice[1]}
                for choice in InfluenceLevel.choices
            ],
            'standard_departments': [
                {'value': dept.id, 'label': dept.get_name_display()}
                for dept in StandardDepartment.objects.all().order_by('name')
            ],
        })