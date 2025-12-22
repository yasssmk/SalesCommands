# app_modules/contacts/views/views_bulk.py
"""
Contact Bulk Operations ViewSet

Handles bulk create/update/delete with idempotency and optimized SQL queries.
Follows CompanyAccountBulkViewSet patterns for consistency.
"""

from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction

from core.throttling import BulkOperationThrottle
from core.idempotency import (
    start_op,
    complete_op,
    fail_op,
    get_owner_from_request,
    compute_payload_hash
)
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, ContactErrorMessages
from core.cache_utils import disable_signals_with_invalidation
from core.logging import get_logger, ctx_from_request
from core.logging.audit import audit_log

from app_modules.accounts.models import CompanyAccount

from ..models import Contact
from .views import ContactViewSet
from ..serializers import ContactSerializer, ContactCreateSerializer

logger = get_logger(__name__)


class ContactBulkViewSet(ContactViewSet):
    """
    ViewSet for bulk contact operations (create/update/delete).
    
    Inherits authentication, permissions, and client scoping from ContactViewSet.
    All operations support idempotency via Idempotency-Key header.
    """
    
    throttle_classes = [BulkOperationThrottle]
    
    # =========================================================================
    # BULK UPDATE
    # =========================================================================
    
    @action(detail=False, methods=['patch'], url_path='bulk-update')
    def bulk_update(self, request):
        """
        Bulk update contacts - IDEMPOTENT wrapper.
        
        Headers:
            Idempotency-Key (optional): Unique key for idempotent operations
            
        Request Body:
            ids: List[UUID] - Contact IDs to update
            patch: Dict - Fields to update
            mode: str - 'partial' (default) or 'strict'
        """
        idempotency_key = request.headers.get('Idempotency-Key')
        
        if not idempotency_key:
            return self._bulk_update_impl(request)
        
        client_id = self.get_client_id()
        
        try:
            owner = get_owner_from_request(request)
        except ValueError as e:
            return Response({
                'error': 'Tenant required',
                'detail': str(e)
            }, status=status.HTTP_403_FORBIDDEN)
        
        payload_hash = compute_payload_hash(request.data)
        
        try:
            op = start_op(client_id, idempotency_key, payload_hash, owner)
        except ValueError as e:
            return Response({
                'error': 'Idempotency conflict',
                'detail': str(e),
                'code': 'IDEMPOTENCY_CONFLICT'
            }, status=status.HTTP_409_CONFLICT)
        
        if op:
            if op['status'] == 'succeeded':
                result_data = op.get('result', {})
                if isinstance(result_data, dict) and 'data' in result_data:
                    return Response(
                        result_data['data'],
                        status=result_data.get('http_status', status.HTTP_200_OK)
                    )
                return Response(result_data, status=status.HTTP_200_OK)
            
            elif op['status'] == 'failed':
                err = op.get('result') or {}
                return Response({
                    'error': 'Operation failed',
                    'detail': err.get('message', 'Unknown error')
                }, status=err.get('http_status', status.HTTP_500_INTERNAL_SERVER_ERROR))
            
            elif op['status'] == 'running':
                return Response({
                    'status': 'processing',
                    'message': 'Operation in progress',
                    'code': 'OPERATION_IN_PROGRESS'
                }, status=status.HTTP_202_ACCEPTED)
        
        # Execute operation
        try:
            response = self._bulk_update_impl(request)
            complete_op(client_id, idempotency_key, {
                'data': response.data,
                'http_status': response.status_code
            })
            return response
        except Exception as e:
            fail_op(client_id, idempotency_key, {
                'message': str(e),
                'http_status': status.HTTP_500_INTERNAL_SERVER_ERROR
            })
            raise
    
    def _bulk_update_impl(self, request):
        """
        Actual bulk update implementation.
        """
        ids = request.data.get('ids', [])
        patch = request.data.get('patch', {})
        mode = request.data.get('mode', 'partial')
        detailed = request.data.get('detailed', False)
        
        # Validate input
        if not ids:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='ids')
            )
        
        if not patch:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='patch')
            )
        
        # Filter allowed fields
        allowed_fields = self.mass_update_allowed_fields
        filtered_patch = {k: v for k, v in patch.items() if k in allowed_fields}
        
        if not filtered_patch:
            raise StandardizedValidationError(CoreErrorMessages.MASS_UPDATE_INVALID)
        
        results = {'success': [], 'failed': []}
        client_id = str(self.get_client_id())
        
        try:
            # Get existing contacts info
            contacts_queryset = Contact.objects.filter(
                id__in=ids,
                client_id=client_id
            ).values('id', 'first_name', 'last_name', 'email')
            
            contacts_info = {
                str(c['id']): {
                    'name': f"{c['first_name']} {c['last_name']}",
                    'email': c['email']
                }
                for c in contacts_queryset
            }
            
            # Find missing IDs
            found_ids = set(contacts_info.keys())
            requested_ids = set(str(id) for id in ids)
            missing_ids = requested_ids - found_ids
            
            # Handle missing contacts
            for missing_id in missing_ids:
                results['failed'].append({
                    'id': missing_id,
                    'name': 'Unknown',
                    'errors': [str(CoreErrorMessages.OBJECT_NOT_FOUND)]
                })
            
            if mode == 'strict' and missing_ids:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
            valid_ids = list(found_ids)
            
            if valid_ids:
                with disable_signals_with_invalidation(client_id, ['contacts', 'accounts']):
                    with transaction.atomic():
                        # Set-based update
                        updated_count = Contact.objects.filter(
                            id__in=valid_ids,
                            client_id=client_id
                        ).update(**filtered_patch)
                        
                        # Build success results
                        for contact_id in valid_ids:
                            info = contacts_info.get(contact_id, {'name': 'Unknown', 'email': ''})
                            results['success'].append({
                                'id': contact_id,
                                'name': info['name'],
                                'email': info['email']
                            })
            
            # Audit log
            audit_log(
                event='bulk_update_contacts_completed',
                action='bulk_update',
                actor_id=str(request.user.id),
                client_id=client_id,
                target_type='contact',
                target_count=len(ids),
                outcome='success',
                extra={
                    'updated': len(results['success']),
                    'failed': len(results['failed'])
                }
            )
            
            return self._build_bulk_success_response(results, len(ids), operation='update', detailed=detailed)
        
        except StandardizedValidationError:
            raise
        except Exception as e:
            logger.error("bulk_update_contacts_error", extra={
                **ctx_from_request(request),
                'error': str(e)
            }, exc_info=True)
            raise
    
    # =========================================================================
    # BULK DELETE
    # =========================================================================
    
    @action(detail=False, methods=['delete'], url_path='bulk-delete')
    def bulk_delete(self, request):
        """
        Delete multiple contacts in bulk - IDEMPOTENT wrapper.
        
        Headers:
            Idempotency-Key (optional): Unique key for idempotent operations
            
        Request Body:
            ids: List[UUID] - Contact IDs to delete
            mode: str - 'partial' (default) or 'strict'
        """
        idempotency_key = request.headers.get('Idempotency-Key')
        
        if not idempotency_key:
            return self._bulk_delete_impl(request)
        
        client_id = self.get_client_id()
        
        try:
            owner = get_owner_from_request(request)
        except ValueError as e:
            return Response({
                'error': 'Tenant required',
                'detail': str(e)
            }, status=status.HTTP_403_FORBIDDEN)
        
        payload_hash = compute_payload_hash(request.data)
        
        try:
            op = start_op(client_id, idempotency_key, payload_hash, owner)
        except ValueError as e:
            return Response({
                'error': 'Idempotency conflict',
                'detail': str(e),
                'code': 'IDEMPOTENCY_CONFLICT'
            }, status=status.HTTP_409_CONFLICT)
        
        if op:
            if op['status'] == 'succeeded':
                result_data = op.get('result', {})
                if isinstance(result_data, dict) and 'data' in result_data:
                    return Response(
                        result_data['data'],
                        status=result_data.get('http_status', status.HTTP_200_OK)
                    )
                return Response(result_data, status=status.HTTP_200_OK)
            
            elif op['status'] == 'failed':
                err = op.get('result') or {}
                return Response({
                    'error': 'Operation failed',
                    'detail': err.get('message', 'Unknown error')
                }, status=err.get('http_status', status.HTTP_500_INTERNAL_SERVER_ERROR))
            
            elif op['status'] == 'running':
                return Response({
                    'status': 'processing',
                    'message': 'Operation in progress',
                    'code': 'OPERATION_IN_PROGRESS'
                }, status=status.HTTP_202_ACCEPTED)
        
        # Execute operation
        try:
            response = self._bulk_delete_impl(request)
            complete_op(client_id, idempotency_key, {
                'data': response.data,
                'http_status': response.status_code
            })
            return response
        except Exception as e:
            fail_op(client_id, idempotency_key, {
                'message': str(e),
                'http_status': status.HTTP_500_INTERNAL_SERVER_ERROR
            })
            raise
    
    def _bulk_delete_impl(self, request):
        """
        Actual bulk delete implementation.
        """
        ids = request.data.get('ids', [])
        mode = request.data.get('mode', 'partial')
        detailed = request.data.get('detailed', False)
        
        # Validate input
        if not ids:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='ids')
            )
        
        results = {'success': [], 'failed': []}
        client_id = str(self.get_client_id())
        
        try:
            # Get existing contacts info
            contacts_queryset = Contact.objects.filter(
                id__in=ids,
                client_id=client_id
            ).values('id', 'first_name', 'last_name', 'email')
            
            contacts_info = {
                str(c['id']): {
                    'name': f"{c['first_name']} {c['last_name']}",
                    'email': c['email']
                }
                for c in contacts_queryset
            }
            
            # Find missing IDs
            found_ids = set(contacts_info.keys())
            requested_ids = set(str(id) for id in ids)
            missing_ids = requested_ids - found_ids
            
            # Handle missing contacts
            for missing_id in missing_ids:
                results['failed'].append({
                    'id': missing_id,
                    'name': 'Unknown',
                    'errors': [str(CoreErrorMessages.OBJECT_NOT_FOUND)]
                })
            
            if mode == 'strict' and missing_ids:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
            
            valid_ids = list(found_ids)
            
            if valid_ids:
                with disable_signals_with_invalidation(client_id, ['contacts', 'accounts']):
                    with transaction.atomic():
                        # Set-based delete
                        deleted_count, _ = Contact.objects.filter(
                            id__in=valid_ids,
                            client_id=client_id
                        ).delete()
                        
                        # Build success results
                        for contact_id in valid_ids:
                            info = contacts_info.get(contact_id, {'name': 'Unknown', 'email': ''})
                            results['success'].append({
                                'id': contact_id,
                                'name': info['name'],
                                'email': info['email']
                            })
            
            # Audit log
            audit_log(
                event='bulk_delete_contacts_completed',
                action='bulk_delete',
                actor_id=str(request.user.id),
                client_id=client_id,
                target_type='contact',
                target_count=len(ids),
                outcome='success',
                extra={
                    'deleted': len(results['success']),
                    'failed': len(results['failed'])
                }
            )
            
            return self._build_bulk_success_response(results, len(ids), operation='delete', detailed=detailed)
        
        except StandardizedValidationError:
            raise
        except Exception as e:
            logger.error("bulk_delete_contacts_error", extra={
                **ctx_from_request(request),
                'error': str(e)
            }, exc_info=True)
            raise
    
    # =========================================================================
    # BULK CREATE
    # =========================================================================
    
    @action(detail=False, methods=['post'], url_path='bulk-create')
    def bulk_create(self, request):
        """
        Create multiple contacts in bulk - IDEMPOTENT wrapper.
        
        Headers:
            Idempotency-Key (optional): Unique key for idempotent operations
            
        Request Body:
            contacts: List[Dict] - Contact data to create
            mode: str - 'partial' (default) or 'strict'
        """
        idempotency_key = request.headers.get('Idempotency-Key')
        
        if not idempotency_key:
            return self._bulk_create_impl(request)
        
        client_id = self.get_client_id()
        
        try:
            owner = get_owner_from_request(request)
        except ValueError as e:
            return Response({
                'error': 'Tenant required',
                'detail': str(e)
            }, status=status.HTTP_403_FORBIDDEN)
        
        payload_hash = compute_payload_hash(request.data)
        
        try:
            op = start_op(client_id, idempotency_key, payload_hash, owner)
        except ValueError as e:
            return Response({
                'error': 'Idempotency conflict',
                'detail': str(e),
                'code': 'IDEMPOTENCY_CONFLICT'
            }, status=status.HTTP_409_CONFLICT)
        
        if op:
            if op['status'] == 'succeeded':
                result_data = op.get('result', {})
                if isinstance(result_data, dict) and 'data' in result_data:
                    return Response(
                        result_data['data'],
                        status=result_data.get('http_status', status.HTTP_201_CREATED)
                    )
                return Response(result_data, status=status.HTTP_201_CREATED)
            
            elif op['status'] == 'failed':
                err = op.get('result') or {}
                return Response({
                    'error': 'Operation failed',
                    'detail': err.get('message', 'Unknown error')
                }, status=err.get('http_status', status.HTTP_500_INTERNAL_SERVER_ERROR))
            
            elif op['status'] == 'running':
                return Response({
                    'status': 'processing',
                    'message': 'Operation in progress',
                    'code': 'OPERATION_IN_PROGRESS'
                }, status=status.HTTP_202_ACCEPTED)
        
        # Execute operation
        try:
            response = self._bulk_create_impl(request)
            complete_op(client_id, idempotency_key, {
                'data': response.data,
                'http_status': response.status_code
            })
            return response
        except Exception as e:
            fail_op(client_id, idempotency_key, {
                'message': str(e),
                'http_status': status.HTTP_500_INTERNAL_SERVER_ERROR
            })
            raise
    
    def _bulk_create_impl(self, request):
        """
        Actual bulk create implementation.
        """
        contacts_data = request.data.get('contacts', [])
        mode = request.data.get('mode', 'partial')
        detailed = request.data.get('detailed', False)
        
        # Validate input
        if not contacts_data:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='contacts')
            )
        
        results = {'success': [], 'failed': []}
        client_id = str(self.get_client_id())
        user = request.user
        
        try:
            with disable_signals_with_invalidation(client_id, ['contacts', 'accounts']):
                with transaction.atomic():
                    for idx, contact_data in enumerate(contacts_data):
                        try:
                            # Validate account_id belongs to client
                            account_id = contact_data.get('account_id')
                            if not account_id:
                                raise StandardizedValidationError(
                                    ContactErrorMessages.ACCOUNT_REQUIRED
                                )
                            
                            try:
                                account = CompanyAccount.objects.get(
                                    id=account_id,
                                    client_id=client_id
                                )
                            except CompanyAccount.DoesNotExist:
                                raise StandardizedValidationError(
                                    ContactErrorMessages.INVALID_ACCOUNT
                                )
                            
                            # Create contact
                            serializer = ContactCreateSerializer(
                                data=contact_data,
                                context={
                                    'request': request,
                                    'client_id': client_id
                                }
                            )
                            
                            if serializer.is_valid():
                                contact = serializer.save()
                                results['success'].append({
                                    'id': str(contact.id),
                                    'name': contact.full_name,
                                    'email': contact.email,
                                    'row': idx + 1
                                })
                            else:
                                if mode == 'strict':
                                    raise StandardizedValidationError(serializer.errors)
                                
                                results['failed'].append({
                                    'row': idx + 1,
                                    'data': contact_data,
                                    'errors': serializer.errors
                                })
                        
                        except StandardizedValidationError as e:
                            if mode == 'strict':
                                raise
                            
                            error_msg = str(e.detail) if hasattr(e, 'detail') else str(e)
                            results['failed'].append({
                                'row': idx + 1,
                                'data': contact_data,
                                'errors': [error_msg]
                            })
                        
                        except Exception as e:
                            if mode == 'strict':
                                raise
                            
                            results['failed'].append({
                                'row': idx + 1,
                                'data': contact_data,
                                'errors': [str(e)]
                            })
            
            # Audit log
            audit_log(
                event='bulk_create_contacts_completed',
                action='bulk_create',
                actor_id=str(user.id),
                client_id=client_id,
                target_type='contact',
                target_count=len(contacts_data),
                outcome='success',
                extra={
                    'created': len(results['success']),
                    'failed': len(results['failed'])
                }
            )
            
            return self._build_bulk_success_response(
                results, 
                len(contacts_data), 
                operation='create', 
                detailed=detailed,
                status_code=status.HTTP_201_CREATED
            )
        
        except StandardizedValidationError:
            raise
        except Exception as e:
            logger.error("bulk_create_contacts_error", extra={
                **ctx_from_request(request),
                'error': str(e)
            }, exc_info=True)
            raise
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _build_bulk_success_response(self, results, total, operation, detailed=False, status_code=None):
        """Build standardized bulk operation response."""
        success_count = len(results['success'])
        failed_count = len(results['failed'])
        
        response_data = {
            'status': 'completed',
            'operation': operation,
            'summary': {
                'total': total,
                'success': success_count,
                'failed': failed_count
            }
        }
        
        if detailed:
            response_data['results'] = results
        
        http_status = status_code or status.HTTP_200_OK
        return Response(response_data, status=http_status)
    
    def _build_bulk_error_response(self, results, total, error_message):
        """Build standardized bulk error response."""
        return Response({
            'status': 'failed',
            'error': error_message,
            'summary': {
                'total': total,
                'success': len(results['success']),
                'failed': len(results['failed'])
            }
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def _format_bulk_error_message(self, exception):
        """Format exception into user-friendly error message."""
        if hasattr(exception, 'detail'):
            if isinstance(exception.detail, dict):
                return exception.detail.get('error', str(exception))
            return str(exception.detail)
        return str(exception)