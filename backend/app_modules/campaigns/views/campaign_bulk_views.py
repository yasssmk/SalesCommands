# app_modules/campaigns/views/campaign_bulk_views.py
"""
Campaign Bulk Operations ViewSet

SIMPLIFIED VERSION (no idempotency wrapper)
==========================================

Mirrors app_modules/territories/views/views_bulk.py:
- No idempotency wrapper (synchronous only): campaign volume is low and
  deletion runs in well under a second, so there is no timeout risk and the
  frontend does not need the 202 Accepted + polling mechanism.
- partial / strict modes, max 500 ids, BulkOperationThrottle.
- Permission + client scoping inherited from CampaignViewSet.

Two intentional differences from Territory's bulk delete:

1. PROTECTED ITEM GUARD
   Territory protects is_system=True. Campaign protects the TARGETED
   singleton (Campaign.is_targeted): it is created once per user per client
   by signal and must never be deleted, exactly like the single-object
   destroy() which calls _assert_not_targeted().

2. CASCADE (see the block in bulk_delete)
   Territory has a minimal cascade and relies on a plain set-based delete.
   Campaign does NOT: Activity.campaign is on_delete=SET_NULL, so a set-based
   Campaign.objects.delete() would orphan the linked activities instead of
   removing them. CampaignViewSet.destroy() handles this by deleting the
   activities explicitly first; the bulk path replicates that behavior for
   the whole deletable batch. All other relations (CampaignAccount,
   CampaignContact, CampaignMember) are on_delete=CASCADE and are removed
   automatically.

Response format is fully compatible with:
- handleBulkError() frontend utility
- Standard snackbar notifications
- AlertCampaignBulkDelete component
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

from app_modules.activities.models import Activity

from ..models import Campaign
from .campaign_views import CampaignViewSet

logger = get_logger(__name__)


class CampaignBulkViewSet(CampaignViewSet):
    """
    ViewSet for bulk campaign operations.

    Inherits authentication, permissions, and client scoping from
    CampaignViewSet.

    Simplified synchronous implementation - no idempotency wrapper needed
    because:
    - Low volume operations (typically a handful of campaigns per user)
    - No timeout risk
    """

    throttle_classes = [BulkOperationThrottle]

    # =========================================================================
    # BULK DELETE
    # =========================================================================

    @action(detail=False, methods=['delete'], url_path='bulk-delete')
    def bulk_delete(self, request):
        """
        Bulk delete campaigns.

        Request Body:
            ids: List[UUID] - Campaign IDs to delete
            mode: str - 'partial' (default, best-effort) or 'strict' (all-or-nothing)

        Query Params:
            detailed: bool - Include full results in response (default: false)

        Business Rules:
            - Cannot delete the TARGETED singleton campaign (is_targeted)
            - Permission scoped via get_objects_for_bulk() (403 if out of scope)
            - Strict mode: Fails entirely if any campaign can't be deleted
            - Partial mode: Deletes what it can, reports failures

        Returns:
            200 OK - All succeeded
            207 Multi-Status - Partial success
            400 Bad Request - All failed or validation error
            403 Forbidden - Attempting to delete campaigns outside permission scope
        """
        ctx = ctx_from_request(request)
        ctx.update({
            'event': 'bulk_delete_campaigns',
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
                    CoreErrorMessages.BULK_INVALID_FORMAT.format(entity="campaign IDs")
                )

            if not ids:
                raise StandardizedValidationError(CoreErrorMessages.BULK_DELETE_NO_IDS)

            if len(ids) > 500:
                raise StandardizedValidationError(
                    CoreErrorMessages.BULK_SIZE_EXCEEDED.format(max_size=500, entity="campaigns")
                )

            if mode not in ['partial', 'strict']:
                raise StandardizedValidationError(CoreErrorMessages.BULK_MODE_INVALID)

            audit_log(
                event='bulk_delete_campaigns',
                action='bulk_delete',
                actor_id=str(request.user.id),
                client_id=str(self.get_client_id()),
                target_type='campaign',
                target_count=len(ids),
                outcome='started',
                extra={'mode': mode}
            )

            # =================================================================
            # FETCH CAMPAIGNS WITH PERMISSION CHECK
            # =================================================================
            # Uses get_objects_for_bulk() from ScopedQuerysetMixin
            # - Raises 403 if any object is out of permission scope
            # - Returns not_found_ids for objects that don't exist

            client_id = self.get_client_id()
            result = self.get_objects_for_bulk(ids)
            campaigns_dict = result['objects']
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
                    f"Strict mode: {len(not_found_ids)} campaign(s) not found"
                )

            # =================================================================
            # CHECK FOR PROTECTED (TARGETED singleton) CAMPAIGNS
            # =================================================================
            # Mirrors the is_system guard in territories/views_bulk.py: the
            # TARGETED campaign is created once per user per client and must
            # never be deleted (see CampaignViewSet._assert_not_targeted).

            protected_ids = []
            deletable_ids = []

            for campaign_id, campaign in campaigns_dict.items():
                if campaign.is_targeted:
                    protected_ids.append(campaign_id)
                    results['failed'].append({
                        'id': campaign_id,
                        'name': campaign.name,
                        'errors': [str(CoreErrorMessages.CANNOT_DELETE.format(fields='the targeted campaign'))]
                    })
                else:
                    deletable_ids.append(campaign_id)

            if mode == 'strict' and protected_ids:
                return self._build_bulk_error_response(
                    results,
                    len(ids),
                    f"Strict mode: {len(protected_ids)} targeted campaign(s) cannot be deleted"
                )

            # =================================================================
            # DELETE OPERATIONS
            # =================================================================
            # Cache invalidation covers BOTH the 'campaigns' and 'activities'
            # namespaces because deleting campaigns also removes their linked
            # activities below (matches CampaignViewSet._invalidate_campaign_caches).

            with disable_signals_with_invalidation(client_id, ['campaigns', 'activities']):
                if mode == 'strict':
                    with transaction.atomic():
                        try:
                            # Store campaign info before deletion
                            campaigns_info = {}
                            for campaign_id in deletable_ids:
                                campaign = campaigns_dict[campaign_id]
                                campaigns_info[campaign_id] = {
                                    'name': campaign.name
                                }

                            if deletable_ids:
                                # CASCADE DIVERGENCE vs Territory: Activity.campaign is
                                # on_delete=SET_NULL, so activities must be deleted
                                # explicitly (as CampaignViewSet.destroy() does at
                                # campaign_views.py) — a set-based Campaign delete alone
                                # would orphan them. CampaignAccount / CampaignContact /
                                # CampaignMember are CASCADE and drop automatically.
                                Activity.objects.filter(
                                    campaign_id__in=deletable_ids,
                                    client_id=client_id
                                ).delete()

                                # SET-BASED DELETE
                                deleted_count, deleted_by_model = Campaign.objects.filter(
                                    id__in=deletable_ids,
                                    client_id=client_id
                                ).delete()

                                logger.info(
                                    f"Bulk delete campaigns: {len(deletable_ids)} deleted",
                                    extra={
                                        **ctx,
                                        'deleted_count': deleted_count,
                                        'cascade': deleted_by_model
                                    }
                                )

                                # Build success results
                                for campaign_id in deletable_ids:
                                    info = campaigns_info[campaign_id]
                                    results['success'].append({
                                        'id': campaign_id,
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
                    campaigns_info = {}
                    for campaign_id in deletable_ids:
                        campaign = campaigns_dict[campaign_id]
                        campaigns_info[campaign_id] = {
                            'name': campaign.name
                        }

                    try:
                        if deletable_ids:
                            # CASCADE DIVERGENCE vs Territory (see strict branch above):
                            # delete Activity rows explicitly before the campaigns
                            # because Activity.campaign is on_delete=SET_NULL.
                            Activity.objects.filter(
                                campaign_id__in=deletable_ids,
                                client_id=client_id
                            ).delete()

                            # SET-BASED DELETE
                            deleted_count, deleted_by_model = Campaign.objects.filter(
                                id__in=deletable_ids,
                                client_id=client_id
                            ).delete()

                            for campaign_id in deletable_ids:
                                info = campaigns_info[campaign_id]
                                results['success'].append({
                                    'id': campaign_id,
                                    'name': info['name']
                                })

                    except Exception as e:
                        error_msg = self._format_bulk_error_message(e)
                        for campaign_id in deletable_ids:
                            info = campaigns_info.get(campaign_id, {'name': 'Unknown'})
                            results['failed'].append({
                                'id': campaign_id,
                                'name': info['name'],
                                'errors': [error_msg]
                            })

            # =================================================================
            # BUILD RESPONSE
            # =================================================================

            success_count = len(results['success'])
            failed_count = len(results['failed'])

            audit_log(
                event='bulk_delete_campaigns_completed',
                action='bulk_delete',
                actor_id=str(request.user.id),
                client_id=str(client_id),
                target_type='campaign',
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
    # HELPER METHODS (mirrors territories/views_bulk.py)
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
