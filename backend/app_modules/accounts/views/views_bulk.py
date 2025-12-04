# app_modules/accounts/views/views_bulk.py
"""
CompanyAccount Bulk Operations ViewSet

Handles bulk create/update/delete with idempotency and optimized SQL queries.
Follows UserBulkViewSet patterns for consistency.
"""

from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.urls import reverse

from core.throttling import BulkOperationThrottle
from core.idempotency import (
    start_op,
    complete_op,
    fail_op,
    get_owner_from_request,
    compute_payload_hash
)
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, AccountErrorMessages, UsersErrorMessages
from core.cache_utils import disable_signals_with_invalidation
from core.logging import get_logger, ctx_from_request
from core.logging.audit import audit_log

from end_users.models import User

from ..models import CompanyAccount, AccountType, AccountClassification
from .views import CompanyAccountViewSet
from ..serializers import CompanyAccountSerializer, CompanyAccountCreateSerializer

logger = get_logger(__name__)


class CompanyAccountBulkViewSet(CompanyAccountViewSet):
    """
    ViewSet for bulk company account operations (create/update/delete).
    
    Inherits authentication, permissions, and client scoping from CompanyAccountViewSet.
    All operations support idempotency via Idempotency-Key header.
    """
    
    throttle_classes = [BulkOperationThrottle]
    
    # =========================================================================
    # BULK UPDATE
    # =========================================================================
    
    @action(detail=False, methods=['patch'], url_path='bulk-update')
    def bulk_update(self, request):
        """
        Bulk update company accounts - IDEMPOTENT wrapper.
        
        Headers:
            Idempotency-Key (optional): Unique key for idempotent operations
            
        Request Body:
            ids: List[UUID] - Account IDs to update
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
                    'poll_url': reverse('ops:status', args=[idempotency_key])
                }, status=status.HTTP_202_ACCEPTED, headers={'Retry-After': '2'})
        
        try:
            result = self._bulk_update_impl(request)
            complete_op(
                client_id,
                idempotency_key,
                {'data': result.data, 'http_status': result.status_code}
            )
            return result
        
        except StandardizedValidationError as e:
            fail_op(
                client_id,
                idempotency_key,
                {'message': str(e), 'http_status': status.HTTP_400_BAD_REQUEST}
            )
            raise
        
        except Exception as e:
            fail_op(
                client_id,
                idempotency_key,
                {'message': str(e), 'http_status': status.HTTP_500_INTERNAL_SERVER_ERROR}
            )
            raise
    
    def _bulk_update_impl(self, request):
        """Internal implementation of bulk update with SQL SET-BASED optimization."""
        ctx = ctx_from_request(request)
        ctx.update({
            'event': 'bulk_update_accounts',
            'client_id': str(self.get_client_id())
        })
        
        detailed = request.query_params.get('detailed', 'false').lower() == 'true'
        
        try:
            # ===== INPUT VALIDATION =====
            if not isinstance(request.data, dict):
                raise StandardizedValidationError("Request must be a JSON object")
            
            ids = request.data.get('ids', [])
            patch = request.data.get('patch', {})
            mode = request.data.get('mode', 'partial')
            
            if not isinstance(ids, list):
                raise StandardizedValidationError(
                    CoreErrorMessages.BULK_INVALID_FORMAT.format(entity="account IDs")
                )
            
            if not ids:
                raise StandardizedValidationError(
                    CoreErrorMessages.BULK_NO_DATA.format(entity="account IDs")
                )
            
            if len(ids) > 500:
                raise StandardizedValidationError(
                    CoreErrorMessages.BULK_SIZE_EXCEEDED.format(max_size=500, entity="accounts")
                )
            
            if not isinstance(patch, dict):
                raise StandardizedValidationError("Patch data must be a JSON object")
            
            if not patch:
                raise StandardizedValidationError(CoreErrorMessages.BULK_UPDATE_NO_FIELDS)
            
            if mode not in ['partial', 'strict']:
                raise StandardizedValidationError(CoreErrorMessages.BULK_MODE_INVALID)
            
            audit_log(
                event='bulk_update_accounts',
                action='bulk_update',
                actor_id=str(request.user.id),
                client_id=str(self.get_client_id()),
                target_type='company_account',
                target_count=len(ids),
                outcome='started',
                extra={'mode': mode}
            )
            
            # ===== VALIDATE ALLOWED FIELDS =====
            ALLOWED_FIELDS = {
                'type', 'classification', 'account_owner_id', 'parent_id',
                'industry', 'company_size', 'annual_revenue', 'has_buying_decision'
            }
            invalid_fields = set(patch.keys()) - ALLOWED_FIELDS
            
            if invalid_fields:
                raise StandardizedValidationError(
                    f"Fields not allowed in bulk update: {', '.join(invalid_fields)}. "
                    f"Allowed: {', '.join(ALLOWED_FIELDS)}"
                )
            
            # ===== FETCH ACCOUNTS WITH TENANT SCOPING =====
            client_id = self.get_client_id()
            accounts_qs = CompanyAccount.objects.filter(
                id__in=ids,
                client_id=client_id
            ).select_related('account_owner', 'account_owner__team', 'parent_company')
            accounts_dict = {str(a.id): a for a in accounts_qs}
            
            # ===== CHECK FOR INVALID IDS =====
            invalid_ids = set(ids) - set(accounts_dict.keys())
            
            results = {'success': [], 'failed': []}
            
            for invalid_id in invalid_ids:
                results['failed'].append({
                    'id': invalid_id,
                    'company_name': 'Unknown',
                    'errors': [CoreErrorMessages.BULK_UPDATE_INVALID_ID.format(id=invalid_id)]
                })
            
            if mode == 'strict' and invalid_ids:
                return self._build_bulk_error_response(
                    results,
                    len(ids),
                    f"Strict mode: {len(invalid_ids)} invalid ID(s) found"
                )
            
            # ===== PRE-VALIDATION FOR FK FIELDS =====
            valid_account_ids = [aid for aid in ids if aid not in invalid_ids]
            
            # Validate FK fields
            validated_fks = {}
            fk_fields = {'account_owner_id', 'parent_id'}
            fk_updates = {k: v for k, v in patch.items() if k in fk_fields}
            fk_validation_error = None

            if fk_updates:
                try:
                     validated_fks = self._prevalidate_account_fks(fk_updates, client_id, valid_account_ids)
                except StandardizedValidationError as e:
                    error_msg = self._format_bulk_error_message(e)
                    if mode == 'strict':
                        return self._build_bulk_error_response(
                            results,
                            len(ids),
                            f"Strict mode failed: {error_msg}"
                )
                    # In partial mode, store error for warning but continue with other fields
                    fk_validation_error = error_msg
                    fk_updates = {}
                    validated_fks = {}
            
            # ===== APPLY UPDATES =====
            with disable_signals_with_invalidation(client_id, ['accounts']):
                if mode == 'strict':
                    with transaction.atomic():
                        try:
                            # Build update dict
                            update_fields = {}
                            
                            # Simple fields
                            simple_fields = {'type', 'classification', 'industry', 
                                           'company_size', 'annual_revenue', 'has_buying_decision'}
                            for field in simple_fields:
                                if field in patch:
                                    # Validate type/classification values
                                    if field == 'type' and patch[field]:
                                        if patch[field] not in dict(AccountType.choices):
                                            raise StandardizedValidationError(
                                                f"Invalid account type: {patch[field]}"
                                            )
                                    if field == 'classification' and patch[field]:
                                        if patch[field] not in dict(AccountClassification.choices):
                                            raise StandardizedValidationError(
                                                f"Invalid classification: {patch[field]}"
                                            )
                                    update_fields[field] = patch[field]
                            
                            # FK fields
                            if 'account_owner_id' in validated_fks:
                                owner = validated_fks['account_owner_id']
                                if owner is None:
                                    update_fields['account_owner'] = None
                                else:
                                    update_fields['account_owner_id'] = owner.id
                            
                            if 'parent_id' in validated_fks:
                                parent = validated_fks['parent_id']
                                if parent is None:
                                    update_fields['parent_company'] = None
                                else:
                                    update_fields['parent_company_id'] = parent.id

                            # Apply set-based update
                            if update_fields and valid_account_ids:
                                CompanyAccount.objects.filter(
                                    id__in=valid_account_ids,
                                    client_id=client_id
                                ).update(**update_fields)
                            
                            # Build success results
                            for account_id in valid_account_ids:
                                account = accounts_dict[account_id]
                                account.refresh_from_db()
                                results['success'].append({
                                    'id': str(account.id),
                                    'company_name': account.company_name
                                })
                        
                        except Exception as e:
                            error_msg = self._format_bulk_error_message(e)
                            return self._build_bulk_error_response(
                                {'success': [], 'failed': results['failed']},
                                len(ids),
                                f"Strict mode failed: {error_msg}"
                            )
                else:
                    # Partial mode: Best-effort updates
                    update_fields = {}
                    
                    # Simple fields with validation
                    simple_fields = {'type', 'classification', 'industry',
                                   'company_size', 'annual_revenue', 'has_buying_decision'}
                    for field in simple_fields:
                        if field in patch:
                            if field == 'type' and patch[field]:
                                if patch[field] not in dict(AccountType.choices):
                                    continue  # Skip invalid in partial mode
                            if field == 'classification' and patch[field]:
                                if patch[field] not in dict(AccountClassification.choices):
                                    continue
                            update_fields[field] = patch[field]
                    
                    # FK fields
                    if 'account_owner_id' in validated_fks:
                        owner = validated_fks['account_owner_id']
                        if owner is None:
                            update_fields['account_owner'] = None
                        else:
                            update_fields['account_owner_id'] = owner.id

                    if 'parent_id' in validated_fks:
                        parent = validated_fks['parent_id']
                        if parent is None:
                            update_fields['parent_company'] = None
                        else:
                            update_fields['parent_company_id'] = parent.id
                    
                    # Check if ALL requested fields failed validation
                    if not update_fields and fk_validation_error:
                        # All fields were FK fields and all failed - return error
                        return self._build_bulk_error_response(
                            results,
                            len(ids),
                            fk_validation_error
                        )
                    
                    # Apply update
                    if update_fields and valid_account_ids:
                        with transaction.atomic():
                            CompanyAccount.objects.filter(
                                id__in=valid_account_ids,
                                client_id=client_id
                            ).update(**update_fields)
                    
                    # Build success results
                    for account_id in valid_account_ids:
                        account = accounts_dict[account_id]
                        account.refresh_from_db()
                        results['success'].append({
                            'id': str(account.id),
                            'company_name': account.company_name
                        })
            
            # ===== BUILD RESPONSE =====
            success_count = len(results['success'])
            failed_count = len(results['failed'])
            
            audit_log(
                event='bulk_update_accounts_completed',
                action='bulk_update',
                actor_id=str(request.user.id),
                client_id=str(self.get_client_id()),
                target_type='company_account',
                target_count=len(ids),
                outcome='success',
                extra={
                    'updated': success_count,
                    'failed': failed_count
                }
            )
            
            # Add warning if FK validation failed in partial mode
            if fk_validation_error:
                response = self._build_bulk_success_response(results, len(ids), operation='update', detailed=detailed)
                response.data['warning'] = f"Some fields were skipped: {fk_validation_error}"
                return response

            return self._build_bulk_success_response(results, len(ids), operation='update', detailed=detailed)
        
        except StandardizedValidationError as e:
            error_msg = str(e)
            if hasattr(e, 'detail') and isinstance(e.detail, dict):
                raw_error = e.detail.get('error', str(e))
                error_msg = str(raw_error)
            
            return self._build_bulk_error_response(
                results={'success': [], 'failed': []},
                total=0,
                error_message=error_msg
            )
    
    # =========================================================================
    # BULK DELETE
    # =========================================================================
    
    @action(detail=False, methods=['delete'], url_path='bulk-delete')
    def bulk_delete(self, request):
        """
        Physically delete multiple accounts in bulk - IDEMPOTENT wrapper.
        
        Headers:
            Idempotency-Key (optional): Unique key for idempotent operations
            
        Request Body:
            ids: List[UUID] - Account IDs to delete
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
                    'poll_url': reverse('ops:status', args=[idempotency_key])
                }, status=status.HTTP_202_ACCEPTED, headers={'Retry-After': '2'})
        
        try:
            result = self._bulk_delete_impl(request)
            complete_op(
                client_id,
                idempotency_key,
                {'data': result.data, 'http_status': result.status_code}
            )
            return result
        
        except StandardizedValidationError as e:
            fail_op(
                client_id,
                idempotency_key,
                {'message': str(e), 'http_status': status.HTTP_400_BAD_REQUEST}
            )
            raise
        
        except Exception as e:
            fail_op(
                client_id,
                idempotency_key,
                {'message': str(e), 'http_status': status.HTTP_500_INTERNAL_SERVER_ERROR}
            )
            raise
    
    def _bulk_delete_impl(self, request):
        """Internal implementation of bulk delete with SQL SET-BASED optimization."""
        ctx = ctx_from_request(request)
        ctx.update({
            'event': 'bulk_delete_accounts',
            'client_id': str(self.get_client_id())
        })
        
        detailed = request.query_params.get('detailed', 'false').lower() == 'true'
        
        try:
            # ===== INPUT VALIDATION =====
            if not isinstance(request.data, dict):
                raise StandardizedValidationError("Request must be a JSON object")
            
            ids = request.data.get('ids', [])
            mode = request.data.get('mode', 'partial')
            
            if not isinstance(ids, list):
                raise StandardizedValidationError(
                    CoreErrorMessages.BULK_INVALID_FORMAT.format(entity="account IDs")
                )
            
            if not ids:
                raise StandardizedValidationError(CoreErrorMessages.BULK_DELETE_NO_IDS)
            
            if len(ids) > 500:
                raise StandardizedValidationError(
                    CoreErrorMessages.BULK_SIZE_EXCEEDED.format(max_size=500, entity="accounts")
                )
            
            if mode not in ['partial', 'strict']:
                raise StandardizedValidationError(CoreErrorMessages.BULK_MODE_INVALID)
            
            audit_log(
                event='bulk_delete_accounts',
                action='bulk_delete',
                actor_id=str(request.user.id),
                client_id=str(self.get_client_id()),
                target_type='company_account',
                target_count=len(ids),
                outcome='started',
                extra={'mode': mode}
            )
            
            # ===== FETCH ACCOUNTS WITH TENANT SCOPING =====
            client_id = self.get_client_id()
            accounts_qs = CompanyAccount.objects.filter(
                id__in=ids,
                client_id=client_id
            ).select_related('parent_company').prefetch_related('direct_child_companies')
            accounts_dict = {str(a.id): a for a in accounts_qs}
            
            # ===== CHECK FOR INVALID IDS =====
            invalid_ids = set(ids) - set(accounts_dict.keys())
            
            results = {'success': [], 'failed': []}
            
            for invalid_id in invalid_ids:
                results['failed'].append({
                    'id': invalid_id,
                    'company_name': 'Unknown',
                    'errors': [CoreErrorMessages.BULK_DELETE_INVALID_ID.format(id=invalid_id)]
                })
            
            if mode == 'strict' and invalid_ids:
                return self._build_bulk_error_response(
                    results,
                    len(ids),
                    f"Strict mode: {len(invalid_ids)} invalid ID(s) found"
                )
            
            # ===== CALCULATE VALID IDS FOR SET-BASED DELETE =====
            valid_ids = set(ids) - invalid_ids
            
            # ===== COUNT ORPHANED CHILDREN FOR AUDIT =====
            total_orphaned = sum(
                account.direct_child_companies.count()
                for account in accounts_dict.values()
                if str(account.id) in valid_ids
            )
            
            # ===== DELETE OPERATIONS =====
            with disable_signals_with_invalidation(client_id, ['accounts', 'contacts']):
                if mode == 'strict':
                    with transaction.atomic():
                        try:
                            # Store account info before deletion
                            accounts_info = {}
                            for account_id in valid_ids:
                                account = accounts_dict[account_id]
                                accounts_info[account_id] = {
                                    'company_name': account.company_name
                                }
                            
                            # SET-BASED DELETE
                            if valid_ids:
                                deleted_count, deleted_by_model = CompanyAccount.objects.filter(
                                    id__in=valid_ids,
                                    client_id=client_id
                                ).delete()
                                
                                logger.info(
                                    f"Bulk delete accounts: {len(valid_ids)} deleted",
                                    extra={
                                        **ctx,
                                        'deleted_count': deleted_count,
                                        'orphaned_children': total_orphaned,
                                        'cascade': deleted_by_model
                                    }
                                )
                                
                                # Build success results
                                for account_id in valid_ids:
                                    info = accounts_info[account_id]
                                    results['success'].append({
                                        'id': account_id,
                                        'company_name': info['company_name']
                                    })
                        
                        except Exception as e:
                            error_msg = self._format_bulk_error_message(e)
                            return self._build_bulk_error_response(
                                {'success': [], 'failed': results['failed']},
                                len(ids),
                                f"Strict mode failed: {error_msg}"
                            )
                else:
                    # Partial mode
                    accounts_info = {}
                    for account_id in valid_ids:
                        account = accounts_dict[account_id]
                        accounts_info[account_id] = {
                            'company_name': account.company_name
                        }
                    
                    # SET-BASED DELETE
                    try:
                        if valid_ids:
                            deleted_count, deleted_by_model = CompanyAccount.objects.filter(
                                id__in=valid_ids,
                                client_id=client_id
                            ).delete()
                            
                            for account_id in valid_ids:
                                info = accounts_info[account_id]
                                results['success'].append({
                                    'id': account_id,
                                    'company_name': info['company_name']
                                })
                    
                    except Exception as e:
                        error_msg = self._format_bulk_error_message(e)
                        for account_id in valid_ids:
                            info = accounts_info.get(account_id, {'company_name': 'Unknown'})
                            results['failed'].append({
                                'id': account_id,
                                'company_name': info['company_name'],
                                'errors': [error_msg]
                            })
            
            # ===== BUILD RESPONSE =====
            success_count = len(results['success'])
            failed_count = len(results['failed'])
            
            audit_log(
                event='bulk_delete_accounts_completed',
                action='bulk_delete',
                actor_id=str(request.user.id),
                client_id=str(self.get_client_id()),
                target_type='company_account',
                target_count=len(ids),
                outcome='success',
                extra={
                    'deleted': success_count,
                    'failed': failed_count
                }
            )
            
            return self._build_bulk_success_response(results, len(ids), operation='delete', detailed=detailed)
        
        except StandardizedValidationError as e:
            error_msg = str(e)
            if hasattr(e, 'detail') and isinstance(e.detail, dict):
                raw_error = e.detail.get('error', str(e))
                error_msg = str(raw_error)
            
            return self._build_bulk_error_response(
                results={'success': [], 'failed': []},
                total=0,
                error_message=error_msg
            )
    
    # =========================================================================
    # BULK CREATE (CSV Import)
    # =========================================================================
    
    @action(detail=False, methods=['post'], url_path='bulk-create')
    def bulk_create(self, request):
        """
        Create multiple accounts in bulk - IDEMPOTENT wrapper.
        
        Headers:
            Idempotency-Key (optional): Unique key for idempotent operations
            
        Request Body:
            accounts: List[Dict] - Account data objects
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
                    'poll_url': reverse('ops:status', args=[idempotency_key])
                }, status=status.HTTP_202_ACCEPTED, headers={'Retry-After': '2'})
        
        try:
            result = self._bulk_create_impl(request)
            complete_op(
                client_id,
                idempotency_key,
                {'data': result.data, 'http_status': result.status_code}
            )
            return result
        
        except StandardizedValidationError as e:
            fail_op(
                client_id,
                idempotency_key,
                {'message': str(e), 'http_status': status.HTTP_400_BAD_REQUEST}
            )
            raise
        
        except Exception as e:
            fail_op(
                client_id,
                idempotency_key,
                {'message': str(e), 'http_status': status.HTTP_500_INTERNAL_SERVER_ERROR}
            )
            raise
    
    def _bulk_create_impl(self, request):
        """Internal implementation of bulk create."""
        ctx = ctx_from_request(request)
        ctx.update({
            'event': 'bulk_create_accounts',
            'client_id': str(self.get_client_id())
        })
        
        detailed = True  # Always detailed for create
        
        try:
            # ===== INPUT VALIDATION =====
            if not isinstance(request.data, dict):
                raise StandardizedValidationError("Request must be a JSON object")
            
            accounts_data = request.data.get('accounts', [])
            mode = request.data.get('mode', 'partial')
            
            if not isinstance(accounts_data, list):
                raise StandardizedValidationError("'accounts' must be a list")
            
            if not accounts_data:
                raise StandardizedValidationError("No accounts provided")
            
            if mode not in ['partial', 'strict']:
                raise StandardizedValidationError(f"Invalid mode '{mode}'. Must be 'partial' or 'strict'")
            
            if len(accounts_data) > 500:
                raise StandardizedValidationError(
                    CoreErrorMessages.BULK_SIZE_EXCEEDED.format(max_size=500, entity="accounts")
                )
            
            ctx['accounts_count'] = len(accounts_data)
            ctx['mode'] = mode
            logger.info("Starting bulk account creation", extra=ctx)
            
            client_id = self.get_client_id()
            
            audit_log(
                event='bulk_create_accounts',
                action='bulk_create',
                actor_id=str(request.user.id),
                client_id=str(client_id),
                target_type='company_account',
                target_count=len(accounts_data),
                outcome='started',
                extra={'mode': mode}
            )
            
            results = {'success': [], 'failed': [], 'skipped': []}
            
            # ===== PRE-VALIDATION: CHECK FOR DUPLICATES =====
            # Check duplicates in request
            company_keys_in_request = []
            for account_data in accounts_data:
                company_name = account_data.get('company_name', '').upper()
                city = account_data.get('city', '').lower()
                country = account_data.get('country', '').lower()
                key = f"{company_name}|{city}|{country}"
                company_keys_in_request.append(key)
            
            duplicate_keys = [k for k in company_keys_in_request if company_keys_in_request.count(k) > 1]
            
            if duplicate_keys and mode == 'strict':
                raise StandardizedValidationError(
                    f"Strict mode: Duplicate company names in request"
                )
            
            # Check existing in DB
            existing_accounts = CompanyAccount.objects.filter(
                client_id=client_id
            ).values_list('company_name', 'city', 'country')
            
            existing_keys = {
                f"{name.upper()}|{(city or '').lower()}|{(country or '').lower()}"
                for name, city, country in existing_accounts
            }
            
            # ===== PRELOAD FKs =====
            fk_preload = self._preload_bulk_create_fks(accounts_data, client_id)
            owners_map = fk_preload['owners_map']
            parents_map = fk_preload['parents_map']
            
            # ===== CREATE ACCOUNTS =====
            with disable_signals_with_invalidation(client_id, ['accounts']):
                if mode == 'strict':
                    with transaction.atomic():
                        try:
                            for idx, account_data in enumerate(accounts_data):
                                row_num = idx + 1
                                company_name = account_data.get('company_name', '').upper()
                                city = account_data.get('city', '').lower()
                                country = account_data.get('country', '').lower()
                                key = f"{company_name}|{city}|{country}"
                                
                                # Check existing
                                if key in existing_keys:
                                    results['skipped'].append({
                                        'row': row_num,
                                        'company_name': company_name,
                                        'reason': "Account with this name, city, country already exists"
                                    })
                                    continue
                                
                                # Create via serializer
                                serializer = CompanyAccountCreateSerializer(
                                    data=account_data,
                                    context=self.get_serializer_context()
                                )
                                serializer.is_valid(raise_exception=True)
                                account = serializer.save()
                                
                                results['success'].append({
                                    'row': row_num,
                                    'company_name': account.company_name,
                                    'id': str(account.id)
                                })
                                
                                # Add to existing keys to prevent duplicates within batch
                                existing_keys.add(key)
                        
                        except Exception as e:
                            error_msg = self._format_bulk_error_message(e)
                            return self._build_bulk_error_response(
                                {'success': [], 'failed': [], 'skipped': results['skipped']},
                                len(accounts_data),
                                f"Strict mode failed: {error_msg}"
                            )
                else:
                    # Partial mode
                    for idx, account_data in enumerate(accounts_data):
                        row_num = idx + 1
                        company_name = account_data.get('company_name', '').upper()
                        city = account_data.get('city', '').lower()
                        country = account_data.get('country', '').lower()
                        key = f"{company_name}|{city}|{country}"
                        
                        # Check existing
                        if key in existing_keys:
                            results['skipped'].append({
                                'row': row_num,
                                'company_name': company_name,
                                'reason': "Account with this name, city, country already exists"
                            })
                            continue
                        
                        with transaction.atomic():
                            try:
                                serializer = CompanyAccountCreateSerializer(
                                    data=account_data,
                                    context=self.get_serializer_context()
                                )
                                serializer.is_valid(raise_exception=True)
                                account = serializer.save()
                                
                                results['success'].append({
                                    'row': row_num,
                                    'company_name': account.company_name,
                                    'id': str(account.id)
                                })
                                
                                existing_keys.add(key)
                            
                            except StandardizedValidationError as e:
                                error_msg = self._format_bulk_error_message(e)
                                results['failed'].append({
                                    'row': row_num,
                                    'company_name': company_name or 'Unknown',
                                    'errors': [error_msg]
                                })
                            
                            except Exception as e:
                                error_msg = self._format_bulk_error_message(e)
                                results['failed'].append({
                                    'row': row_num,
                                    'company_name': company_name or 'Unknown',
                                    'errors': [error_msg]
                                })
            
            # ===== BUILD RESPONSE =====
            success_count = len(results['success'])
            failed_count = len(results['failed'])
            skipped_count = len(results['skipped'])
            
            audit_log(
                event='bulk_create_accounts_completed',
                action='bulk_create',
                actor_id=str(request.user.id),
                client_id=str(client_id),
                target_type='company_account',
                target_count=len(accounts_data),
                outcome='success',
                extra={
                    'success_count': success_count,
                    'failed_count': failed_count,
                    'skipped_count': skipped_count
                }
            )
            
            return self._build_bulk_success_response(results, len(accounts_data), operation='create', detailed=detailed)
        
        except StandardizedValidationError as e:
            error_msg = str(e)
            if hasattr(e, 'detail') and isinstance(e.detail, dict):
                raw_error = e.detail.get('error', str(e))
                error_msg = str(raw_error)
            
            return self._build_bulk_error_response(
                results={'success': [], 'failed': [], 'skipped': []},
                total=0,
                error_message=error_msg
            )
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _prevalidate_account_fks(self, patch, client_id, account_ids=None):
        """Pre-validate FK fields for bulk update.
        
        Args:
            patch: Dict of fields to update
            client_id: Client UUID for tenant isolation
            account_ids: List of account IDs being updated (for hierarchy validation)
        """
        validated_fks = {}
        account_ids = account_ids or []
        account_ids_set = set(str(aid) for aid in account_ids)
        
        # Account owner validation
        if 'account_owner_id' in patch:
            owner_id = patch['account_owner_id']
            
            if owner_id is None or owner_id == '':
                validated_fks['account_owner_id'] = None
            else:
                try:
                    import uuid
                    uuid.UUID(str(owner_id))
                except ValueError:
                    raise StandardizedValidationError(AccountErrorMessages.INVALID_USER)
                
                try:
                    owner = User.objects.get(id=owner_id)
                    if not owner.is_active:
                        raise StandardizedValidationError(AccountErrorMessages.USER_INACTIVE)
                    validated_fks['account_owner_id'] = owner
                except User.DoesNotExist:
                    raise StandardizedValidationError(UsersErrorMessages.USER_NOT_FOUND)
        
        # Parent company validation
        if 'parent_id' in patch:
            parent_id = patch['parent_id']
            
            if parent_id is None or parent_id == '':
                validated_fks['parent_id'] = None
            else:
                try:
                    import uuid
                    uuid.UUID(str(parent_id))
                except ValueError:
                    raise StandardizedValidationError(AccountErrorMessages.INVALID_PARENT)
                
                # Check self-reference: parent cannot be one of the accounts being updated
                if str(parent_id) in account_ids_set:
                    raise StandardizedValidationError(AccountErrorMessages.SELF_PARENT)
                
                try:
                    parent = CompanyAccount.objects.get(id=parent_id, client_id=client_id)
                    
                    # Check circular hierarchy: parent cannot be a child of any account being updated
                    # Get all children of accounts being updated
                    children_of_selected = set()
                    for account_id in account_ids_set:
                        self._get_all_descendant_ids(account_id, client_id, children_of_selected)
                    
                    if str(parent_id) in children_of_selected:
                        raise StandardizedValidationError(AccountErrorMessages.CIRCULAR_HIERARCHY)
                    
                    validated_fks['parent_id'] = parent
                except CompanyAccount.DoesNotExist:
                    raise StandardizedValidationError(AccountErrorMessages.PARENT_NOT_FOUND)
        
        return validated_fks

    def _get_all_descendant_ids(self, account_id, client_id, descendants_set):
        """Recursively get all descendant IDs of an account."""
        children = CompanyAccount.objects.filter(
            parent_company_id=account_id,
            client_id=client_id
        ).values_list('id', flat=True)
        
        for child_id in children:
            child_id_str = str(child_id)
            if child_id_str not in descendants_set:
                descendants_set.add(child_id_str)
                self._get_all_descendant_ids(child_id, client_id, descendants_set)
    
    def _preload_bulk_create_fks(self, accounts_data, client_id):
        """Preload FKs for bulk create (1 query per FK type)."""
        owner_ids = set()
        parent_ids = set()
        
        for account_data in accounts_data:
            owner_id = account_data.get('account_owner_id')
            if owner_id:
                owner_ids.add(str(owner_id))
            
            parent_id = account_data.get('parent_id')
            if parent_id:
                parent_ids.add(str(parent_id))
        
        # Preload owners
        owners_map = {}
        if owner_ids:
            owners = User.objects.filter(
                id__in=owner_ids,
                client_account_id=client_id,
                is_active=True
            )
            owners_map = {str(u.id): u for u in owners}
        
        # Preload parents
        parents_map = {}
        if parent_ids:
            parents = CompanyAccount.objects.filter(
                id__in=parent_ids,
                client_id=client_id
            )
            parents_map = {str(p.id): p for p in parents}
        
        return {
            'owners_map': owners_map,
            'parents_map': parents_map,
            'stats': {
                'unique_owners': len(owner_ids),
                'unique_parents': len(parent_ids),
                'preloaded_owners': len(owners_map),
                'preloaded_parents': len(parents_map),
            }
        }
    
    def _format_bulk_error_message(self, error):
        """
        Format exception into user-friendly error message for bulk operations.
        
        In bulk context, errors are caught individually per item to allow
        partial success. This method extracts user-friendly messages.
        """
        from rest_framework.exceptions import ValidationError as DRFValidationError
        
        if isinstance(error, StandardizedValidationError):
            if hasattr(error, 'detail'):
                if isinstance(error.detail, dict):
                    raw_error = error.detail.get('error', str(error))
                    return str(raw_error)
                elif isinstance(error.detail, list):
                    return '; '.join(str(e) for e in error.detail)
            return str(error)
        
        # Handle DRF ValidationError (from serializer.is_valid(raise_exception=True))
        if isinstance(error, DRFValidationError):
            if hasattr(error, 'detail'):
                detail = error.detail
                if isinstance(detail, dict):
                    # Format: {'field': [ErrorDetail('msg')]} -> "field: msg"
                    messages = []
                    for field, errors in detail.items():
                        if isinstance(errors, list) and errors:
                            messages.append(f"{field}: {str(errors[0])}")
                        else:
                            messages.append(f"{field}: {str(errors)}")
                    return '; '.join(messages) if messages else str(error)
                elif isinstance(detail, list) and detail:
                    return str(detail[0])
            return str(error)
        
        # Fallback for unexpected exceptions (defensive)
        return str(error) if error else "Processing failed"
    
    def _build_bulk_error_response(self, results, total, error_message):
        """Build standardized error response for bulk operations."""
        # ✅ Ensure error_message is always a plain string
        if error_message and not isinstance(error_message, str):
            error_message = str(error_message)
        
        return Response({
            'success': False,
            'message': error_message,
            'summary': {
                'total': total,
                'success': len(results.get('success', [])),
                'failed': len(results.get('failed', [])),
                'skipped': len(results.get('skipped', []))
            },
            'results': results
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def _build_bulk_success_response(self, results, total, operation='create', detailed=False):
        """Build standardized success response for bulk operations."""
        success_count = len(results.get('success', []))
        failed_count = len(results.get('failed', []))
        skipped_count = len(results.get('skipped', []))
        
        # Determine status
        if success_count == 0 and failed_count > 0:
            status_code = status.HTTP_400_BAD_REQUEST
            success_status = False
            
            # Extract detailed error message from first failed item
            failed_items = results.get('failed', [])
            extracted_message = None
            
            if failed_items:
                first_failed = failed_items[0]
                if isinstance(first_failed, dict) and 'errors' in first_failed:
                    errors_list = first_failed['errors']
                    if errors_list and len(errors_list) > 0:
                        # ✅ Force string conversion for ErrorDetail
                        raw_error = errors_list[0]
                        extracted_message = str(raw_error) if raw_error else None
            
            # Use extracted message if available, otherwise fallback to generic
            if extracted_message:
                message = extracted_message
            else:
                message = f"Bulk {operation} failed: all {failed_count} item(s) failed"
                
        elif failed_count > 0 or skipped_count > 0:
                status_code = status.HTTP_207_MULTI_STATUS
                success_status = 'partial'
                message = f"Bulk {operation}: {success_count} succeeded, {failed_count} failed, {skipped_count} skipped"
        else:
            status_code = status.HTTP_201_CREATED if operation == 'create' else status.HTTP_200_OK
            success_status = True
            message = f"Bulk {operation}: {success_count} item(s) processed successfully"
        
        # Build results
        if not detailed:
            clean_results = {
                'success': [
                    item.get('id') if isinstance(item, dict) else str(item)
                    for item in results.get('success', [])
                ],
                'failed': [
                    item.get('id') if isinstance(item, dict) else str(item)
                    for item in results.get('failed', [])
                ],
                'skipped': [
                    item.get('id') if isinstance(item, dict) else str(item)
                    for item in results.get('skipped', [])
                ]
            }
        else:
            clean_results = {
                'success': results.get('success', []),
                'failed': results.get('failed', []),
                'skipped': results.get('skipped', [])
            }
        
        operation_key_map = {
            'create': 'created',
            'update': 'updated',
            'delete': 'deleted',
        }
        operation_key = operation_key_map.get(operation, 'processed')
        
        return Response({
            'success': success_status,
            'message': message,
            'summary': {
                'requested': total,
                operation_key: success_count,
                'failed': failed_count,
                'skipped': skipped_count,
            },
            'results': clean_results
        }, status=status_code)