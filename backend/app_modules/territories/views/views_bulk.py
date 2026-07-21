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

Key differences from Accounts:
- No idempotency wrapper (synchronous only)
- No admin-only restriction (individuals can delete their own territories)
- System territory protection (is_system=True cannot be deleted)

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
    # BULK DELETE
    # =========================================================================
    
    @action(detail=False, methods=['delete'], url_path='bulk-delete')
    def bulk_delete(self, request):
        """
        Bulk delete territories.
        
        Request Body:
            ids: List[UUID] - Territory IDs to delete
            mode: str - 'partial' (default, best-effort) or 'strict' (all-or-nothing)
            
        Query Params:
            detailed: bool - Include full results in response (default: false)
            
        Business Rules:
            - Cannot delete system territories (is_system=True)
            - Permission scoped via get_objects_for_bulk() (403 if out of scope)
            - Strict mode: Fails entirely if any territory can't be deleted
            - Partial mode: Deletes what it can, reports failures
            
        Returns:
            200 OK - All succeeded
            207 Multi-Status - Partial success
            400 Bad Request - All failed or validation error
            403 Forbidden - Attempting to delete territories outside permission scope
        """
        ctx = ctx_from_request(request)
        ctx.update({
            'event': 'bulk_delete_territories',
            'client_id': str(self.get_client_id())
        })
        
        detailed = request.query_params.get('detailed', 'false').lower() == 'true'
        results = {'success': [], 'failed': [], 'skipped': []}
        
        try:
            # =================================================================
            # INPUT VALIDATION
            # =================================================================
            
            if not isinstance(request.data, dict):
                raise StandardizedValidationError("Request must be a JSON object")
            
            ids = request.data.get('ids', [])
            mode = request.data.get('mode', 'partial')
            
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
            
            audit_log(
                event='bulk_delete_territories',
                action='bulk_delete',
                actor_id=str(request.user.id),
                client_id=str(self.get_client_id()),
                target_type='territory',
                target_count=len(ids),
                outcome='started',
                extra={'mode': mode}
            )
            
            # =================================================================
            # FETCH TERRITORIES WITH PERMISSION CHECK
            # =================================================================
            # Uses get_objects_for_bulk() from ScopedQuerysetMixin
            # - Raises 403 if any object is out of permission scope
            # - Returns not_found_ids for objects that don't exist
            
            client_id = self.get_client_id()
            result = self.get_objects_for_bulk(ids)
            territories_dict = result['objects']
            not_found_ids = result['not_found_ids']
            
            # =================================================================
            # HANDLE NOT FOUND IDs
            # =================================================================
            
            for nf_id in not_found_ids:
                results['failed'].append({
                    'id': nf_id,
                    'name': 'Unknown',
                    'errors': [str(CoreErrorMessages.OBJECT_NOT_FOUND)]
                })
            
            if mode == 'strict' and not_found_ids:
                return self._build_bulk_error_response(
                    results,
                    len(ids),
                    f"Strict mode: {len(not_found_ids)} territory(ies) not found"
                )
            
            # =================================================================
            # CHECK FOR PROTECTED (is_system=True) TERRITORIES
            # =================================================================
            
            protected_ids = []
            deletable_ids = []
            
            for territory_id, territory in territories_dict.items():
                if territory.is_system:
                    protected_ids.append(territory_id)
                    results['failed'].append({
                        'id': territory_id,
                        'name': territory.name,
                        'errors': [str(CoreErrorMessages.CANNOT_DELETE.format(fields='system territory'))]
                    })
                else:
                    deletable_ids.append(territory_id)
            
            if mode == 'strict' and protected_ids:
                return self._build_bulk_error_response(
                    results,
                    len(ids),
                    f"Strict mode: {len(protected_ids)} system territory(ies) cannot be deleted"
                )
            
            # =================================================================
            # DELETE OPERATIONS
            # =================================================================
            
            with disable_signals_with_invalidation(client_id, ['territories']):
                if mode == 'strict':
                    with transaction.atomic():
                        try:
                            # Store territory info before deletion
                            territories_info = {}
                            for territory_id in deletable_ids:
                                territory = territories_dict[territory_id]
                                territories_info[territory_id] = {
                                    'name': territory.name
                                }
                            
                            # SET-BASED DELETE
                            if deletable_ids:
                                deleted_count, deleted_by_model = Territory.objects.filter(
                                    id__in=deletable_ids,
                                    client_id=client_id
                                ).delete()
                                
                                logger.info(
                                    f"Bulk delete territories: {len(deletable_ids)} deleted",
                                    extra={
                                        **ctx,
                                        'deleted_count': deleted_count,
                                        'cascade': deleted_by_model
                                    }
                                )
                                
                                # Build success results
                                for territory_id in deletable_ids:
                                    info = territories_info[territory_id]
                                    results['success'].append({
                                        'id': territory_id,
                                        'name': info['name']
                                    })
                        
                        except Exception as e:
                            error_msg = self._format_bulk_error_message(e)
                            logger.error("Bulk delete strict mode failed", extra={
                                **ctx,
                                'error': error_msg
                            }, exc_info=True)
                            
                            return self._build_bulk_error_response(
                                {'success': [], 'failed': results['failed'], 'skipped': []},
                                len(ids),
                                f"Strict mode failed: {error_msg}"
                            )
                else:
                    # Partial mode
                    territories_info = {}
                    for territory_id in deletable_ids:
                        territory = territories_dict[territory_id]
                        territories_info[territory_id] = {
                            'name': territory.name
                        }
                    
                    # SET-BASED DELETE
                    try:
                        if deletable_ids:
                            deleted_count, deleted_by_model = Territory.objects.filter(
                                id__in=deletable_ids,
                                client_id=client_id
                            ).delete()
                            
                            for territory_id in deletable_ids:
                                info = territories_info[territory_id]
                                results['success'].append({
                                    'id': territory_id,
                                    'name': info['name']
                                })
                    
                    except Exception as e:
                        error_msg = self._format_bulk_error_message(e)
                        for territory_id in deletable_ids:
                            info = territories_info.get(territory_id, {'name': 'Unknown'})
                            results['failed'].append({
                                'id': territory_id,
                                'name': info['name'],
                                'errors': [error_msg]
                            })
            
            # =================================================================
            # BUILD RESPONSE
            # =================================================================
            
            success_count = len(results['success'])
            failed_count = len(results['failed'])
            
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
            
            return self._build_bulk_success_response(
                results,
                len(ids),
                operation='delete',
                detailed=detailed
            )
        
        except StandardizedValidationError as e:
            error_msg = str(e)
            if hasattr(e, 'detail') and isinstance(e.detail, dict):
                raw_error = e.detail.get('error', str(e))
                error_msg = str(raw_error)
            
            return self._build_bulk_error_response(
                results={'success': [], 'failed': [], 'skipped': []},
                total=len(request.data.get('ids', [])) if isinstance(request.data, dict) else 0,
                error_message=error_msg
        )
    
    # =========================================================================
    # BATCHED COUNTS
    # =========================================================================

    # Upper bound on ids per request. Matches the territory list's pageSize
    # fetch: one COUNT query runs per territory (territories have no stored
    # membership, so no GROUP BY is possible), and this caps that fan-in.
    MAX_COUNTS_IDS = 100

    @action(detail=False, methods=['post'], url_path='counts')
    def counts(self, request):
        """
        Return per-territory record counts for a batch of territory ids.

        Kills the per-card N+1: instead of one workspace request per contact
        card, the client asks for every visible territory's count in a single
        round-trip. Each territory is counted with the same filter evaluators
        the workspace uses (ACCOUNT -> AccountFilterService, CONTACT ->
        ContactFilterService), so batched counts match detail-view counts.

        Request Body:
            ids: List[UUID] - territory ids (1..MAX_COUNTS_IDS)

        Returns:
            200 OK - {"success": True, "data": {"<id>": {"type", "count"}}}
            400 Bad Request - ids missing, empty, wrong type, or over the cap
            403 Forbidden - any id exists but is outside permission scope

        Notes:
            - Ids that do not exist in the tenant (not_found) are silently
              omitted from the response map; the client only ever asks about
              ids of cards it is already displaying.
            - Counts are inherently one COUNT query per territory; the loop is
              bounded by MAX_COUNTS_IDS so a request can never fan out further.
        """
        from ..models import TerritoryType

        if not isinstance(request.data, dict):
            raise StandardizedValidationError(
                CoreErrorMessages.BULK_INVALID_FORMAT.format(entity="territory IDs")
            )

        ids = request.data.get('ids', [])
        if not isinstance(ids, list):
            raise StandardizedValidationError(
                CoreErrorMessages.BULK_INVALID_FORMAT.format(entity="territory IDs")
            )
        if not ids:
            raise StandardizedValidationError("At least one territory id is required.")
        if len(ids) > self.MAX_COUNTS_IDS:
            raise StandardizedValidationError(
                CoreErrorMessages.BULK_SIZE_EXCEEDED.format(
                    max_size=self.MAX_COUNTS_IDS, entity="territories"
                )
            )

        # Scope + permission: raises 403 if any id is out of scope; returns the
        # in-scope objects and the ids that simply do not exist in the tenant.
        result = self.get_objects_for_bulk(ids)
        territories_dict = result['objects']

        data = {}
        for territory_id, territory in territories_dict.items():
            if territory.type == TerritoryType.CONTACT:
                count = self._count_contacts_for_territory(territory, request)
            else:
                count = self._count_accounts_for_territory(territory, request)
            data[str(territory_id)] = {'type': territory.type, 'count': count}

        return Response({'success': True, 'data': data})

    # =========================================================================
    # HELPER METHODS (copied from accounts/views_bulk.py)
    # =========================================================================

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
        
        if isinstance(error, DRFValidationError):
            if hasattr(error, 'detail'):
                detail = error.detail
                if isinstance(detail, dict):
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
        
        return str(error) if error else "Processing failed"
    
    def _build_bulk_error_response(self, results, total, error_message):
        """Build standardized error response for bulk operations."""
        if error_message and not isinstance(error_message, str):
            error_message = str(error_message)
        
        if 'skipped' not in results:
            results['skipped'] = []
        
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
    
    def _build_bulk_success_response(self, results, total, operation='delete', detailed=False):
        """Build standardized success response for bulk operations."""
        success_count = len(results.get('success', []))
        failed_count = len(results.get('failed', []))
        skipped_count = len(results.get('skipped', []))
        
        if success_count == 0 and failed_count > 0:
            status_code = status.HTTP_400_BAD_REQUEST
            success_status = False
            
            failed_items = results.get('failed', [])
            extracted_message = None
            
            if failed_items:
                first_failed = failed_items[0]
                if isinstance(first_failed, dict) and 'errors' in first_failed:
                    errors_list = first_failed['errors']
                    if errors_list and len(errors_list) > 0:
                        raw_error = errors_list[0]
                        extracted_message = str(raw_error) if raw_error else None
            
            if extracted_message:
                message = extracted_message
            else:
                message = f"Bulk {operation} failed: all {failed_count} item(s) failed"
                
        elif failed_count > 0 or skipped_count > 0:
            status_code = status.HTTP_207_MULTI_STATUS
            success_status = 'partial'
            message = f"Bulk {operation}: {success_count} succeeded, {failed_count} failed, {skipped_count} skipped"
        else:
            status_code = status.HTTP_200_OK
            success_status = True
            message = f"Bulk {operation}: {success_count} item(s) processed successfully"
        
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