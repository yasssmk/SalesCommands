# backend/end_users/views/user_view_bulk.py

"""
User Bulk Operations ViewSet

Handles bulk create/update/delete with idempotency and optimized SQL queries.
This module contains all bulk operations previously in UserViewSet, now separated
for better code organization and maintainability.

Key Features:
- Idempotent operations using Redis-backed idempotency layer
- Set-based SQL operations for optimal performance (1 query instead of N)
- Strict and partial modes for different failure handling strategies
- Comprehensive validation and error handling
- Detailed logging and audit trail
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
from core.logging.helpers import safe_user_context, safe_user_data_context
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from core.cache_utils import disable_signals_with_invalidation
from core.logging import get_logger, ctx_from_request
from ..models import User, UserRole, Team, Organization
from .user_view import UserViewSet



logger = get_logger(__name__)


class UserBulkViewSet(UserViewSet):
    """
    ViewSet for bulk user operations (create/update/delete).
    
    Inherits authentication, permissions, and client scoping from UserViewSet.
    All operations support idempotency via Idempotency-Key header.
    
    Optimizations:
    - Set-based DELETE: One query for N deletions
    - Set-based UPDATE: One query for simple field updates
    - Bulk CREATE: Already optimal via Django's bulk_create
    """
    
    # =========================================================================
    # BULK UPDATE
    # =========================================================================
    throttle_classes = [BulkOperationThrottle]
    
    @action(detail=False, methods=['patch'], url_path='bulk-update')
    def bulk_update(self, request):
        """
        Bulk update users - IDEMPOTENT wrapper.
        
        This wrapper handles idempotency logic. The actual business logic
        is in _bulk_update_impl() to keep concerns separated.
        
        Headers:
            Idempotency-Key (optional): Unique key for idempotent operations
            
        Request Body:
            ids: List[UUID] - User IDs to update
            patch: Dict - Fields to update (is_active, is_superuser, role, team, organization)
            mode: str - 'partial' (default) or 'strict'
            
        Returns:
            200/201: Success with results
            202: Operation in progress (poll via poll_url)
            400: Validation error
            409: Idempotency conflict (same key, different payload)
            500: Server error
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
                else:
                    return Response(result_data, status=status.HTTP_200_OK)

            elif op['status'] == 'failed':
                err = op.get('result') or {}
                return Response({
                    'error': 'Operation failedAA',
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

    # def _bulk_update_impl(self, request):
    #     """
    #     Internal implementation of bulk update with SQL SET-BASED optimization.
        
    #     OPTIMIZATION APPLIED:
    #     - Simple fields (is_active, is_superuser): UPDATE WHERE id IN (...)
    #     - FK fields (role, team, organization): Individual updates with validation
        
    #     This reduces N queries to 1 query for simple field updates.
    #     """
    #     ctx = ctx_from_request(request) 
    #     ctx.update({
    #         'event': 'bulk_update_users',
    #         'client_id': self.get_client_id()
    #     })

    #     detailed = request.query_params.get('detailed', 'false').lower() == 'true'
        
    #     try:
    #         # ===== INPUT VALIDATION =====
    #         if not isinstance(request.data, dict):
    #             raise StandardizedValidationError("Request must be a JSON object")

    #         ids = request.data.get('ids', [])
    #         patch = request.data.get('patch', {})
    #         mode = request.data.get('mode', 'partial')

    #         if not isinstance(ids, list):
    #             raise StandardizedValidationError(
    #                 CoreErrorMessages.BULK_INVALID_FORMAT.format(entity="user IDs")
    #             )

    #         if not ids:
    #             raise StandardizedValidationError(
    #                 CoreErrorMessages.BULK_NO_DATA.format(entity="user IDs")
    #             )

    #         if len(ids) > 500:
    #             raise StandardizedValidationError(
    #                 CoreErrorMessages.BULK_SIZE_EXCEEDED.format(max_size=500, entity="users")
    #             )

    #         if not isinstance(patch, dict):
    #             raise StandardizedValidationError("Patch data must be a JSON object")

    #         if not patch:
    #             raise StandardizedValidationError(CoreErrorMessages.BULK_UPDATE_NO_FIELDS)

    #         if mode not in ['partial', 'strict']:
    #             raise StandardizedValidationError(CoreErrorMessages.BULK_MODE_INVALID)

    #         ctx['ids_count'] = len(ids)
    #         ctx['mode'] = mode
    #         logger.info("Starting bulk user update", extra=ctx)

    #         # ===== VALIDATE ALLOWED FIELDS =====
    #         ALLOWED_FIELDS = {'is_active', 'is_superuser', 'role', 'team', 'organization'}
    #         invalid_fields = set(patch.keys()) - ALLOWED_FIELDS

    #         if invalid_fields:
    #             raise StandardizedValidationError(
    #                 f"Fields not allowed in bulk update: {', '.join(invalid_fields)}. "
    #                 f"Allowed: {', '.join(ALLOWED_FIELDS)}"
    #             )

    #         # ===== SECURITY: PREVENT SELF-MODIFICATION =====
    #         requester_id = str(request.user.id)
    #         if requester_id in ids:
    #             raise StandardizedValidationError(CoreErrorMessages.BULK_UPDATE_SELF_MODIFY)

    #         # ===== FETCH USERS WITH TENANT SCOPING =====
    #         client_id = self.get_client_id()
    #         users_qs = User.objects.filter(
    #             id__in=ids,
    #             client_account_id=client_id
    #         ).select_related('role', 'team', 'organization', 'client_account')
    #         users_dict = {str(u.id): u for u in users_qs}

    #         # ===== CHECK FOR INVALID IDS =====
    #         invalid_ids = set(ids) - set(users_dict.keys())

    #         results = {'success': [], 'failed': []}

    #         for invalid_id in invalid_ids:
    #             results['failed'].append({
    #                 'id': invalid_id,
    #                 'email': 'Unknown',
    #                 'errors': [CoreErrorMessages.BULK_UPDATE_INVALID_ID.format(id=invalid_id)]
    #             })

    #         if mode == 'strict' and invalid_ids:
    #             return self._build_bulk_error_response(
    #                 results,
    #                 len(ids),
    #                 f"Strict mode: {len(invalid_ids)} invalid ID(s) found"
    #             )

    #         # ===== PRE-VALIDATION FOR SET-BASED UPDATES =====
    #         # Separate simple fields (can use set-based UPDATE) from complex fields
    #         simple_fields = {'is_active', 'is_superuser'}
    #         complex_fields = {'role', 'team', 'organization'}
            
    #         simple_updates = {k: v for k, v in patch.items() if k in simple_fields and k not in ['is_active', 'is_superuser']}
    #         complex_updates = {k: v for k, v in patch.items() if k in complex_fields}
            
    #         # For set-based updates, we need to validate all users first
    #         valid_user_ids = []
    #         for idx, user_id in enumerate(ids):
    #             if user_id in invalid_ids:
    #                 continue

    #             user = users_dict[user_id]
                
    #             # Pre-validate this user for the updates
    #             try:
    #                 # Validate simple field updates
    #                 if 'is_active' in simple_updates:
    #                     new_active = simple_updates['is_active']
    #                     if new_active is False and user.is_active and user.is_last_active_admin():
    #                         raise StandardizedValidationError(
    #                             f"Cannot deactivate user '{user.email}': last active administrator"
    #                         )
                    
    #                 if 'is_superuser' in simple_updates:
    #                     new_superuser = simple_updates['is_superuser']
    #                     if new_superuser is False and user.is_superuser and user.is_last_superuser():
    #                         raise StandardizedValidationError(
    #                             f"Cannot remove superuser status from '{user.email}': last superuser"
    #                         )
                    
    #                 # If validation passes, add to valid list
    #                 valid_user_ids.append(user_id)
                    
    #             except StandardizedValidationError as e:
    #                 results['failed'].append({
    #                     'id': user_id,
    #                     'email': user.email,
    #                     'errors': [str(e)]
    #                 })
                    
    #                 if mode == 'strict':
    #                     return self._build_bulk_error_response(
    #                         results,
    #                         len(ids),
    #                         f"Strict mode validation failed: {str(e)}"
    #                     )

    #         # ===== APPLY UPDATES =====
    #         with disable_signals_with_invalidation(client_id, ['users']):
    #             if mode == 'strict':

    #                 validated_fks = {}
    #                 if complex_updates:
    #                     try:
    #                         validated_fks = self._prevalidate_fks(complex_updates, client_id)

    #                         if 'role' in validated_fks:
    #                             self._validate_bulk_role_change_last_admin(
    #                                 client_id=client_id,
    #                                 user_ids_changing_role=valid_user_ids,
    #                                 users_dict=users_dict,
    #                                 new_role_name=validated_fks.get('role_name'),
    #                                 mode='strict'
    #                             )

    #                     except StandardizedValidationError as e:
    #                         error_msg = self._format_bulk_error_message(e)
    #                         ctx['event'] = 'bulk_update_fk_validation_failed'
    #                         ctx['error'] = error_msg
    #                         logger.error("FK validation failed in strict mode", extra=ctx, exc_info=True)
    #                         return self._build_bulk_error_response(
    #                             {'success': [], 'failed': results['failed']},
    #                             len(ids),
    #                             f"Strict mode failed: {error_msg}"
    #                         )
                    
    #                 with transaction.atomic():
    #                     try:
    #                         # SET-BASED UPDATE for simple fields (1 query instead of N)
    #                         if simple_updates and valid_user_ids:
    #                             update_fields = {}
    #                             # if 'is_active' in simple_updates:
    #                             #     update_fields['is_active'] = simple_updates['is_active']
    #                             # if 'is_superuser' in simple_updates:
    #                             #     update_fields['is_superuser'] = simple_updates['is_superuser']
    #                             #     # If promoting to superuser, also set is_staff
    #                             #     if simple_updates['is_superuser'] is True:
    #                             #         update_fields['is_staff'] = True
                                
    #                             if update_fields:
    #                                 User.objects.filter(
    #                                     id__in=valid_user_ids,
    #                                     client_account_id=client_id
    #                                 ).update(**update_fields)
                                
    #                         if 'is_active' in patch:
    #                             if patch['is_active'] is True:
    #                                 validation_result = self._validate_bulk_activation_seats(
    #                                     client_id=client_id,
    #                                     user_ids_to_activate=valid_user_ids,
    #                                     mode=mode
    #                                 )
                                    
    #                                 if validation_result['allowed_ids']:
    #                                     User.objects.filter(
    #                                         id__in=validation_result['allowed_ids'],
    #                                         client_account_id=client_id
    #                                     ).update(is_active=True)
                                    
    #                                 for user_id in validation_result['denied_ids']:
    #                                     user = users_dict[user_id]
    #                                     results['failed'].append({
    #                                         'id': str(user.id),
    #                                         'email': user.email,
    #                                         'errors': [validation_result['warning']]
    #                                     })
                                    
    #                                 valid_user_ids = [uid for uid in valid_user_ids 
    #                                                 if uid not in validation_result['denied_ids']]
    #                             else:
    #                                 self._validate_bulk_deactivation_last_admin(
    #                                     client_id=client_id,
    #                                     user_ids_to_deactivate=valid_user_ids,
    #                                     users_dict=users_dict,
    #                                     mode='strict'
    #                                 )
                                    
    #                                 User.objects.filter(
    #                                     id__in=valid_user_ids,
    #                                     client_account_id=client_id
    #                                 ).update(is_active=False)
                            
    #                         if 'is_superuser' in patch:
    #                             # Valider permissions + dernier superuser
    #                             self._validate_superuser_modification(
    #                                 current_user=request.user,
    #                                 request_data=patch,
    #                                 target_user_ids=valid_user_ids
    #                             )
                                
    #                             # Si validation OK, UPDATE
    #                             update_fields = {'is_superuser': patch['is_superuser']}
    #                             if patch['is_superuser'] is True:
    #                                 update_fields['is_staff'] = True
                                
    #                             User.objects.filter(
    #                                 id__in=valid_user_ids,
    #                                 client_account_id=client_id
    #                             ).update(**update_fields)
                            
    #                         # Complex fields (FK) need individual updates for validation
    #                         if validated_fks and valid_user_ids:
    #                             self._apply_fk_updates_setbased(valid_user_ids, validated_fks, client_id)
                            
    #                         # Build success results
    #                         for user_id in valid_user_ids:
    #                             user = users_dict[user_id]
    #                             # Refresh from DB to get updated values
    #                             user.refresh_from_db()
    #                             results['success'].append({
    #                                 'id': str(user.id),
    #                                 'email': user.email,
    #                                 'name': user.get_full_name()
    #                             })
                            
    #                         # Invalidate cache after commit
    #                         # transaction.on_commit(lambda: invalidate_tag(client_id, 'users')) // on utilise maintenant disable_signals_with_invalidation(client_id, ['users'])

    #                         requester_id = str(request.user.id)
    #                         client = User.objects.get(id=requester_id).client_account
    #                         client.ensure_admin_invariants()


    #                     except Exception as e:
    #                         error_msg = self._format_bulk_error_message(e)
    #                         ctx['event'] = 'bulk_update_strict_mode_failed'
    #                         ctx['error'] = error_msg
    #                         logger.error("Bulk update strict mode failed", extra=ctx, exc_info=True)
    #                         return self._build_bulk_error_response(
    #                             {'success': [], 'failed': results['failed']},
    #                             len(ids),
    #                             f"Strict mode failed: {error_msg}"
    #                         )
    #             else:
    #                 # Partial mode: Best-effort updates
    #                 # ⭐ SET-BASED UPDATE for simple fields
    #                 if simple_updates and valid_user_ids:
    #                     update_fields = {}
    #                     # if 'is_active' in simple_updates:
    #                     #     update_fields['is_active'] = simple_updates['is_active']
    #                     # if 'is_superuser' in simple_updates:
    #                     #     update_fields['is_superuser'] = simple_updates['is_superuser']
    #                     #     if simple_updates['is_superuser'] is True:
    #                     #         update_fields['is_staff'] = True
                        
    #                     if update_fields:
    #                         User.objects.filter(
    #                             id__in=valid_user_ids,
    #                             client_account_id=client_id
    #                         ).update(**update_fields)

    #                 if 'is_active' in patch:

    #                     if patch['is_active'] is True:
    #                         with transaction.atomic(): 
    #                             validation_result = self._validate_bulk_activation_seats(
    #                                 client_id=client_id,
    #                                 user_ids_to_activate=valid_user_ids,
    #                                 mode=mode
    #                             )
                                
    #                         if validation_result['allowed_ids']:
    #                             User.objects.filter(
    #                                 id__in=validation_result['allowed_ids'],
    #                                 client_account_id=client_id
    #                             ).update(is_active=True)
                            
    #                         for user_id in validation_result['denied_ids']:
    #                             user = users_dict[user_id]
    #                             results['failed'].append({
    #                                 'id': str(user.id),
    #                                 'email': user.email,
    #                                 'errors': [validation_result['warning']]
    #                             })
                            
    #                         valid_user_ids = [uid for uid in valid_user_ids 
    #                                         if uid not in validation_result['denied_ids']]
    #                     else:

    #                         with transaction.atomic():
    #                             validation_result = self._validate_bulk_deactivation_last_admin(
    #                                 client_id=client_id,
    #                                 user_ids_to_deactivate=valid_user_ids,
    #                                 users_dict=users_dict,
    #                                 mode='partial'
    #                             )
                                
    #                             # Désactiver seulement allowed_ids (admins exclus automatiquement)
    #                             if validation_result['allowed_ids']:
    #                                 User.objects.filter(
    #                                     id__in=validation_result['allowed_ids'],
    #                                     client_account_id=client_id
    #                                 ).update(is_active=False)
                                
    #                         # Ajouter denied_ids (derniers admins) dans failed avec warning
    #                         for user_id in validation_result['denied_ids']:
    #                             user = users_dict[user_id]
    #                             results['failed'].append({
    #                                 'id': str(user.id),
    #                                 'email': user.email,
    #                                 'errors': [validation_result['warning']]
    #                             })
                            
    #                         # Mettre à jour valid_user_ids pour exclure denied
    #                         # (important pour la suite du traitement)
    #                         valid_user_ids = [uid for uid in valid_user_ids 
    #                                         if uid not in validation_result['denied_ids']]
                            
    #                         # User.objects.filter(
    #                         #     id__in=valid_user_ids,
    #                         #     client_account_id=client_id
    #                         # ).update(is_active=False)
                    
    #                 if 'is_superuser' in patch:
    #                             # Valider permissions + dernier superuser
    #                             self._validate_superuser_modification(
    #                                 current_user=request.user,
    #                                 request_data=patch,
    #                                 target_user_ids=valid_user_ids
    #                             )
                                
    #                             # Si validation OK, UPDATE
    #                             update_fields = {'is_superuser': patch['is_superuser']}
    #                             if patch['is_superuser'] is True:
    #                                 update_fields['is_staff'] = True
                                
    #                             User.objects.filter(
    #                                 id__in=valid_user_ids,
    #                                 client_account_id=client_id
    #                             ).update(**update_fields)


    #                 # Validate then apply SET-BASED (NEW OPTIMIZATION)
    #                 if complex_updates and valid_user_ids:
    #                     # Try to validate FKs for all users
    #                     try:
    #                         validated_fks = self._prevalidate_fks(complex_updates, client_id)

    #                         if 'role' in validated_fks:
    #                             validation_result = self._validate_bulk_role_change_last_admin(
    #                                 client_id=client_id,
    #                                 user_ids_changing_role=valid_user_ids,
    #                                 users_dict=users_dict,
    #                                 new_role_name=validated_fks.get('role_name'),
    #                                 mode='partial'
    #                             )
                                
    #                             # Filtrer valid_user_ids pour exclure les derniers admins protégés
    #                             if validation_result['denied_ids']:
    #                                 # Ajouter denied_ids (derniers admins) dans failed avec warning
    #                                 for user_id in validation_result['denied_ids']:
    #                                     user = users_dict[user_id]
    #                                     results['failed'].append({
    #                                         'id': str(user.id),
    #                                         'email': user.email,
    #                                         'errors': [validation_result['warning']]
    #                                     })
                                    
    #                                 # Mettre à jour valid_user_ids pour exclure denied
    #                                 valid_user_ids = [uid for uid in valid_user_ids 
    #                                                 if uid not in validation_result['denied_ids']]
                            
    #                         # If validation succeeds, apply to all valid users in one go
    #                         with transaction.atomic():
    #                             self._apply_fk_updates_setbased(valid_user_ids, validated_fks, client_id)
                                
    #                     except StandardizedValidationError as e:
    #                         # If FK validation fails globally, it affects all users
    #                         error_msg = self._format_bulk_error_message(e)
    #                         for user_id in valid_user_ids:
    #                             user = users_dict[user_id]
    #                             results['failed'].append({
    #                                 'id': user_id,
    #                                 'email': user.email,
    #                                 'errors': [error_msg]
    #                             })
    #                         # Clear valid_user_ids since all FK updates failed
    #                         valid_user_ids = []
                    
    #                 # Build success results
    #                 for user_id in valid_user_ids:
    #                     user = users_dict[user_id]
    #                     user.refresh_from_db()
    #                     results['success'].append({
    #                         'id': str(user.id),
    #                         'email': user.email,
    #                         'name': user.get_full_name()
    #                     })
                    

    #                 try:
    #                     requester_id = str(request.user.id)
    #                     client = User.objects.get(id=requester_id).client_account
    #                     client.ensure_admin_invariants()
    #                 except Exception as e:
    #                     logger.warning(
    #                         f"Failed to ensure admin invariants after bulk update: {e}",
    #                         extra=ctx
    #                     )

    #                 # ✅ SECURITY FIX: Invalidate cache AFTER all transactions are committed
    #                 # This ensures cache is only invalidated if all database writes succeed
    #                 # If any transaction rolls back, cache invalidation won't happen
    #                 # transaction.on_commit(lambda: invalidate_tag(client_id, 'users'))

    #         success_count = len(results['success'])
    #         failed_count = len(results['failed'])

    #         ctx.update({
    #             'event': 'bulk_update_users_completed',
    #             'requested': len(ids),
    #             'updated': success_count,
    #             'failed': failed_count
    #         })
    #         logger.info("Bulk user update completed", extra=ctx)

    #         return self._build_bulk_success_response(results, len(ids), operation='update', detailed=detailed)

    #     except StandardizedValidationError as e:
    #         if hasattr(e, 'detail') and isinstance(e.detail, dict):
    #             error_msg = e.detail.get('error', str(e))
    #         else:
    #             error_msg = str(e)
            
    #         return self._build_bulk_error_response(
    #             results={'success': [], 'failed': []},
    #             total=0,
    #             error_message=error_msg
    #         )

    def _bulk_update_impl(self, request):
        """
        Internal implementation of bulk update with SQL SET-BASED optimization.
        
        OPTIMIZATION APPLIED:
        - Simple fields (is_active, is_superuser): handled with proper validations
        - FK fields (role, team, organization): Set-based updates after prevalidation
        
        This reduces N queries to 1 query for simple field updates.
        """
        ctx = ctx_from_request(request)
        ctx.update({
            'event': 'bulk_update_users',
            'client_id': self.get_client_id()
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
                    CoreErrorMessages.BULK_INVALID_FORMAT.format(entity="user IDs")
                )

            if not ids:
                raise StandardizedValidationError(
                    CoreErrorMessages.BULK_NO_DATA.format(entity="user IDs")
                )

            if len(ids) > 500:
                raise StandardizedValidationError(
                    CoreErrorMessages.BULK_SIZE_EXCEEDED.format(max_size=500, entity="users")
                )

            if not isinstance(patch, dict):
                raise StandardizedValidationError("Patch data must be a JSON object")

            if not patch:
                raise StandardizedValidationError(CoreErrorMessages.BULK_UPDATE_NO_FIELDS)

            if mode not in ['partial', 'strict']:
                raise StandardizedValidationError(CoreErrorMessages.BULK_MODE_INVALID)

            ctx['ids_count'] = len(ids)
            ctx['mode'] = mode
            logger.info("Starting bulk user update", extra=ctx)

            # ===== VALIDATE ALLOWED FIELDS =====
            ALLOWED_FIELDS = {'is_active', 'is_superuser', 'role', 'team', 'organization'}
            invalid_fields = set(patch.keys()) - ALLOWED_FIELDS

            if invalid_fields:
                raise StandardizedValidationError(
                    f"Fields not allowed in bulk update: {', '.join(invalid_fields)}. "
                    f"Allowed: {', '.join(ALLOWED_FIELDS)}"
                )

            # ===== SECURITY: PREVENT SELF-MODIFICATION =====
            requester_id = str(request.user.id)
            if requester_id in ids:
                raise StandardizedValidationError(CoreErrorMessages.BULK_UPDATE_SELF_MODIFY)

            # ===== FETCH USERS WITH TENANT SCOPING =====
            client_id = self.get_client_id()
            users_qs = User.objects.filter(
                id__in=ids,
                client_account_id=client_id
            ).select_related('role', 'team', 'organization', 'client_account')
            users_dict = {str(u.id): u for u in users_qs}

            # ===== CHECK FOR INVALID IDS =====
            invalid_ids = set(ids) - set(users_dict.keys())

            results = {'success': [], 'failed': []}

            for invalid_id in invalid_ids:
                results['failed'].append({
                    'id': invalid_id,
                    'email': 'Unknown',
                    'errors': [CoreErrorMessages.BULK_UPDATE_INVALID_ID.format(id=invalid_id)]
                })

            if mode == 'strict' and invalid_ids:
                return self._build_bulk_error_response(
                    results,
                    len(ids),
                    f"Strict mode: {len(invalid_ids)} invalid ID(s) found"
                )

            # ===== PRE-VALIDATION FOR SET-BASED UPDATES =====
            # Only keep FK fields here; is_active/is_superuser are handled below with business rules
            complex_fields = {'role', 'team', 'organization'}
            complex_updates = {k: v for k, v in patch.items() if k in complex_fields}
            
            # Build list of users we can operate on (invalid IDs already excluded)
            valid_user_ids = []
            for user_id in ids:
                if user_id in invalid_ids:
                    continue

                # (any per-user pre-validation that doesn't hit DB can be placed here)
                valid_user_ids.append(user_id)

            # ===== APPLY UPDATES =====
            # Use the wrapper to disable signals and guarantee cache invalidation of 'users'
            with disable_signals_with_invalidation(client_id, ['users']):
                if mode == 'strict':
                    validated_fks = {}
                    if complex_updates:
                        try:
                            validated_fks = self._prevalidate_fks(complex_updates, client_id)

                            if 'role' in validated_fks:
                                self._validate_bulk_role_change_last_admin(
                                    client_id=client_id,
                                    user_ids_changing_role=valid_user_ids,
                                    users_dict=users_dict,
                                    new_role_name=validated_fks.get('role_name'),
                                    mode='strict'
                                )

                        except StandardizedValidationError as e:
                            error_msg = self._format_bulk_error_message(e)
                            ctx['event'] = 'bulk_update_fk_validation_failed'
                            ctx['error'] = error_msg
                            logger.error("FK validation failed in strict mode", extra=ctx, exc_info=True)
                            return self._build_bulk_error_response(
                                {'success': [], 'failed': results['failed']},
                                len(ids),
                                f"Strict mode failed: {error_msg}"
                            )
                    
                    with transaction.atomic():
                        try:
                            # --- is_active ---
                            if 'is_active' in patch:
                                if patch['is_active'] is True:
                                    validation_result = self._validate_bulk_activation_seats(
                                        client_id=client_id,
                                        user_ids_to_activate=valid_user_ids,
                                        mode=mode
                                    )
                                    
                                    if validation_result['allowed_ids']:
                                        User.objects.filter(
                                            id__in=validation_result['allowed_ids'],
                                            client_account_id=client_id
                                        ).update(is_active=True)
                                    
                                    for user_id in validation_result['denied_ids']:
                                        user = users_dict[user_id]
                                        results['failed'].append({
                                            'id': str(user.id),
                                            'email': user.email,
                                            'errors': [validation_result['warning']]
                                        })
                                    
                                    valid_user_ids = [uid for uid in valid_user_ids 
                                                    if uid not in validation_result['denied_ids']]
                                else:
                                    self._validate_bulk_deactivation_last_admin(
                                        client_id=client_id,
                                        user_ids_to_deactivate=valid_user_ids,
                                        users_dict=users_dict,
                                        mode='strict'
                                    )
                                    
                                    User.objects.filter(
                                        id__in=valid_user_ids,
                                        client_account_id=client_id
                                    ).update(is_active=False)
                            
                            # --- is_superuser ---
                            if 'is_superuser' in patch:
                                # Validate permissions + last superuser protection
                                self._validate_superuser_modification(
                                    current_user=request.user,
                                    request_data=patch,
                                    target_user_ids=valid_user_ids
                                )
                                
                                update_fields = {'is_superuser': patch['is_superuser']}
                                if patch['is_superuser'] is True:
                                    update_fields['is_staff'] = True
                                
                                User.objects.filter(
                                    id__in=valid_user_ids,
                                    client_account_id=client_id
                                ).update(**update_fields)
                            
                            # --- FK fields (set-based) ---
                            if validated_fks and valid_user_ids:
                                self._apply_fk_updates_setbased(valid_user_ids, validated_fks, client_id)
                            
                            # Build success results
                            for user_id in valid_user_ids:
                                user = users_dict[user_id]
                                user.refresh_from_db()
                                results['success'].append({
                                    'id': str(user.id),
                                    'email': user.email,
                                    'name': user.get_full_name()
                                })
                            
                            # Ensure admin invariants
                            requester_id_local = str(request.user.id)
                            client = User.objects.get(id=requester_id_local).client_account
                            client.ensure_admin_invariants()

                        except Exception as e:
                            error_msg = self._format_bulk_error_message(e)
                            ctx['event'] = 'bulk_update_strict_mode_failed'
                            ctx['error'] = error_msg
                            logger.error("Bulk update strict mode failed", extra=ctx, exc_info=True)
                            return self._build_bulk_error_response(
                                {'success': [], 'failed': results['failed']},
                                len(ids),
                                f"Strict mode failed: {error_msg}"
                            )
                else:
                    # Partial mode: Best-effort updates
                    # --- is_active ---
                    if 'is_active' in patch:

                        if patch['is_active'] is True:
                            with transaction.atomic(): 
                                validation_result = self._validate_bulk_activation_seats(
                                    client_id=client_id,
                                    user_ids_to_activate=valid_user_ids,
                                    mode=mode
                                )
                                
                            if validation_result['allowed_ids']:
                                User.objects.filter(
                                    id__in=validation_result['allowed_ids'],
                                    client_account_id=client_id
                                ).update(is_active=True)
                            
                            for user_id in validation_result['denied_ids']:
                                user = users_dict[user_id]
                                results['failed'].append({
                                    'id': str(user.id),
                                    'email': user.email,
                                    'errors': [validation_result['warning']]
                                })
                            
                            valid_user_ids = [uid for uid in valid_user_ids 
                                            if uid not in validation_result['denied_ids']]
                        else:
                            with transaction.atomic():
                                validation_result = self._validate_bulk_deactivation_last_admin(
                                    client_id=client_id,
                                    user_ids_to_deactivate=valid_user_ids,
                                    users_dict=users_dict,
                                    mode='partial'
                                )
                                
                                # Deactivate only allowed_ids (admins excluded automatically)
                                if validation_result['allowed_ids']:
                                    User.objects.filter(
                                        id__in=validation_result['allowed_ids'],
                                        client_account_id=client_id
                                    ).update(is_active=False)
                            
                            # Add denied_ids (last admins) to failed with warning
                            for user_id in validation_result['denied_ids']:
                                user = users_dict[user_id]
                                results['failed'].append({
                                    'id': str(user.id),
                                    'email': user.email,
                                    'errors': [validation_result['warning']]
                                })
                            
                            # Update valid_user_ids to exclude denied
                            valid_user_ids = [uid for uid in valid_user_ids 
                                            if uid not in validation_result['denied_ids']]
                    
                    # --- is_superuser ---
                    if 'is_superuser' in patch:
                        self._validate_superuser_modification(
                            current_user=request.user,
                            request_data=patch,
                            target_user_ids=valid_user_ids
                        )
                        
                        update_fields = {'is_superuser': patch['is_superuser']}
                        if patch['is_superuser'] is True:
                            update_fields['is_staff'] = True
                        
                        User.objects.filter(
                            id__in=valid_user_ids,
                            client_account_id=client_id
                        ).update(**update_fields)

                    # --- FK fields (validate then apply set-based) ---
                    if complex_updates and valid_user_ids:
                        try:
                            validated_fks = self._prevalidate_fks(complex_updates, client_id)

                            if 'role' in validated_fks:
                                validation_result = self._validate_bulk_role_change_last_admin(
                                    client_id=client_id,
                                    user_ids_changing_role=valid_user_ids,
                                    users_dict=users_dict,
                                    new_role_name=validated_fks.get('role_name'),
                                    mode='partial'
                                )
                                
                                if validation_result['denied_ids']:
                                    for user_id in validation_result['denied_ids']:
                                        user = users_dict[user_id]
                                        results['failed'].append({
                                            'id': str(user.id),
                                            'email': user.email,
                                            'errors': [validation_result['warning']]
                                        })
                                    
                                    valid_user_ids = [uid for uid in valid_user_ids 
                                                    if uid not in validation_result['denied_ids']]
                            
                            # Apply to all valid users in one go
                            with transaction.atomic():
                                self._apply_fk_updates_setbased(valid_user_ids, validated_fks, client_id)
                                
                        except StandardizedValidationError as e:
                            error_msg = self._format_bulk_error_message(e)
                            for user_id in valid_user_ids:
                                user = users_dict[user_id]
                                results['failed'].append({
                                    'id': user_id,
                                    'email': user.email,
                                    'errors': [error_msg]
                                })
                            valid_user_ids = []
                    
                    # Build success results
                    for user_id in valid_user_ids:
                        user = users_dict[user_id]
                        user.refresh_from_db()
                        results['success'].append({
                            'id': str(user.id),
                            'email': user.email,
                            'name': user.get_full_name()
                        })
                    
                    try:
                        requester_id_local = str(request.user.id)
                        client = User.objects.get(id=requester_id_local).client_account
                        client.ensure_admin_invariants()
                    except Exception as e:
                        ctx_safe = {**ctx, 'error': str(e)[:200]}
                        logger.warning("Failed to ensure admin invariants", extra=ctx_safe)

            # ===== BUILD RESPONSE =====
            success_count = len(results['success'])
            failed_count = len(results['failed'])

            ctx_safe = {
                **ctx,
                'event': 'bulk_update_users_completed',
                'requested': len(ids),
                'updated': success_count,
                'failed': failed_count
            }
            logger.info("Bulk user update completed", extra=ctx_safe)

            return self._build_bulk_success_response(results, len(ids), operation='update', detailed=detailed)

        except StandardizedValidationError as e:
            if hasattr(e, 'detail') and isinstance(e.detail, dict):
                error_msg = e.detail.get('error', str(e))
            else:
                error_msg = str(e)
            
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
        Physically delete multiple users in bulk (hard delete) - IDEMPOTENT wrapper.
        
        Headers:
            Idempotency-Key (optional): Unique key for idempotent operations
            
        Request Body:
            ids: List[UUID] - User IDs to delete
            mode: str - 'partial' (default) or 'strict'
            
        Returns:
            200: Success with results
            202: Operation in progress
            400: Validation error
            409: Idempotency conflict
            500: Server error
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
                else:
                    return Response(result_data, status=status.HTTP_200_OK)

            elif op['status'] == 'failed':
                err = op.get('result') or {}
                return Response({
                    'error': 'Operation failedBB',
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
        """
        Internal implementation of bulk delete with SQL SET-BASED optimization.
        
        OPTIMIZATION APPLIED:
        - DELETE WHERE id IN (valid_ids) instead of looping user.delete()
        - This reduces N queries to 1 query for all deletions
        
        Business rules preserved:
        - Last admin protection
        - Self-delete prevention
        - Tenant scoping
        - Admin invariants enforcement
        """

        ctx = ctx_from_request(request)
        ctx.update({
            'event': 'bulk_delete_users_hard',
            'client_id': self.get_client_id()
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
                    CoreErrorMessages.BULK_INVALID_FORMAT.format(entity="user IDs")
                )

            if not ids:
                raise StandardizedValidationError(CoreErrorMessages.BULK_DELETE_NO_IDS)

            if len(ids) > 500:
                raise StandardizedValidationError(
                    CoreErrorMessages.BULK_SIZE_EXCEEDED.format(max_size=500, entity="users")
                )

            if mode not in ['partial', 'strict']:
                raise StandardizedValidationError(CoreErrorMessages.BULK_MODE_INVALID)

            ctx['ids_count'] = len(ids)
            ctx['mode'] = mode
            logger.info("Starting bulk user delete (hard)", extra=ctx)

            # ===== SECURITY: PREVENT SELF-DELETE =====
            requester_id = str(request.user.id)
            if requester_id in ids:
                raise StandardizedValidationError(CoreErrorMessages.BULK_DELETE_SELF)

            # ===== FETCH USERS WITH TENANT SCOPING =====
            client_id = self.get_client_id()
            users_qs = User.objects.filter(
                id__in=ids,
                client_account_id=client_id
            ).select_related('role', 'team', 'organization', 'client_account')
            users_dict = {str(u.id): u for u in users_qs}

            # ===== CHECK FOR INVALID IDS =====
            invalid_ids = set(ids) - set(users_dict.keys())
            
            results = {'success': [], 'failed': []}

            for invalid_id in invalid_ids:
                results['failed'].append({
                    'id': invalid_id,
                    'email': 'Unknown',
                    'errors': [CoreErrorMessages.BULK_DELETE_INVALID_ID.format(id=invalid_id)]
                })

            if mode == 'strict' and invalid_ids:
                return self._build_bulk_error_response(
                    results,
                    len(ids),
                    f"Strict mode: {len(invalid_ids)} invalid ID(s) found"
                )

            # ===== PRE-VALIDATION: CHECK FOR PROTECTED USERS =====
            protected_users = []
            
            for idx, user_id in enumerate(ids):
                if user_id in invalid_ids:
                    continue
                    
                user = users_dict[user_id]
                
                if user.is_last_active_admin():
                    protected_users.append({
                        'id': str(user.id),
                        'email': user.email,
                        'reason': CoreErrorMessages.BULK_DELETE_LAST_ADMIN.format(email=user.email)
                    })

            if mode == 'strict' and protected_users:
                for protected in protected_users:
                    results['failed'].append({
                        'id': protected['id'],
                        'email': protected['email'],
                        'errors': [protected['reason']]
                    })
                
                return self._build_bulk_error_response(
                    results,
                    len(ids),
                    f"Strict mode: {len(protected_users)} protected user(s) found"
                )

            # ===== CALCULATE VALID IDS FOR SET-BASED DELETE =====
            protected_ids = {p['id'] for p in protected_users}
            valid_ids = set(ids) - invalid_ids - protected_ids

            # ===== DELETE OPERATIONS =====
            with disable_signals_with_invalidation(client_id, ['users']):
                if mode == 'strict':
                    # Strict mode: All-or-nothing transaction
                    with transaction.atomic():
                        try:
                            # Store user info before deletion for response
                            users_info = {}
                            for user_id in valid_ids:
                                user = users_dict[user_id]
                                users_info[user_id] = {
                                    'email': user.email,
                                    'name': user.get_full_name()
                                }
                            
                            # ⭐ SET-BASED DELETE: 1 query instead of N
                            if valid_ids:

                                deleted_count,  deleted_by_model = User.objects.filter(
                                    id__in=valid_ids,
                                    client_account_id=client_id
                                ).delete()

                                # Log structuré des cascades
                                cascade_summary = ', '.join([
                                    f"{model.split('.')[-1]}={count}" 
                                    for model, count in deleted_by_model.items() 
                                    if model != 'end_users.User'
                                ])

                                logger.info(
                                    f"[Bulk Delete - Strict Mode] Successfully deleted {len(valid_ids)} users | "
                                    f"Total objects: {deleted_count} | "
                                    f"Cascades: {cascade_summary or 'none'}",
                                    extra=ctx
                                )
                                
                                # Build success results
                                for user_id in valid_ids:
                                    info = users_info[user_id]
                                    results['success'].append({
                                        'id': user_id,
                                        'email': info['email'],
                                        'name': info['name']
                                    })
                            
                            # Add protected users to failed
                            for protected in protected_users:
                                results['failed'].append({
                                    'id': protected['id'],
                                    'email': protected['email'],
                                    'errors': [protected['reason']]
                                })
                            
                            # Ensure admin invariants
                            client = User.objects.get(id=requester_id).client_account
                            client.ensure_admin_invariants()
                            
                            # Invalidation cache APRÈS commit
                            # transaction.on_commit(lambda: invalidate_tag(client_id, 'users'))
                            
                        except Exception as e:
                            error_msg = self._format_bulk_error_message(e)
                            ctx['event'] = 'bulk_delete_strict_mode_failed'
                            ctx['error'] = error_msg
                            logger.error("Bulk delete strict mode failed", extra=ctx, exc_info=True)
                            
                            return self._build_bulk_error_response(
                                {'success': [], 'failed': results['failed']},
                                len(ids),
                                f"Strict mode failed: {error_msg}"
                            )
                else:
                    # Partial mode: Best-effort deletion
                    # Store user info before deletion
                    users_info = {}
                    for user_id in valid_ids:
                        user = users_dict[user_id]
                        users_info[user_id] = {
                            'email': user.email,
                            'name': user.get_full_name()
                        }
                    
                    # Add protected users to failed first
                    for protected in protected_users:
                        results['failed'].append({
                            'id': protected['id'],
                            'email': protected['email'],
                            'errors': [protected['reason']]
                        })
                    
                    # ⭐ SET-BASED DELETE: 1 query instead of N
                    try:
                        if valid_ids:
                            deleted_count, deleted_by_model = User.objects.filter(
                                id__in=valid_ids,
                                client_account_id=client_id
                            ).delete()

                            # Log structuré des cascades
                            cascade_summary = ', '.join([
                                f"{model.split('.')[-1]}={count}" 
                                for model, count in deleted_by_model.items() 
                                if model != 'end_users.User'
                            ])

                            ctx_safe = {
                                **ctx,
                                'deleted_users': len(valid_ids),
                                'total_objects': deleted_count,
                                'cascade_summary': cascade_summary or 'none'
                            }
                            logger.info("Bulk delete completed", extra=ctx_safe)
                            
                            # Build success results
                            for user_id in valid_ids:
                                info = users_info[user_id]
                                results['success'].append({
                                    'id': user_id,
                                    'email': info['email'],
                                    'name': info['name']
                                })
                        
                        # Ensure admin invariants (partial mode)
                        try:
                            client = User.objects.get(id=requester_id).client_account
                            client.ensure_admin_invariants()
                        except Exception as e:
                            logger.warning(f"Failed to ensure admin invariants: {e}", extra=ctx)
                        
                        # ✅ SECURITY FIX: Invalidate cache AFTER all transactions are committed
                        # This ensures cache is only invalidated if the DELETE succeeds and commits
                        # If the outer try block fails, cache invalidation won't happen
                        # transaction.on_commit(lambda: invalidate_tag(client_id, 'users'))
                        
                    except Exception as e:
                        error_msg = self._format_bulk_error_message(e)
                        ctx['event'] = 'bulk_delete_unexpected_error'
                        ctx['error'] = str(e)
                        logger.error("Unexpected error in bulk delete", extra=ctx, exc_info=True)
                        
                        # Mark all as failed if set-based delete fails
                        for user_id in valid_ids:
                            info = users_info.get(user_id, {'email': 'Unknown', 'name': 'Unknown'})
                            results['failed'].append({
                                'id': user_id,
                                'email': info['email'],
                                'errors': [error_msg]
                            })

            # ===== BUILD RESPONSE =====
            success_count = len(results['success'])
            failed_count = len(results['failed'])

            ctx.update({
                'event': 'bulk_delete_users_completed',
                'requested': len(ids),
                'deleted': success_count,
                'failed': failed_count
            })
            logger.info("Bulk user deletion completed", extra=ctx)

            return self._build_bulk_success_response(results, len(ids), operation='delete', detailed=detailed)

        except StandardizedValidationError as e:
            if hasattr(e, 'detail') and isinstance(e.detail, dict):
                error_msg = e.detail.get('error', str(e))
            else:
                error_msg = str(e)
            
            return self._build_bulk_error_response(
                results={'success': [], 'failed': []},
                total=0,
                error_message=error_msg
            )

    
    # =========================================================================
    # BULK CREATE  
    # =========================================================================
        
    
    @action(detail=False, methods=['post'], url_path='bulk-create')
    def bulk_create(self, request):
        """
        Create multiple users in bulk - IDEMPOTENT wrapper.
        
        Headers:
            Idempotency-Key (optional): Unique key for idempotent operations
            
        Request Body:
            users: List[Dict] - User data objects
            mode: str - 'partial' (default) or 'strict'
            
        Returns:
            200/201: Success with results
            202: Operation in progress
            400: Validation error
            409: Idempotency conflict
            500: Server error
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
                else:
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
    
    def _preload_bulk_create_fks(self, users_data, client_id):
        """
       Preload all FKs in 3 SELECT queries instead of N×3.

        This method eliminates N×3 SELECT queries by loading all referenced FKs upfront.
        Used by _bulk_create_impl to optimize FK validation before user creation loop.

        Performance Impact:
        - Before: 100 users × 3 FKs = ~300 SELECT queries
        - After: 3 SELECT queries (1 per FK type)
        - Speedup: ~100x for FK validation phase

        Args:
            users_data: List of user dicts to create
            client_id: Current client ID for tenant scoping

        Returns:
            Dict with lookup maps:
            {
                'roles_map': {role_id: UserRole instance, ...},
                'teams_map': {team_id: Team instance, ...},
                'orgs_map': {org_id: Organization instance, ...},
                'stats': {
                    'unique_roles': int,
                    'unique_teams': int,
                    'unique_orgs': int,
                    'total_fks_preloaded': int
                }
            }

        Example:
            users_data = [
                {'email': 'a@test.com', 'role': 'uuid-1', 'team': 'uuid-2'},
                {'email': 'b@test.com', 'role': 'uuid-1', 'team': 'uuid-3'},
                {'email': 'c@test.com', 'role': 'uuid-4'},
            ]

            result = self._preload_bulk_create_fks(users_data, client_id)
            # result['roles_map'] = {'uuid-1': <Role obj>, 'uuid-4': <Role obj>}
            # result['teams_map'] = {'uuid-2': <Team obj>, 'uuid-3': <Team obj>}
            # result['stats'] = {'unique_roles': 2, 'unique_teams': 2, ...}
        """
        # ===== EXTRACT UNIQUE FK IDS FROM PAYLOAD =====
        role_ids = set()
        team_ids = set()
        org_ids = set()

        for user_data in users_data:
            # Extract role ID if present and not null/empty
            role_id = user_data.get('role')
            if role_id and role_id != '':
                role_ids.add(str(role_id))

            # Extract team ID if present and not null/empty
            team_id = user_data.get('team')
            if team_id and team_id != '':
                team_ids.add(str(team_id))

            # Extract organization ID if present and not null/empty
            org_id = user_data.get('organization')
            if org_id and org_id != '':
                org_ids.add(str(org_id))

        # ===== PRELOAD ROLES (1 SELECT) =====
        roles_map = {}
        if role_ids:
            logger.info(
                f"[PHASE 2.E.1] Preloading {len(role_ids)} unique roles for bulk create",
                extra={'client_id': str(client_id), 'role_ids_count': len(role_ids)}
            )

            roles = UserRole.objects.filter(
                id__in=role_ids,
                client_account_id=client_id
            )

            # Build lookup map: {str(id): instance}
            roles_map = {str(role.id): role for role in roles}

            logger.info(
                f"[PHASE 2.E.1] Preloaded {len(roles_map)} roles successfully",
                extra={'client_id': str(client_id), 'loaded_count': len(roles_map)}
            )

        # ===== PRELOAD TEAMS (1 SELECT with select_related for org validation) =====
        teams_map = {}
        if team_ids:
            logger.info(
                f"[PHASE 2.E.1] Preloading {len(team_ids)} unique teams for bulk create",
                extra={'client_id': str(client_id), 'team_ids_count': len(team_ids)}
            )

            teams = Team.objects.filter(
                id__in=team_ids,
                organization__client_account_id=client_id  # Scoped via organization
            ).select_related('organization')  # Avoid N+1 for org validation

            # Build lookup map: {str(id): instance}
            teams_map = {str(team.id): team for team in teams}

            logger.info(
                f"[PHASE 2.E.1] Preloaded {len(teams_map)} teams successfully",
                extra={'client_id': str(client_id), 'loaded_count': len(teams_map)}
            )

        # ===== PRELOAD ORGANIZATIONS (1 SELECT) =====
        orgs_map = {}
        if org_ids:
            logger.info(
                f"[PHASE 2.E.1] Preloading {len(org_ids)} unique organizations for bulk create",
                extra={'client_id': str(client_id), 'org_ids_count': len(org_ids)}
            )

            orgs = Organization.objects.filter(
                id__in=org_ids,
                client_account_id=client_id
            )

            # Build lookup map: {str(id): instance}
            orgs_map = {str(org.id): org for org in orgs}

            logger.info(
                f"[PHASE 2.E.1] Preloaded {len(orgs_map)} organizations successfully",
                extra={'client_id': str(client_id), 'loaded_count': len(orgs_map)}
            )

        # ===== BUILD RESULT WITH STATS =====
        result = {
            'roles_map': roles_map,
            'teams_map': teams_map,
            'orgs_map': orgs_map,
            'stats': {
                'unique_roles': len(role_ids),
                'unique_teams': len(team_ids),
                'unique_orgs': len(org_ids),
                'total_fks_preloaded': len(roles_map) + len(teams_map) + len(orgs_map),
                'preloaded_roles': len(roles_map),
                'preloaded_teams': len(teams_map),
                'preloaded_orgs': len(orgs_map)
            }
        }

        logger.info(
            f"[PHASE 2.E.1] FK preloading completed for bulk create",
            extra={
                'client_id': str(client_id),
                **result['stats']
            }
        )

        return result
    
    def _validate_bulk_create_fks_in_memory(self, users_data, roles_map, teams_map, orgs_map, mode, client_id):
        """
        ⭐ Validate FKs in memory without SQL queries.
        
        This method validates all FK references using preloaded maps from _preload_bulk_create_fks().
        No database queries are executed during validation - everything happens in memory.
        
        Performance Impact:
        - Before: N×3 SELECT queries during validation loop
        - After: 0 SELECT queries (pure in-memory validation)
        - Speedup: ~100x for FK validation phase
        
        Args:
            users_data: List of user dicts to create
            roles_map: Preloaded roles map {role_id: UserRole instance}
            teams_map: Preloaded teams map {team_id: Team instance}
            orgs_map: Preloaded orgs map {org_id: Organization instance}
            mode: 'strict' or 'partial'
            client_id: Current client ID for logging
            
        Returns:
            Tuple (valid_users, failed_users):
            - valid_users: List of (row_num, user_data) tuples that passed validation
            - failed_users: List of dicts with {'row': int, 'email': str, 'errors': [str]}
            
        Raises:
            StandardizedValidationError: If mode='strict' and any FK validation fails
            
        Example:
            valid, failed = self._validate_bulk_create_fks_in_memory(
                users_data, roles_map, teams_map, orgs_map, 'partial', client_id
            )
            # valid = [(1, user_data_1), (3, user_data_3), ...]
            # failed = [{'row': 2, 'email': 'bad@test.com', 'errors': ['Role not found']}]
        """
        valid_users = []
        failed_users = []
        
        logger.info(
            f"[PHASE 2.E.2] Starting in-memory FK validation for {len(users_data)} users",
            extra={
                'client_id': str(client_id),
                'mode': mode,
                'users_count': len(users_data),
                'roles_available': len(roles_map),
                'teams_available': len(teams_map),
                'orgs_available': len(orgs_map)
            }
        )
        
        # ===== VALIDATE EACH USER IN MEMORY =====
        for idx, user_data in enumerate(users_data):
            row_num = idx + 1
            errors = []
            email = user_data.get('email', 'Unknown')
            
            # ===== VALIDATE ROLE FK =====
            role_id = user_data.get('role')
            if role_id and role_id != '':
                role_id_str = str(role_id)
                
                # Check if role exists in preloaded map
                if role_id_str not in roles_map:
                    error_msg = f"Role '{role_id}' not found in your organization"
                    errors.append(error_msg)
                    
                    logger.warning(
                        f" Row {row_num}: Invalid role FK",
                        extra={
                            'client_id': str(client_id),
                            'row': row_num,
                            'user_id': user_data.get('id', 'pending'),
                            'role_id': role_id_str,
                            'available_roles': list(roles_map.keys())
                        }
                    )
            
            # ===== VALIDATE TEAM FK =====
            team_id = user_data.get('team')
            if team_id and team_id != '':
                team_id_str = str(team_id)
                
                # Check if team exists in preloaded map
                if team_id_str not in teams_map:
                    error_msg = f"Team '{team_id}' not found or doesn't belong to your organization"
                    errors.append(error_msg)
                    
                    logger.warning(
                        f" Row {row_num}: Invalid team FK",
                        extra={
                            'client_id': str(client_id),
                            'row': row_num,
                            'user_id': user_data.get('id', 'pending'),
                            'team_id': team_id_str,
                            'available_teams': list(teams_map.keys())
                        }
                    )
            
            # ===== VALIDATE ORGANIZATION FK =====
            org_id = user_data.get('organization')
            if org_id and org_id != '':
                org_id_str = str(org_id)
                
                # Check if organization exists in preloaded map
                if org_id_str not in orgs_map:
                    error_msg = f"Organization '{org_id}' not found in your organization"
                    errors.append(error_msg)
                    
                    logger.warning(
                        f"[PHASE 2.E.2] Row {row_num}: Invalid organization FK",
                        extra={
                            'client_id': str(client_id),
                            'row': row_num,
                            'user_id': user_data.get('id', 'pending'),
                            'org_id': org_id_str,
                            'available_orgs': list(orgs_map.keys())
                        }
                    )
            
            # ===== ADDITIONAL VALIDATION: Team belongs to Organization =====
            if team_id and team_id != '' and org_id and org_id != '':
                team_id_str = str(team_id)
                org_id_str = str(org_id)
                
                # Both must be valid first
                if team_id_str in teams_map and org_id_str in orgs_map:
                    team_instance = teams_map[team_id_str]
                    org_instance = orgs_map[org_id_str]
                    
                    # Check if team belongs to the specified organization
                    if str(team_instance.organization.id) != org_id_str:
                        error_msg = (
                            f"Team '{team_id}' does not belong to organization '{org_id}'. "
                            f"Team belongs to organization '{team_instance.organization.name}'"
                        )
                        errors.append(error_msg)
                        
                        logger.warning(
                            f"Row {row_num}: Team-Organization mismatch",
                            extra={
                                'client_id': str(client_id),
                                'row': row_num,
                                'user_id': user_data.get('id', 'pending'),
                                'team_id': team_id_str,
                                'requested_org_id': org_id_str,
                                'actual_org_id': str(team_instance.organization.id),
                                'actual_org_name': team_instance.organization.name
                            }
                        )
            
            # ===== HANDLE VALIDATION RESULTS =====
            if errors:
                # User has FK validation errors
                failed_users.append({
                    'row': row_num,
                    'email': email,
                    'errors': errors
                })
                
                # In strict mode: fail fast on first error
                if mode == 'strict':
                    error_summary = '; '.join(errors)
                    logger.error(
                        f"Strict mode: FK validation failed at row {row_num}",
                        extra={
                            'client_id': str(client_id),
                            'row': row_num,
                            'user_id': user_data.get('id', 'pending'),
                            'errors': errors,
                            'mode': mode
                        }
                    )
                    raise StandardizedValidationError(
                        f"Row {row_num} ({email}): {error_summary}"
                    )
            else:
                # User passed all FK validations
                valid_users.append((row_num, user_data))
        
        # ===== LOG VALIDATION SUMMARY =====
        logger.info(
            f"In-memory FK validation completed",
            extra={
                'client_id': str(client_id),
                'mode': mode,
                'total_users': len(users_data),
                'valid_users': len(valid_users),
                'failed_users': len(failed_users),
                'validation_success_rate': f"{(len(valid_users)/len(users_data)*100):.1f}%"
            }
        )
        
        return valid_users, failed_users

    def _bulk_create_impl(self, request):
        """
        Internal implementation of bulk create.
        
        OPTIMIZATION NOTE:
        Already optimal - Django's serializer.save() uses bulk_create internally.
        No further optimization needed here.
        """


        ctx = ctx_from_request(request)
        ctx.update({
            'event': 'bulk_create_users',
            'client_id': self.get_client_id()
        })

        detailed = True 

        try:
            # ===== INPUT VALIDATION =====
            if not isinstance(request.data, dict):
                raise StandardizedValidationError("Request must be a JSON object")

            users_data = request.data.get('users', [])
            mode = request.data.get('mode', 'partial')

            if not isinstance(users_data, list):
                raise StandardizedValidationError("'users' must be a list")

            if not users_data:
                raise StandardizedValidationError("No users provided")

            if mode not in ['partial', 'strict']:
                raise StandardizedValidationError(f"Invalid mode '{mode}'. Must be 'partial' or 'strict'")

            if len(users_data) > 500:
                raise StandardizedValidationError(
                    CoreErrorMessages.BULK_SIZE_EXCEEDED.format(max_size=500, entity="users")
                )

            ctx['users_count'] = len(users_data)
            ctx['mode'] = mode
            logger.info("Starting bulk user creation", extra=ctx)

            # ===== PREPARE CLIENT ID =====
            client_id = self.get_client_id()

            results = {'success': [], 'failed': [], 'skipped': []}

            # ===== PRE-VALIDATION: CHECK FOR DUPLICATE EMAILS =====
            emails_in_request = [u.get('email', '').lower() for u in users_data if u.get('email')]
            duplicate_emails = [email for email in emails_in_request if emails_in_request.count(email) > 1]
            
            if duplicate_emails and mode == 'strict':
                raise StandardizedValidationError(
                    f"Strict mode: Duplicate emails in request: {', '.join(set(duplicate_emails))}"
                )

            # Check existing emails in DB
            existing_emails = set(
                User.objects.filter(
                    email__in=emails_in_request,
                    client_account_id=client_id
                ).values_list('email', flat=True)
            )

            # ===== VALIDATION SEATS POUR USERS ACTIFS =====
            validation_result = self._validate_bulk_creation_seats(
                client_id=client_id,
                users_data=users_data,
                mode=mode
            )

            # En mode partial : forcer is_active=False pour users excédentaires
            if mode == 'partial' and validation_result['warning']:
                active_count = 0
                max_allowed = validation_result['max_active_allowed']
                
                for user_data in users_data:
                    if user_data.get('is_active', True):  # Default True
                        active_count += 1
                        if active_count > max_allowed:
                            user_data['is_active'] = False
                            user_data['_forced_inactive'] = True  # Flag pour logging
            
            # ===== PREMIER USER ADMIN WARNING =====
            from ..models import ClientAccount
            client = ClientAccount.objects.get(id=client_id)

            if client.users.count() == 0 and users_data:
                # C'est le premier user du tenant
                first_user_data = users_data[0]
                
                is_superuser = first_user_data.get('is_superuser', False)
                role_id = first_user_data.get('role')
                
                # Vérifier si Admin role
                is_admin_role = False
                if role_id:
                    try:
                        from ..models import UserRole
                        role = UserRole.objects.get(id=role_id, client_account_id=client_id)
                        is_admin_role = (role.name == 'Admin')
                    except UserRole.DoesNotExist:
                        pass
                
                if not is_superuser and not is_admin_role:
                    # ⚠️ WARNING : Premier user sans admin
                    logger.warning(
                        f"Creating first user for client '{client.name}' "
                        f"without superuser or Admin role. "
                        # f"Email: {first_user_data.get('email', 'N/A')}. "
                        f"Serializer will auto-promote to Admin in individual mode, "
                        f"but bulk mode may skip this logic.",
                        extra={
                            'event': 'first_user_without_admin',
                            'client_id': str(client_id),
                            'client_name': client.name,
                            # 'user_email': first_user_data.get('email', 'N/A'),
                            **safe_user_data_context(first_user_data),
                            'mode': mode
                        }
                    )
            
            # Preload all FKs in 3 SELECT queries
            fk_preload_result = self._preload_bulk_create_fks(users_data, client_id)
            
            roles_map = fk_preload_result['roles_map']
            teams_map = fk_preload_result['teams_map']
            orgs_map = fk_preload_result['orgs_map']
            
            logger.info(
                "FK preloading stats",
                extra={
                    'client_id': str(client_id),
                    **fk_preload_result['stats']
                }
            )
            
            # Validate FKs in memory (0 SQL queries)
            try:
                valid_users_with_fks, failed_fk_validations = self._validate_bulk_create_fks_in_memory(
                    users_data=users_data,
                    roles_map=roles_map,
                    teams_map=teams_map,
                    orgs_map=orgs_map,
                    mode=mode,
                    client_id=client_id
                )
                
                # Add FK validation failures to results
                results['failed'].extend(failed_fk_validations)
                
                logger.info(
                    "FK validation completed",
                    extra={
                        'client_id': str(client_id),
                        'valid_users': len(valid_users_with_fks),
                        'failed_fk_validations': len(failed_fk_validations)
                    }
                )
                
            except StandardizedValidationError as e:
                # Strict mode failed - FK validation error
                logger.error(
                    "Strict mode FK validation failed",
                    extra={
                        'client_id': str(client_id),
                        'error': str(e)
                    }
                )
                raise
            
            # Override users_data with only valid users for creation loop
            # This ensures we only process users that passed FK validation
            if mode == 'partial':
                # In partial mode: only create valid users, skip failed ones
                users_data_to_create = [user_data for _, user_data in valid_users_with_fks]
                
                logger.info(
                    "Partial mode: proceeding with valid users only",
                    extra={
                        'client_id': str(client_id),
                        'original_count': len(users_data),
                        'valid_count': len(users_data_to_create),
                        'skipped_count': len(failed_fk_validations)
                    }
                )
            else:
                # In strict mode: all users passed validation or exception was raised
                users_data_to_create = [user_data for _, user_data in valid_users_with_fks]
                
                logger.info(
                    "Strict mode: all users passed FK validation",
                    extra={
                        'client_id': str(client_id),
                        'valid_count': len(users_data_to_create)
                    }
                )


            # ===== CREATE USERS =====
            with disable_signals_with_invalidation(client_id, ['users']):
                if mode == 'strict':
                    # Strict mode: All-or-nothing
                    with transaction.atomic():
                        try:
                            for idx, user_data in enumerate(users_data):
                                row_num = idx + 1
                                email = user_data.get('email', '').lower()

                                # Check for existing email
                                if email in existing_emails:
                                    results['skipped'].append({
                                        'row': row_num,
                                        'email': email,
                                        'reason': "A user with this email already exists"
                                    })
                                    continue

                                # Validate superuser modification
                                self._validate_superuser_modification(request.user, user_data)

                                # Create user via serializer
                                serializer = self.get_serializer(
                                    data=user_data,
                                    context=self.get_serializer_context()
                                )
                                serializer.is_valid(raise_exception=True)
                                user = serializer.save()

                                results['success'].append({
                                    'row': row_num,
                                    'email': user.email,
                                    'id': str(user.id),
                                    'name': user.get_full_name()
                                })
                            
                            # Invalidate cache after commit
                            # transaction.on_commit(lambda: invalidate_tag(client_id, 'users'))

                            client = ClientAccount.objects.get(id=client_id)
                            client.ensure_admin_invariants()
                            
                        except Exception as e:
                            error_msg = self._format_bulk_error_message(e)
                            ctx['event'] = 'bulk_create_strict_mode_failed'
                            ctx['error'] = error_msg
                            logger.error("Bulk create strict mode failed", extra=ctx, exc_info=True)
                            
                            return self._build_bulk_error_response(
                                {'success': [], 'failed': [], 'skipped': results['skipped']}, 
                                len(users_data),
                                f"Strict mode failed: {error_msg}"
                            )
                else:
                    # Partial mode: Best-effort creation
                    for idx, user_data in enumerate(users_data_to_create):
                        
                        row_num = idx + 1
                        email_display = user_data.get('email', 'Unknown')

                        # Skip if already in skipped list
                        if any(s['row'] == row_num for s in results['skipped']):
                            continue

                        with transaction.atomic():
                            try:
                                email = user_data.get('email', '').lower()

                                # Check for existing email
                                if email in existing_emails:
                                    results['skipped'].append({
                                        'row': row_num,
                                        'email': email,
                                        'reason': "A user with this email already exists"
                                    })
                                    continue

                                # Validate superuser modification
                                self._validate_superuser_modification(request.user, user_data)

                                # Create user
                                serializer = self.get_serializer(
                                    data=user_data,
                                    context=self.get_serializer_context()
                                )
                                serializer.is_valid(raise_exception=True)
                                user = serializer.save()

                                results['success'].append({
                                    'row': row_num,
                                    'email': user.email,
                                    'id': str(user.id),
                                    'name': user.get_full_name()
                                })

                            except StandardizedValidationError as e:
                                error_msg = self._format_bulk_error_message(e)
                                results['failed'].append({
                                    'row': row_num,
                                    'email': email_display,
                                    'errors': [error_msg]
                                })
                                transaction.set_rollback(True)
                                
                            except Exception as e:
                                ctx['event'] = 'bulk_create_unexpected_error'
                                ctx['row'] = row_num
                                ctx['error'] = str(e)
                                logger.error("Unexpected error in bulk create", extra=ctx, exc_info=True)
                                
                                error_msg = self._format_bulk_error_message(e)
                                results['failed'].append({
                                    'row': row_num,
                                    'email': email_display,
                                    'errors': [error_msg]
                                })
                                transaction.set_rollback(True)

                    try:
                        client = ClientAccount.objects.get(id=client_id)
                        client.ensure_admin_invariants()
                    except Exception as e:
                        logger.warning(
                            f"Failed to ensure admin invariants after bulk create: {e}",
                            extra=ctx
                        )
                    
                    # ✅ SECURITY FIX: Invalidate cache AFTER all transactions are committed
                    # This ensures cache is only invalidated if all individual user creations succeed
                    # Each user has its own transaction.atomic() in the loop above
                    # The on_commit callback will execute after ALL these mini-transactions are done
                    # transaction.on_commit(lambda: invalidate_tag(client_id, 'users'))

            # ===== BUILD RESPONSE =====
            success_count = len(results['success'])
            failed_count = len(results['failed'])
            skipped_count = len(results['skipped'])

            ctx.update({
                'event': 'bulk_create_users_completed',
                'requested': len(users_data),
                'summary_created': success_count,
                'failed': failed_count,
                'skipped': skipped_count
            })

            ctx_safe = {**ctx, 'success_count': len(results['success'])}
            logger.info("Bulk user creation completed", extra=ctx_safe)

            return self._build_bulk_success_response(results, len(users_data), operation='create', detailed=detailed )

        except StandardizedValidationError as e:
            if hasattr(e, 'detail') and isinstance(e.detail, dict):
                error_msg = e.detail.get('error', str(e))
            else:
                error_msg = str(e)
            
            return self._build_bulk_error_response(
                results={'success': [], 'failed': [], 'skipped': []},
                total=0,
                error_message=error_msg
            )
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _format_bulk_error_message(self, error):
        """
        Format exception into user-friendly error message.
        
        Converts technical exceptions into readable messages while preserving
        important details for debugging.
        """
        if isinstance(error, StandardizedValidationError):
            if hasattr(error, 'detail'):
                if isinstance(error.detail, dict):
                    return error.detail.get('error', str(error))
                elif isinstance(error.detail, list):
                    return '; '.join(str(e) for e in error.detail)
            return str(error)
        
        error_type = type(error).__name__
        
        if "IntegrityError" in error_type:
            if "unique constraint" in str(error).lower():
                return "Duplicate entry detected"
            return "Database integrity error"
        elif "ValidationError" in error_type:
            return str(error)
        elif "PermissionDenied" in error_type or "PermissionError" in error_type:
            return "Permission denied"
        elif "DoesNotExist" in error_type:
            return "Referenced resource not found"
        
        return "Processing failed. Please check your data and try again."

    def _build_bulk_error_response(self, results, total, error_message):
        """
        Build standardized error response for bulk operations.
        
        Args:
            results: Dict with 'success', 'failed', 'skipped' arrays
            total: Total number of items requested
            error_message: Main error message
            
        Returns:
            Response object with 400 status
        """
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
            """
            Build standardized success response for bulk operations.
            
            Intelligently determines HTTP status code based on results:
            - 200/201: All succeeded
            - 207: Partial success (some failed)
            - 400: All failed
            
            Args:
                results: Dict with 'success', 'failed', 'skipped' arrays
                total: Total number of items requested
                operation: Operation type ('create', 'update', 'delete', 'archive')
                detailed: If False (default), return IDs only for fast response.
                        If True, return full objects with all fields.
                
            Returns:
                Response object with appropriate status code
            """
            success_count = len(results.get('success', []))
            failed_count = len(results.get('failed', []))
            skipped_count = len(results.get('skipped', []))

            # Determine status
            if success_count == 0 and failed_count > 0:
                status_code = status.HTTP_400_BAD_REQUEST
                success_status = False
                # message = f"Bulk {operation} failed: all {failed_count} item(s) failed"
                failed_items = results.get('failed', [])
                extracted_message = None
                
                if failed_items:
                    first_failed = failed_items[0]
                    if isinstance(first_failed, dict) and 'errors' in first_failed:
                        errors_list = first_failed['errors']
                        if errors_list and len(errors_list) > 0:
                            extracted_message = str(errors_list[0])
                
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

            # ===== FAST vs DETAILED MODE =====
            if not detailed:
                # FAST MODE: IDs only (reduces payload by ~90%)
                # Extract ID from dict or use value directly if already an ID
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
                # DETAILED MODE: Full objects (backward compatibility)
                clean_results = {
                    'success': results.get('success', []),
                    'failed': [],
                    'skipped': []
                }
                
                for failed_item in results.get('failed', []):
                    clean_item = failed_item.copy()
                    if 'errors' in clean_item:
                        clean_item['errors'] = [str(error) for error in clean_item['errors']]
                    clean_results['failed'].append(clean_item)
                
                for skipped_item in results.get('skipped', []):
                    clean_item = skipped_item.copy()
                    if 'reason' in clean_item:
                        clean_item['reason'] = str(clean_item['reason'])
                    clean_results['skipped'].append(clean_item)

            # Map operation to specific summary key
            operation_key_map = {
                'create': 'created',
                'update': 'updated',
                'delete': 'deleted',
                'archive': 'archived',
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
    


    def _prevalidate_fks(self, patch, client_id):
        """
        Pre-validate and fetch all FK instances in bulk (1 query per FK type).
        
        This method eliminates N×3 SELECT queries by validating all FKs upfront.
        Used by bulk_update to optimize FK validation before set-based UPDATE.
        
        Args:
            patch: Dict containing FK fields to update (role, team, organization)
            client_id: Current client ID for validation
            
        Returns:
            Dict with validated instances: {'role': UserRole(...), 'team': Team(...), ...}
            Empty dict if no FK fields in patch
            
        Raises:
            StandardizedValidationError: If any FK validation fails
            
        Example:
            patch = {'role': 'uuid-123', 'team': 'uuid-456'}
            result = self._prevalidate_fks(patch, client_id)
            # result = {'role': <UserRole obj>, 'team': <Team obj>}
        """
        validated_fks = {}
        
        # ===== ROLE VALIDATION =====
        if 'role' in patch:
            role_id = patch['role']
            
            if role_id is None or role_id == '':
                validated_fks['role'] = None
                validated_fks['role_name'] = None
            else:
                # Validate UUID format
                try:
                    import uuid
                    uuid.UUID(str(role_id))
                except ValueError:
                    raise StandardizedValidationError(f"Invalid role ID format: {role_id}")
                
                # Fetch role (1 SELECT for all users)
                try:
                    role = UserRole.objects.get(id=role_id, client_account_id=client_id)
                    validated_fks['role'] = role
                    validated_fks['role_name'] = role.name
                except UserRole.DoesNotExist:
                    raise StandardizedValidationError(
                        CoreErrorMessages.BULK_CREATE_INVALID_ROLE.format(role=role_id)
                    )
        
        # ===== ORGANIZATION VALIDATION =====
        if 'organization' in patch:
            org_id = patch['organization']
            
            if org_id is None or org_id == '':
                validated_fks['organization'] = None
            else:
                # Validate UUID format
                try:
                    import uuid
                    uuid.UUID(str(org_id))
                except ValueError:
                    raise StandardizedValidationError(f"Invalid organization ID format: {org_id}")
                
                # Fetch organization (1 SELECT for all users)
                try:
                    org = Organization.objects.get(id=org_id, client_account_id=client_id)
                    validated_fks['organization'] = org
                except Organization.DoesNotExist:
                    raise StandardizedValidationError(f"Organization with ID '{org_id}' not found")
        
        # ===== TEAM VALIDATION =====
        if 'team' in patch:
            team_id = patch['team']
            
            if team_id is None or team_id == '':
                validated_fks['team'] = None
            else:
                # Validate UUID format
                try:
                    import uuid
                    uuid.UUID(str(team_id))
                except ValueError:
                    raise StandardizedValidationError(f"Invalid team ID format: {team_id}")
                
                # Fetch team (1 SELECT for all users)
                try:
                    team = Team.objects.get(id=team_id)
                    # Validate team belongs to client
                    if str(team.organization.client_account_id) != str(client_id):
                        raise StandardizedValidationError("Team does not belong to your organization")
                    validated_fks['team'] = team
                except Team.DoesNotExist:
                    raise StandardizedValidationError(f"Team with ID '{team_id}' not found")
        
        return validated_fks
    
    def _validate_bulk_creation_seats(self, client_id, users_data, mode):
        """
        Valide si la création masse respecte les sièges disponibles.
        
        Args:
            client_id: ID du client tenant
            users_data: Liste des dicts users à créer
            mode: 'strict' ou 'partial'
        
        Returns:
            dict: {
                'can_proceed': True,
                'max_active_allowed': int (nombre max d'actifs autorisés),
                'active_requested': int,
                'available_seats': int,
                'warning': str ou None
            }
        
        Raises:
            StandardizedValidationError: Si mode strict et dépassement
        """
        from ..models import ClientAccount
        
        # Calculer sièges disponibles
        client = ClientAccount.objects.get(id=client_id)
        available_seats = client.max_users - client.count_active_users()
        
        # Compter users actifs demandés (is_active par défaut = True)
        active_requested = sum(
            1 for user_data in users_data 
            if user_data.get('is_active', True)
        )
        
        # Validation selon le mode
        if active_requested > available_seats:
            if mode == 'strict':
                raise StandardizedValidationError(
                    # f"Cannot create {active_requested} active user(s). "
                    # f"Only {available_seats} seat(s) available. "
                    # f"Set is_active=false for some users or increase max_users limit."
                    CoreErrorMessages.SEAT_LIMIT_REACHED  
                )
            else:  # partial mode
                return {
                    'can_proceed': True,
                    'max_active_allowed': available_seats,
                    'active_requested': active_requested,
                    'available_seats': available_seats,
                    'warning': (str(CoreErrorMessages.SEAT_LIMIT_REACHED))
                }
        
        # Assez de sièges pour tous
        return {
            'can_proceed': True,
            'max_active_allowed': active_requested,
            'active_requested': active_requested,
            'available_seats': available_seats,
            'warning': None
        }
        
    def _apply_fk_updates_setbased(self, valid_user_ids, validated_fks, client_id):
        """
        Apply FK updates using set-based UPDATE queries (1 query per FK field).
        
        This eliminates N UPDATE queries by using WHERE id IN (...) pattern.
        Replaces the loop with individual .save() calls.
        
        Args:
            valid_user_ids: List of user IDs to update
            validated_fks: Dict with pre-validated FK instances from _prevalidate_fks()
            client_id: Current client ID for tenant scoping
            
        Returns:
            int: Total number of users updated
            
        Example:
            validated_fks = {'role': <UserRole obj>, 'team': None}
            count = self._apply_fk_updates_setbased([id1, id2, id3], validated_fks, client_id)
            # Executes: UPDATE users SET role_id='...' WHERE id IN (id1, id2, id3)
            #           UPDATE users SET team_id=NULL WHERE id IN (id1, id2, id3)
        """
        if not valid_user_ids or not validated_fks:
            return 0
        
        updated_count = 0
        base_queryset = User.objects.filter(
            id__in=valid_user_ids,
            client_account_id=client_id
        )
        
        # ===== ROLE UPDATE (SET-BASED) =====
        if 'role' in validated_fks:
            role_value = validated_fks['role']
            
            if role_value is None:
                # Set role to NULL
                count = base_queryset.update(role=None, role_name=None)
            else:
                # Set role to the validated instance
                count = base_queryset.update(
                    role=role_value,
                    role_name=validated_fks.get('role_name')
                )
            
            updated_count = max(updated_count, count)
        
        # ===== ORGANIZATION UPDATE (SET-BASED) =====
        if 'organization' in validated_fks:
            org_value = validated_fks['organization']
            
            if org_value is None:
                count = base_queryset.update(organization=None)
            else:
                count = base_queryset.update(organization=org_value)
            
            updated_count = max(updated_count, count)
        
        # ===== TEAM UPDATE (SET-BASED) =====
        if 'team' in validated_fks:
            team_value = validated_fks['team']
            
            if team_value is None:
                count = base_queryset.update(team=None)
            else:
                count = base_queryset.update(team=team_value)
            
            updated_count = max(updated_count, count)
        
        return updated_count

    def _validate_and_apply_patch(self, user, patch, client_id):
        """
        Validate and apply patch to a user (for complex FK updates).
        
        Used by bulk_update for FK fields (role, team, organization) that
        require individual validation and cannot use set-based UPDATE.
        
        Args:
            user: User instance to update
            patch: Dict of fields to update
            client_id: Current client ID for validation
            
        Raises:
            StandardizedValidationError: If validation fails
        """
        changes = {}
        
        # Validate and prepare role change
        if 'role' in patch:
            role_id = patch['role']
            
            if role_id is None or role_id == '':
                changes['role'] = None
                changes['role_name'] = None
            else:
                try:
                    import uuid
                    uuid.UUID(str(role_id))
                except ValueError:
                    raise StandardizedValidationError(f"Invalid role ID format: {role_id}")
                
                try:
                    role = UserRole.objects.get(id=role_id, client_account_id=client_id)
                    changes['role'] = role
                    changes['role_name'] = role.name
                except UserRole.DoesNotExist:
                    raise StandardizedValidationError(
                        CoreErrorMessages.BULK_CREATE_INVALID_ROLE.format(role=role_id)
                    )
        
        # Validate and prepare organization change
        if 'organization' in patch:
            org_id = patch['organization']
            
            if org_id is None or org_id == '':
                changes['organization'] = None
            else:
                try:
                    import uuid
                    uuid.UUID(str(org_id))
                except ValueError:
                    raise StandardizedValidationError(f"Invalid organization ID format: {org_id}")
                
                try:
                    org = Organization.objects.get(id=org_id, client_account_id=client_id)
                    changes['organization'] = org
                except Organization.DoesNotExist:
                    raise StandardizedValidationError(f"Organization with ID '{org_id}' not found")
        
        # Validate and prepare team change
        if 'team' in patch:
            team_id = patch['team']
            
            if team_id is None or team_id == '':
                changes['team'] = None
            else:
                try:
                    import uuid
                    uuid.UUID(str(team_id))
                except ValueError:
                    raise StandardizedValidationError(f"Invalid team ID format: {team_id}")
                
                try:
                    team = Team.objects.get(id=team_id)
                    if str(team.organization.client_account_id) != str(client_id):
                        raise StandardizedValidationError("Team does not belong to your organization")
                    changes['team'] = team
                except Team.DoesNotExist:
                    raise StandardizedValidationError(f"Team with ID '{team_id}' not found")
        
        # Apply changes
        if changes:
            for field, value in changes.items():
                setattr(user, field, value)
            
            # Determine which fields to update
            update_fields = list(changes.keys())
            update_fields.append('updated_at')
            
            user.save(update_fields=update_fields)
    
    def _validate_bulk_activation_seats(self, client_id, user_ids_to_activate, mode):
        """
        Valide si l'activation masse respecte les sièges disponibles.
        
        Args:
            client_id: ID du client tenant
            user_ids_to_activate: Liste des IDs users à activer
            mode: 'strict' ou 'partial'
        
        Returns:
            dict: {
                'allowed_ids': [ids pouvant être activés],
                'denied_ids': [ids ne pouvant pas être activés],
                'available_seats': int,
                'requested': int,
                'warning': str ou None
            }
        
        Raises:
            StandardizedValidationError: Si mode strict et dépassement
        """
        from ..models import ClientAccount
        
        # Récupérer client et calculer sièges disponibles
        client = ClientAccount.objects.get(id=client_id)
        available_seats = client.max_users - client.count_active_users()
        
        # Identifier users actuellement INACTIFS qui vont devenir actifs
        users_to_activate_qs = User.objects.filter(
            id__in=user_ids_to_activate,
            client_account_id=client_id,
            is_active=False  # Seulement ceux qui changent d'état
        ).order_by('created_at')  # FIFO : premiers créés = premiers activés
        
        count_to_activate = users_to_activate_qs.count()
        
        # Validation selon le mode
        if count_to_activate > available_seats:
            if mode == 'strict':
                raise StandardizedValidationError(
                    f"Cannot activate {count_to_activate} user(s). "
                    f"Only {available_seats} seat(s) available. "
                    f"Deactivate other users or increase max_users limit."
                )
            else:  # partial mode
                # Activer seulement les X premiers (FIFO)
                allowed_ids = list(
                    users_to_activate_qs[:available_seats].values_list('id', flat=True)
                )
                denied_ids = list(
                    users_to_activate_qs[available_seats:].values_list('id', flat=True)
                )
                
                return {
                    'allowed_ids': [str(uid) for uid in allowed_ids],
                    'denied_ids': [str(uid) for uid in denied_ids],
                    'available_seats': available_seats,
                    'requested': count_to_activate,
                    'warning': str(CoreErrorMessages.SEAT_LIMIT_REACHED)
                }
        
        # Tous les users peuvent être activés
        all_ids = [str(uid) for uid in users_to_activate_qs.values_list('id', flat=True)]
        return {
            'allowed_ids': all_ids,
            'denied_ids': [],
            'available_seats': available_seats,
            'requested': count_to_activate,
            'warning': None
        }
    
    def _validate_superuser_modification(self, current_user, request_data, target_user=None, target_user_ids=None):
        """
        Validate if the current user can modify superuser status.
        
        Called before create or update operations that involve is_superuser field.
        Only superusers or Admin role users can grant/revoke superuser status.
        
        Args:
            current_user: User making the request
            request_data: Data being submitted (may contain is_superuser)
            target_user: User being modified (None for create operations)
            
        Raises:
            StandardizedValidationError: If validation fails
        """
        if 'is_superuser' not in request_data:
            return
        
        # Check if current user can grant superuser
        if not current_user.is_superuser:
            # Check if user has Admin role
            if not (current_user.role and current_user.role.name == 'Admin'):
                raise StandardizedValidationError(
                    "Only superusers and admins can grant/revoke superuser status"
                )
        
        # If removing superuser status, check it's not the last one
        elif target_user_ids and request_data.get('is_superuser') is False:
            # Identifier superusers actuels dans le batch
            current_superusers_in_batch = list(
            User.objects.filter(
                id__in=target_user_ids,
                client_account_id=current_user.client_account_id,
                is_superuser=True
            ).values_list('id', flat=True)
        )
        
        # ✅ VERROU: Compter autres superusers HORS du batch avec lock pessimiste
        # Convert to list() because select_for_update() doesn't work with count()
        # Performance impact is minimal (typically < 10 superusers per tenant)
        other_superusers = list(
            User.objects.select_for_update().filter(
                client_account_id=current_user.client_account_id,
                is_superuser=True
            ).exclude(id__in=current_superusers_in_batch).values_list('id', flat=True)
        )
        
        if len(other_superusers) == 0:
            raise StandardizedValidationError(
                "Cannot remove superuser status from the last superuser(s). "
                "Promote another user to superuser first."
            )
            
    def _validate_bulk_deactivation_last_admin(
        self, 
        client_id, 
        user_ids_to_deactivate, 
        users_dict,
        mode
    ):
        """
        Validate that we don't deactivate the last active admin of the tenant.
        
        SECURITY: This function uses select_for_update() to prevent TOCTOU race condition.
        The admin count query locks the rows to ensure no concurrent transaction can
        deactivate admins between the COUNT check and the UPDATE operation.
        
        An admin = is_superuser=True OR role.name='Admin'
        
        Args:
            client_id: ID du client tenant
            user_ids_to_deactivate: Liste des IDs users à désactiver
            users_dict: Dict {user_id: User obj} pour éviter requêtes supplémentaires
            mode: 'strict' ou 'partial'
        
        Returns (mode partial):
            dict: {
                'allowed_ids': [ids pouvant être désactivés],
                'denied_ids': [ids protégés - derniers admins],
                'warning': str ou None
            }
        
        Raises (mode strict):
            StandardizedValidationError: Si désactivation affecte dernier admin actif
        
        SQL Impact: +1 SELECT FOR UPDATE query (admins actifs hors du batch)
        
        IMPORTANT: This function MUST be called within a transaction.atomic() block
        for the select_for_update() lock to be effective.
        
        Examples:
            # Mode strict - 1 seul admin actif dans tenant
            >>> self._validate_bulk_deactivation_last_admin(
            ...     client_id='abc123',
            ...     user_ids_to_deactivate=['admin-id', 'user2'],
            ...     users_dict={...},
            ...     mode='strict'
            ... )
            StandardizedValidationError: "Cannot deactivate 1 admin(s)..."
            
            # Mode partial - exclure dernier admin
            >>> result = self._validate_bulk_deactivation_last_admin(
            ...     client_id='abc123',
            ...     user_ids_to_deactivate=['admin-id', 'user2'],
            ...     users_dict={...},
            ...     mode='partial'
            ... )
            >>> result
            {
                'allowed_ids': ['user2'],
                'denied_ids': ['admin-id'],
                'warning': "1 admin(s) cannot be deactivated (last active admin)"
            }
        """
        from django.db.models import Q
        
        # ===== ÉTAPE 1 : Identifier admins actifs DANS le batch =====
        admins_in_batch = []
        for user_id in user_ids_to_deactivate:
            user = users_dict.get(user_id)
            if not user:
                continue
            
            # Vérifier si user est actif ET admin
            if user.is_active:
                # Admin = superuser OU rôle Admin
                is_admin = user.is_superuser or (user.role and user.role.name == 'Admin')
                if is_admin:
                    admins_in_batch.append(user_id)
        
        # Si aucun admin dans le batch, pas de risque
        if not admins_in_batch:
            return {
                'allowed_ids': list(user_ids_to_deactivate),
                'denied_ids': [],
                'warning': None
            }
        
        # ===== ÉTAPE 2 : Compter admins actifs HORS du batch avec lock =====
        # SECURITY FIX: Use select_for_update() to prevent TOCTOU race condition
        # This locks the admin rows until the end of the transaction, preventing
        # concurrent transactions from deactivating admins between CHECK and UPDATE
        #
        # Note: We convert to list() instead of .count() because select_for_update()
        # doesn't work with .count(). The performance impact is minimal since we're
        # typically dealing with a small number of admins (< 100 per tenant).
        other_active_admins = list(
            User.objects.filter(
                client_account_id=client_id,
                is_active=True
            ).filter(
                Q(is_superuser=True) | Q(role__name='Admin')
            ).exclude(
                id__in=admins_in_batch
            ).select_for_update()  # ✅ LOCK to prevent race condition
            .only('id')  # Performance: only fetch IDs, not full objects
        )
        
        other_active_admins_count = len(other_active_admins)
        
        # ===== ÉTAPE 3 : Décision selon mode =====
        if other_active_admins_count == 0:
            # Problème : on va désactiver le(s) dernier(s) admin(s)
            
            if mode == 'strict':
                # Mode strict : erreur immédiate, transaction annulée
                raise StandardizedValidationError(
                    f"Cannot deactivate {len(admins_in_batch)} admin(s). "
                    f"At least one active admin must remain in the organization. "
                    f"Promote another user to admin or activate an inactive admin before proceeding."
                )
            else:
                # Mode partial : exclure les admins du batch, désactiver les autres
                allowed_ids = [
                    uid for uid in user_ids_to_deactivate 
                    if uid not in admins_in_batch
                ]
                
                return {
                    'allowed_ids': allowed_ids,
                    'denied_ids': admins_in_batch,
                    'warning': (
                        f"{len(admins_in_batch)} admin(s) cannot be deactivated "
                        f"(last active admin). Promote another user to admin first."
                    )
                }
        
        # Pas de problème : il reste d'autres admins actifs
        return {
            'allowed_ids': list(user_ids_to_deactivate),
            'denied_ids': [],
            'warning': None
        }
    
    def _validate_bulk_role_change_last_admin(
        self, 
        client_id, 
        user_ids_changing_role,
        users_dict,
        new_role_name,
        mode
    ):
        """
        Valide qu'on ne retire pas le rôle Admin au dernier Admin du tenant.
        
        Un tenant doit toujours avoir au moins un admin (role='Admin' OU is_superuser=True).
        Cette validation empêche le changement de rôle si cela retire le dernier Admin.
        
        Args:
            client_id: ID du client tenant
            user_ids_changing_role: Liste des IDs users changeant de rôle
            users_dict: Dict {user_id: User obj} pour éviter requêtes supplémentaires
            new_role_name: Nom du nouveau rôle (None si suppression, 'Admin' si reste admin)
            mode: 'strict' ou 'partial'
        
        Returns (mode partial):
            dict: {
                'allowed_ids': [ids pouvant changer de rôle],
                'denied_ids': [ids protégés - derniers Admins],
                'warning': str ou None
            }
        
        Raises (mode strict):
            StandardizedValidationError: Si changement affecte dernier Admin
        
        SQL Impact: +1 COUNT query (conditionnel, seulement si role change)
        
        Exemples:
            # Mode strict - Changement rôle Admin → Sales Rep (dernier Admin)
            >>> self._validate_bulk_role_change_last_admin(
            ...     client_id='abc123',
            ...     user_ids_changing_role=['admin-id'],
            ...     users_dict={...},
            ...     new_role_name='Sales Rep',
            ...     mode='strict'
            ... )
            StandardizedValidationError: "Cannot change role for 1 admin(s)..."
            
            # Mode partial - Exclure dernier Admin du changement
            >>> result = self._validate_bulk_role_change_last_admin(
            ...     client_id='abc123',
            ...     user_ids_changing_role=['admin-id', 'user2'],
            ...     users_dict={...},
            ...     new_role_name='Manager',
            ...     mode='partial'
            ... )
            >>> result
            {
                'allowed_ids': ['user2'],
                'denied_ids': ['admin-id'],
                'warning': "1 admin(s) role cannot be changed (last Admin role)"
            }
            
            # Pas de problème - Changement vers Admin
            >>> result = self._validate_bulk_role_change_last_admin(
            ...     new_role_name='Admin',  # On reste/devient Admin
            ...     ...
            ... )
            >>> result
            {'allowed_ids': [...], 'denied_ids': [], 'warning': None}
        """
        from django.db.models import Q
        
        # ===== ÉTAPE 1 : Si nouveau rôle = Admin, pas de problème =====
        if new_role_name == 'Admin':
            # On reste Admin ou on devient Admin → OK
            return {
                'allowed_ids': list(user_ids_changing_role),
                'denied_ids': [],
                'warning': None
            }
        
        # ===== ÉTAPE 2 : Identifier users avec rôle Admin actuellement DANS le batch =====
        admins_in_batch = []
        for user_id in user_ids_changing_role:
            user = users_dict.get(user_id)
            if not user:
                continue
            
            # Vérifier si user a actuellement le rôle Admin
            # (is_superuser n'est pas affecté par le changement de rôle, donc on ne le compte pas ici)
            if user.role and user.role.name == 'Admin':
                admins_in_batch.append(user_id)
        
        # Si aucun Admin dans le batch, pas de risque
        if not admins_in_batch:
            return {
                'allowed_ids': list(user_ids_changing_role),
                'denied_ids': [],
                'warning': None
            }
        
        # ===== ÉTAPE 3 : Compter autres admins (rôle Admin OU superuser) HORS du batch =====
        # Un tenant est sécurisé s'il a au moins un user actif avec :
        # - role.name == 'Admin' OU
        # - is_superuser == True
        # qui n'est PAS dans le batch de changement de rôle
        
        other_admins = list(
            User.objects.select_for_update().filter(
                client_account_id=client_id,
                is_active=True  # On ne compte que les actifs
            ).filter(
                Q(role__name='Admin') | Q(is_superuser=True)
            ).exclude(id__in=admins_in_batch).values_list('id', flat=True)
        )

        other_admins_count = len(other_admins)
        
        # ===== ÉTAPE 4 : Décision selon mode =====
        if other_admins_count == 0:
            # Problème : on va retirer le rôle Admin au(x) dernier(s) Admin(s)
            
            if mode == 'strict':
                # Mode strict : erreur immédiate, transaction annulée
                raise StandardizedValidationError(
                    f"Cannot change role for {len(admins_in_batch)} admin(s). "
                    f"At least one Admin role must remain in the organization. "
                    f"Promote another user to Admin or create a new admin before changing these roles."
                )
            else:
                # Mode partial : exclure les derniers admins du changement de rôle
                allowed_ids = [
                    uid for uid in user_ids_changing_role 
                    if uid not in admins_in_batch
                ]
                
                return {
                    'allowed_ids': allowed_ids,
                    'denied_ids': admins_in_batch,
                    'warning': (
                        f"{len(admins_in_batch)} admin(s) role cannot be changed "
                        f"(last Admin role in organization). Promote another user to Admin first."
                    )
                }
        
        # Pas de problème : il reste d'autres admins actifs (role ou superuser)
        return {
            'allowed_ids': list(user_ids_changing_role),
            'denied_ids': [],
            'warning': None
        }