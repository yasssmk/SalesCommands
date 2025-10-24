"""
Operation status polling views.

Provides GET /ops/{key} endpoint for checking status of long-running
operations (bulk delete, bulk update, etc.) using idempotency store.

Usage:
    Frontend polls this endpoint while operation is running:
    
    GET /ops/bulk-delete-abc123
    
    Response (running):
    {
        "status": "running",
        "started_at": "2025-10-24T12:34:56.789Z",
        "message": "Operation in progress"
    }
    
    Response (succeeded):
    {
        "status": "succeeded",
        "started_at": "2025-10-24T12:34:56.789Z",
        "completed_at": "2025-10-24T12:35:01.234Z",
        "result": {
            "deleted": 42,
            "failed": 0
        }
    }
    
    Response (failed):
    {
        "status": "failed",
        "started_at": "2025-10-24T12:34:56.789Z",
        "completed_at": "2025-10-24T12:35:01.234Z",
        "error": "Database connection lost"
    }
"""

import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from core.idempotency import get_op, get_owner_from_request, is_public_endpoint
from core.exceptions import StandardizedValidationError

logger = logging.getLogger(__name__)


class OperationStatusView(APIView):
    """
    GET /ops/{key} - Poll operation status for long-running tasks.
    
    Returns current status of an operation identified by its idempotency key.
    Used by frontend to implement polling pattern for bulk operations.
    
    Authentication:
        Required (IsAuthenticated)
    
    Permissions:
        - User can only check operations from their tenant (client_id scoping)
        - Owner verification (operation.owner must match request owner)
    
    Path Parameters:
        key (str): Idempotency key of the operation
    
    Returns:
        200 OK: Operation found, returns status + result/error if completed
        404 Not Found: No operation found with this key
        403 Forbidden: Operation belongs to different tenant or user
        400 Bad Request: Missing tenant context
    
    Example:
        GET /ops/bulk-delete-abc123
        
        Response (202 Accepted - still running):
        {
            "status": "running",
            "started_at": "2025-10-24T12:34:56.789Z",
            "message": "Operation in progress"
        }
        
        Response (200 OK - completed):
        {
            "status": "succeeded",
            "started_at": "2025-10-24T12:34:56.789Z",
            "completed_at": "2025-10-24T12:35:01.234Z",
            "result": {...}
        }
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, key):
        """
        Get status of operation by idempotency key.
        
        Args:
            request: Django HttpRequest
            key: Idempotency key (from URL path)
        
        Returns:
            Response with operation status
        """
        try:
            # 1. Validate not a public endpoint (shouldn't happen, but safety check)
            if is_public_endpoint(request):
                raise StandardizedValidationError(
                    "Operation status endpoint requires authentication"
                )
            
            # 2. Extract client_id and owner
            # This will raise ValueError if tenant missing in strict mode (prod)
            owner = get_owner_from_request(request)
            
            # Extract client_id from owner string
            client_id = owner.split(':')[0]
            
            # Validate client_id is valid
            if client_id in ('unknown', 'public'):
                raise StandardizedValidationError(
                    "Tenant context required for operation status check"
                )
            
            try:
                client_id = int(client_id)
            except (ValueError, TypeError):
                raise StandardizedValidationError(
                    f"Invalid tenant ID: {client_id}"
                )
            
            logger.info(
                f"Polling operation status: key={key}",
                extra={
                    'client_id': client_id,
                    'owner': owner,
                    'key': key
                }
            )
            
            # 3. Get operation from idempotency store
            op = get_op(client_id, key)
            
            if not op:
                # Operation not found
                logger.warning(
                    f"Operation not found: key={key}",
                    extra={'client_id': client_id, 'key': key}
                )
                return Response(
                    {
                        'error': 'Operation not found',
                        'detail': f"No operation found with key '{key}'. "
                                 "It may have expired or never existed."
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # 4. Verify operation belongs to same owner (security check)
            op_owner = op.get('owner', '')
            
            if op_owner != owner:
                # Security: Don't leak information about other users' operations
                logger.warning(
                    f"Unauthorized operation access attempt: key={key}, "
                    f"expected_owner={owner}, actual_owner={op_owner}",
                    extra={'client_id': client_id, 'key': key}
                )
                return Response(
                    {
                        'error': 'Operation not found',
                        'detail': f"No operation found with key '{key}'."
                    },
                    status=status.HTTP_404_NOT_FOUND  # Don't reveal it exists
                )
            
            # 5. Build response based on status
            op_status = op.get('status', 'unknown')
            
            response_data = {
                'status': op_status,
                'started_at': op.get('started_at'),
            }
            
            # Add completion timestamp if available
            if 'completed_at' in op and op['completed_at']:
                response_data['completed_at'] = op['completed_at']
            
            # Handle different statuses
            if op_status == 'running':
                # Still processing
                response_data['message'] = 'Operation in progress'
                http_status = status.HTTP_202_ACCEPTED
            
            elif op_status == 'succeeded':
                # Completed successfully
                response_data['result'] = op.get('result', {})
                http_status = status.HTTP_200_OK
            
            elif op_status == 'failed':
                # Failed
                response_data['error'] = op.get('error', 'Unknown error')
                http_status = status.HTTP_200_OK  # 200 with error field (operation completed, just failed)
            
            else:
                # Unknown status
                response_data['message'] = f'Unknown operation status: {op_status}'
                http_status = status.HTTP_200_OK
            
            logger.debug(
                f"Operation status retrieved: key={key}, status={op_status}",
                extra={'client_id': client_id, 'key': key}
            )
            
            return Response(response_data, status=http_status)
        
        except StandardizedValidationError as e:
            # Client error (400)
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        except ValueError as e:
            # Tenant validation error (from get_owner_from_request in strict mode)
            return Response(
                {'error': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        
        except Exception as e:
            # Unexpected error (500)
            logger.error(
                f"Unexpected error polling operation: {e}",
                extra={'key': key},
                exc_info=True
            )
            return Response(
                {
                    'error': 'Internal server error',
                    'detail': 'Failed to retrieve operation status. Please try again.'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )