# app_modules/territories/views/views_bulk.py
"""
Territory Bulk Operations ViewSet

SIMPLIFIED VERSION (no idempotency wrapper)
==========================================

Why simplified vs Users/Accounts:
- Territories have minimal cascade (no heavy relations like Contacts, Activities, etc.)
- Typical volume is low (< 50 territories per client)
- Execution time is always < 1 second, so no timeout risk
- No need for 202 Accepted + polling mechanism

This keeps the code simple and the frontend doesn't need to handle async polling.
Idempotency can be added later if territories get heavy relations.

Response format is fully compatible with:
- handleBulkError() frontend utility
- Standard snackbar notifications
- AlertTerritoryBulkDelete component
"""

from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction

from core.throttling import BulkOperationThrottle
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from core.cache_utils import disable_signals_with_invalidation
from core.logging import get_logger, ctx_from_request
from core.logging.audit import audit_log

from ..models import Territory
from .views import TerritoryViewSet

logger = get_logger(__name__)


class TerritoryBulkViewSet(TerritoryViewSet):
    """
    ViewSet for bulk territory operations.
    
    Inherits authentication, permissions, and client scoping from TerritoryViewSet.
    
    Simplified synchronous implementation - no idempotency wrapper needed because:
    - Territory deletion is fast (no heavy cascade)
    - Low volume operations (typically < 50 items)
    - No timeout risk
    """
    
    throttle_classes = [BulkOperationThrottle]
    
    # =========================================================================
    # RESPONSE BUILDERS - Standard format compatible with handleBulkError()
    # =========================================================================
    
    def _build_bulk_success_response(self, results, total, operation='delete', detailed=False):
        """
        Build standardized success response for bulk operations.
        
        Response format compatible with frontend handleBulkError():
        {
            "success": true,
            "summary": {
                "total_requested": 5,
                "successful": 4,
                "failed": 1
            },
            "results": {
                "success": [{"id": "...", "name": "..."}],
                "failed": [{"id": "...", "name": "...", "errors": ["..."]}]
            }
        }
        """
        success_count = len(results.get('success', []))
        failed_count = len(results.get('failed', []))
        
        # Determine HTTP status code
        if success_count == 0 and failed_count > 0:
            # Total failure
            http_status = status.HTTP_400_BAD_REQUEST
            success_flag = False
        elif failed_count > 0:
            # Partial success
            http_status = status.HTTP_207_MULTI_STATUS
            success_flag = 'partial'
        else:
            # Full success
            http_status = status.HTTP_200_OK
            success_flag = True
        
        response_data = {
            'success': success_flag,
            'summary': {
                'total_requested': total,
                'successful': success_count,
                'failed': failed_count
            }
        }
        
        # Include results if detailed mode or if there are failures
        if detailed or failed_count > 0:
            response_data['results'] = results
        
        return Response(response_data, status=http_status)
    
    def _build_bulk_error_response(self, results, total, error_message):
        """
        Build standardized error response for bulk operations.
        
        Response format compatible with frontend handleBulkError():
        {
            "success": false,
            "error": "Error message",
            "summary": {...},
            "results": {...}
        }
        """
        return Response({
            'success': False,
            'error': error_message,
            'summary': {
                'total_requested': total,
                'successful': len(results.get('success', [])),
                'failed': len(results.get('failed', []))
            },
            'results': results
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def _format_bulk_error_message(self, exception):
        """Extract error message from exception."""
        if hasattr(exception, 'detail'):
            if isinstance(exception.detail, dict):
                return str(exception.detail.get('error', str(exception)))
            return str(exception.detail)
        return str(exception)
    
    # =========================================================================
    # BULK DELETE - Synchronous implementation
    # =========================================================================
    
    @action(detail=False, methods=['delete'], url_path='bulk-delete')
    def bulk_delete(self, request):
        """
        Bulk delete territories.
        
        Synchronous implementation (no 202/polling) because:
        - Territory deletion is fast (minimal cascade)
        - Typical volume < 50 items
        - No timeout risk
        
        Request Body:
            ids: List[UUID] - Territory IDs to delete
            mode: str - 'partial' (default, best-effort) or 'strict' (all-or-nothing)
            
        Query Params:
            detailed: bool - Include full results in response (default: false)
            
        Business Rules:
            - Cannot delete system territories (is_system=True)
            - Strict mode: Fails entirely if any territory can't be deleted
            - Partial mode: Deletes what it can, reports failures
            
        Returns:
            200 OK - All succeeded
            207 Multi-Status - Partial success
            400 Bad Request - All failed or validation error
        """
        ctx = ctx_from_request(request)
        client_id = self.get_client_id()
        
        ctx.update({
            'event': 'bulk_delete_territories',
            'client_id': str(client_id)
        })
        
        detailed = request.query_params.get('detailed', 'false').lower() == 'true'
        results = {'success': [], 'failed': []}
        
        try:
            # =================================================================
            # INPUT VALIDATION
            # =================================================================
            
            if not isinstance(request.data, dict):
                raise StandardizedValidationError("Request body must be a JSON object")
            
            ids = request.data.get('ids', [])
            mode = request.data.get('mode', 'partial')
            
            # Validate ids format
            if not isinstance(ids, list):
                raise StandardizedValidationError(
                    CoreErrorMessages.BULK_INVALID_FORMAT.format(entity="territory IDs")
                )
            
            if not ids:
                raise StandardizedValidationError(CoreErrorMessages.BULK_DELETE_NO_IDS)
            
            if len(ids) > 500:
                raise StandardizedValidationError(
                    CoreErrorMessages.BULK_SIZE_EXCEEDED.format(max_size=500, entity="territories")
                )
            
            if mode not in ['partial', 'strict']:
                raise StandardizedValidationError(CoreErrorMessages.BULK_MODE_INVALID)
            
            # Audit: operation started
            audit_log(
                event='bulk_delete_territories_started',
                action='bulk_delete',
                actor_id=str(request.user.id),
                client_id=str(client_id),
                target_type='territory',
                target_count=len(ids),
                outcome='started',
                extra={'mode': mode}
            )
            
            logger.info("bulk_delete_territories_started", extra={
                **ctx,
                'ids_count': len(ids),
                'mode': mode
            })
            
            # =================================================================
            # FETCH TERRITORIES (with tenant scoping)
            # =================================================================
            
            territories_qs = Territory.objects.filter(
                id__in=ids,
                client_id=client_id
            )
            territories_dict = {str(t.id): t for t in territories_qs}
            
            # =================================================================
            # CHECK FOR NOT FOUND IDs
            # =================================================================
            
            requested_ids = set(str(id) for id in ids)
            found_ids = set(territories_dict.keys())
            not_found_ids = requested_ids - found_ids
            
            if not_found_ids:
                for nf_id in not_found_ids:
                    results['failed'].append({
                        'id': nf_id,
                        'name': None,
                        'errors': ['Territory not found or access denied']
                    })
                
                # Strict mode: fail immediately if any ID not found
                if mode == 'strict':
                    logger.warning("bulk_delete_territories_strict_not_found", extra={
                        **ctx,
                        'not_found_count': len(not_found_ids)
                    })
                    return self._build_bulk_error_response(
                        results,
                        len(ids),
                        f"Strict mode: {len(not_found_ids)} territory(ies) not found"
                    )
            
            # =================================================================
            # CHECK FOR PROTECTED (is_system=True) TERRITORIES
            # =================================================================
            
            protected = []
            deletable_ids = []
            
            for territory_id, territory in territories_dict.items():
                if territory.is_system:
                    protected.append({
                        'id': territory_id,
                        'name': territory.name,
                        'errors': ['Cannot delete system territory']
                    })
                else:
                    deletable_ids.append(territory_id)
            
            # Strict mode: fail if any protected
            if mode == 'strict' and protected:
                for p in protected:
                    results['failed'].append(p)
                
                logger.warning("bulk_delete_territories_strict_protected", extra={
                    **ctx,
                    'protected_count': len(protected)
                })
                return self._build_bulk_error_response(
                    results,
                    len(ids),
                    f"Strict mode: {len(protected)} system territory(ies) cannot be deleted"
                )
            
            # Partial mode: add protected to failed
            if protected:
                results['failed'].extend(protected)
            
            # =================================================================
            # PERFORM DELETION
            # =================================================================
            
            if deletable_ids:
                # Store info before deletion
                territories_info = {
                    tid: {'name': territories_dict[tid].name}
                    for tid in deletable_ids
                }
                
                with transaction.atomic():
                    try:
                        # Disable signals and invalidate cache after deletion
                        with disable_signals_with_invalidation(client_id, ['territories']):
                            deleted_count, deleted_by_model = Territory.objects.filter(
                                id__in=deletable_ids,
                                client_id=client_id
                            ).delete()
                        
                        # Build success results
                        for tid in deletable_ids:
                            results['success'].append({
                                'id': tid,
                                'name': territories_info[tid]['name']
                            })
                        
                        # Log cascade info
                        cascade_summary = ', '.join([
                            f"{model.split('.')[-1]}={count}"
                            for model, count in deleted_by_model.items()
                            if 'Territory' not in model
                        ]) or 'none'
                        
                        logger.info("bulk_delete_territories_executed", extra={
                            **ctx,
                            'deleted_count': deleted_count,
                            'cascade': cascade_summary
                        })
                    
                    except Exception as e:
                        error_msg = self._format_bulk_error_message(e)
                        logger.error("bulk_delete_territories_db_error", extra={
                            **ctx,
                            'error': error_msg
                        })
                        
                        if mode == 'strict':
                            # Strict: rollback everything
                            return self._build_bulk_error_response(
                                {'success': [], 'failed': results['failed']},
                                len(ids),
                                f"Strict mode failed: {error_msg}"
                            )
                        else:
                            # Partial: report all as failed
                            for tid in deletable_ids:
                                results['failed'].append({
                                    'id': tid,
                                    'name': territories_info.get(tid, {}).get('name'),
                                    'errors': [error_msg]
                                })
            
            # =================================================================
            # BUILD RESPONSE
            # =================================================================
            
            success_count = len(results['success'])
            failed_count = len(results['failed'])
            
            # Audit: operation completed
            audit_log(
                event='bulk_delete_territories_completed',
                action='bulk_delete',
                actor_id=str(request.user.id),
                client_id=str(client_id),
                target_type='territory',
                target_count=len(ids),
                outcome='success' if failed_count == 0 else 'partial',
                extra={
                    'deleted': success_count,
                    'failed': failed_count
                }
            )
            
            logger.info("bulk_delete_territories_completed", extra={
                **ctx,
                'success_count': success_count,
                'failed_count': failed_count
            })
            
            return self._build_bulk_success_response(
                results, 
                len(ids), 
                operation='delete', 
                detailed=detailed
            )
        
        except StandardizedValidationError as e:
            error_msg = str(e)
            if hasattr(e, 'detail') and isinstance(e.detail, dict):
                error_msg = str(e.detail.get('error', str(e)))
            
            logger.warning("bulk_delete_territories_validation_error", extra={
                **ctx,
                'error': error_msg
            })
            
            return self._build_bulk_error_response(
                results={'success': [], 'failed': []},
                total=len(request.data.get('ids', [])) if isinstance(request.data, dict) else 0,
                error_message=error_msg
            )
        
        except Exception as e:
            error_msg = self._format_bulk_error_message(e)
            logger.error("bulk_delete_territories_unexpected_error", extra={
                **ctx,
                'error': error_msg
            }, exc_info=True)
            
            return self._build_bulk_error_response(
                results={'success': [], 'failed': []},
                total=len(request.data.get('ids', [])) if isinstance(request.data, dict) else 0,
                error_message=f"Unexpected error: {error_msg}"
            )