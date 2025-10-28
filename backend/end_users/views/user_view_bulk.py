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

import time
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.urls import reverse
from django.core.exceptions import ValidationError

from core.idempotency import (
    start_op,
    complete_op, 
    fail_op,
    get_owner_from_request,
    compute_payload_hash
)
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from core.cache_utils import invalidate_tag
from core.logging import get_logger, ctx_from_request

from ..models import User, UserRole, Team, Organization
from .user_view import UserViewSet

logger = get_logger(__name__)

import os
import os
import threading
from django.http import HttpRequest
from rest_framework.request import Request as DRFRequest
from django.contrib.auth import get_user_model

from decouple import config

# LOG AU CHARGEMENT DU MODULE
if config('SIMULATE_SLOW_DELETE', default='false') == 'true':
    duration = config('SLOW_DELETE_DURATION', default='25')
    logger.warning(f"⚠️ TEST MODE ACTIVATED: SIMULATE_SLOW_DELETE=true, duration={duration}s")
else:
    logger.info("Normal mode: SIMULATE_SLOW_DELETE not set")


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
        """
        Internal implementation of bulk update with SQL SET-BASED optimization.
        
        OPTIMIZATION APPLIED:
        - Simple fields (is_active, is_superuser): UPDATE WHERE id IN (...)
        - FK fields (role, team, organization): Individual updates with validation
        
        This reduces N queries to 1 query for simple field updates.
        """
        ctx = ctx_from_request(request) 
        ctx.update({
            'event': 'bulk_update_users',
            'client_id': self.get_client_id()
        })
        
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
            # Separate simple fields (can use set-based UPDATE) from complex fields
            simple_fields = {'is_active', 'is_superuser'}
            complex_fields = {'role', 'team', 'organization'}
            
            simple_updates = {k: v for k, v in patch.items() if k in simple_fields}
            complex_updates = {k: v for k, v in patch.items() if k in complex_fields}
            
            # For set-based updates, we need to validate all users first
            valid_user_ids = []
            for user_id in ids:
                if user_id in invalid_ids:
                    continue

                user = users_dict[user_id]
                
                # Pre-validate this user for the updates
                try:
                    # Validate simple field updates
                    if 'is_active' in simple_updates:
                        new_active = simple_updates['is_active']
                        if new_active is False and user.is_active and user.is_last_active_admin():
                            raise StandardizedValidationError(
                                f"Cannot deactivate user '{user.email}': last active administrator"
                            )
                    
                    if 'is_superuser' in simple_updates:
                        new_superuser = simple_updates['is_superuser']
                        if new_superuser is False and user.is_superuser and user.is_last_superuser():
                            raise StandardizedValidationError(
                                f"Cannot remove superuser status from '{user.email}': last superuser"
                            )
                    
                    # If validation passes, add to valid list
                    valid_user_ids.append(user_id)
                    
                except StandardizedValidationError as e:
                    results['failed'].append({
                        'id': user_id,
                        'email': user.email,
                        'errors': [str(e)]
                    })
                    
                    if mode == 'strict':
                        return self._build_bulk_error_response(
                            results,
                            len(ids),
                            f"Strict mode validation failed: {str(e)}"
                        )

            # ===== APPLY UPDATES =====
            if mode == 'strict':
                with transaction.atomic():
                    try:
                        # ⭐ SET-BASED UPDATE for simple fields (1 query instead of N)
                        if simple_updates and valid_user_ids:
                            update_fields = {}
                            if 'is_active' in simple_updates:
                                update_fields['is_active'] = simple_updates['is_active']
                            if 'is_superuser' in simple_updates:
                                update_fields['is_superuser'] = simple_updates['is_superuser']
                                # If promoting to superuser, also set is_staff
                                if simple_updates['is_superuser'] is True:
                                    update_fields['is_staff'] = True
                            
                            if update_fields:
                                User.objects.filter(
                                    id__in=valid_user_ids,
                                    client_account_id=client_id
                                ).update(**update_fields)
                        
                        # Complex fields (FK) need individual updates for validation
                        if complex_updates and valid_user_ids:
                            for user_id in valid_user_ids:
                                user = users_dict[user_id]
                                self._validate_and_apply_patch(user, complex_updates, client_id)
                        
                        # Build success results
                        for user_id in valid_user_ids:
                            user = users_dict[user_id]
                            # Refresh from DB to get updated values
                            user.refresh_from_db()
                            results['success'].append({
                                'id': str(user.id),
                                'email': user.email,
                                'name': user.get_full_name()
                            })
                        
                        # Invalidate cache after commit
                        transaction.on_commit(lambda: invalidate_tag(client_id, 'users'))

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
                # ⭐ SET-BASED UPDATE for simple fields
                if simple_updates and valid_user_ids:
                    update_fields = {}
                    if 'is_active' in simple_updates:
                        update_fields['is_active'] = simple_updates['is_active']
                    if 'is_superuser' in simple_updates:
                        update_fields['is_superuser'] = simple_updates['is_superuser']
                        if simple_updates['is_superuser'] is True:
                            update_fields['is_staff'] = True
                    
                    if update_fields:
                        User.objects.filter(
                            id__in=valid_user_ids,
                            client_account_id=client_id
                        ).update(**update_fields)
                
                # Complex fields need individual handling
                if complex_updates:
                    for user_id in valid_user_ids:
                        user = users_dict[user_id]
                        with transaction.atomic():
                            try:
                                self._validate_and_apply_patch(user, complex_updates, client_id)
                            except StandardizedValidationError as e:
                                error_msg = self._format_bulk_error_message(e)
                                results['failed'].append({
                                    'id': user_id,
                                    'email': user.email,
                                    'errors': [error_msg]
                                })
                                transaction.set_rollback(True)
                                
                                # Remove from valid_user_ids if failed
                                if user_id in valid_user_ids:
                                    valid_user_ids.remove(user_id)
                
                # Build success results
                for user_id in valid_user_ids:
                    user = users_dict[user_id]
                    user.refresh_from_db()
                    results['success'].append({
                        'id': str(user.id),
                        'email': user.email,
                        'name': user.get_full_name()
                    })
                
                invalidate_tag(client_id, 'users')

            success_count = len(results['success'])
            failed_count = len(results['failed'])

            ctx.update({
                'event': 'bulk_update_users_completed',
                'requested': len(ids),
                'updated': success_count,
                'failed': failed_count
            })
            logger.info("Bulk user update completed", extra=ctx)

            return self._build_bulk_success_response(results, len(ids), operation='update')

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
            
            for user_id in ids:
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

                            deleted_count = User.objects.filter(
                                id__in=valid_ids,
                                client_account_id=client_id
                            ).delete()[0]
                            
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
                        transaction.on_commit(lambda: invalidate_tag(client_id, 'users'))
                        
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
                        deleted_count = User.objects.filter(
                            id__in=valid_ids,
                            client_account_id=client_id
                        ).delete()[0]
                        
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
                    
                    # Invalidation cache en mode partial
                    invalidate_tag(client_id, 'users')
                    
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

            return self._build_bulk_success_response(results, len(ids), operation='delete')

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

            # ===== CREATE USERS =====
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
                                    'reason': f"Email '{email}' already exists"
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
                        transaction.on_commit(lambda: invalidate_tag(client_id, 'users'))
                        
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
                for idx, user_data in enumerate(users_data):
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
                                    'reason': f"Email '{email}' already exists"
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
                
                # Invalidate cache in partial mode
                invalidate_tag(client_id, 'users')

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
            logger.info("Bulk user creation completed", extra=ctx)

            return self._build_bulk_success_response(results, len(users_data), operation='create')

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

    def _build_bulk_success_response(self, results, total, operation='create'):
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
            message = f"Bulk {operation} failed: all {failed_count} item(s) failed"
        elif failed_count > 0 or skipped_count > 0:
            status_code = status.HTTP_207_MULTI_STATUS
            success_status = 'partial'
            message = f"Bulk {operation}: {success_count} succeeded, {failed_count} failed, {skipped_count} skipped"
        else:
            status_code = status.HTTP_201_CREATED if operation == 'create' else status.HTTP_200_OK
            success_status = True
            message = f"Bulk {operation}: {success_count} item(s) processed successfully"

        # Clean results
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

        # ✅ CORRECTIF A: Map operation to specific summary key
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
    
    def _validate_superuser_modification(self, current_user, request_data, target_user=None):
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
        if target_user and target_user.is_superuser:
            if request_data.get('is_superuser') is False:
                client = target_user.client_account
                other_superusers = User.objects.filter(
                    client_account_id=client.id,
                    is_superuser=True
                ).exclude(id=target_user.id).count()
                
                if other_superusers == 0:
                    raise StandardizedValidationError(
                        "Cannot remove superuser status from the last superuser. "
                        "Promote another user to superuser first."
                    )