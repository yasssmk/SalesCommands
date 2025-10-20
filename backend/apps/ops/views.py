# backend/apps/ops/views.py

"""
Operations Test Views - TEMPORARY FOR MVP VALIDATION

These endpoints are for testing timeout behavior and error handling.
They should be REMOVED or DISABLED in production.

⚠️ WARNING: These endpoints intentionally sleep and can cause performance issues.
Only enable in development/staging environments.
"""

import time
import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def sleep_view(request, seconds):
    """
    Test endpoint that sleeps for N seconds before responding.
    
    Used to validate timeout behavior:
    - Frontend timeout profiles (critical=8s, widget=4s, mutation=10s, bulk=60s)
    - Backend timeout handling (Gunicorn 15s, DB 10s)
    - 408 Request Timeout error handling
    - Retry logic (GET vs POST)
    
    Args:
        seconds (int): Number of seconds to sleep (1-120)
    
    Returns:
        200 OK with {slept: seconds, method: GET/POST}
        OR 408 if client timeout occurs first
    
    Examples:
        GET /ops/sleep/5/   → Sleeps 5s then returns 200
        POST /ops/sleep/12/ → Sleeps 12s then returns 200 (may timeout at 10s)
    
    Usage with TestTimeoutButton.jsx:
        - CRITICAL (8s): GET /ops/sleep/12/ → Should timeout after 8s
        - WIDGET (4s): GET /ops/sleep/6/ → Should timeout after 4s
        - MUTATION (10s): POST /ops/sleep/12/ → Should timeout after 10s
        - BULK (60s): POST /ops/sleep/65/ → Should timeout after 60s
    
    ⚠️ SECURITY: Only accessible with authentication.
    ⚠️ PERFORMANCE: Can block worker threads. Use with caution.
    """
    
    # Validate seconds parameter
    try:
        sleep_duration = int(seconds)
    except (ValueError, TypeError):
        return Response(
            {'error': 'Invalid seconds parameter. Must be an integer.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Safety limits
    if sleep_duration < 1:
        return Response(
            {'error': 'Sleep duration must be at least 1 second.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if sleep_duration > 120:
        return Response(
            {'error': 'Sleep duration cannot exceed 120 seconds (safety limit).'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Log the test (for debugging)
    correlation_id = getattr(request, 'correlation_id', 'unknown')
    logger.info(
        f"[OPS TEST] Sleep test started: {request.method} /ops/sleep/{sleep_duration}/ "
        f"(correlation_id={correlation_id}, user={request.user.id})"
    )
    
    # Sleep (blocks current worker thread)
    try:
        time.sleep(sleep_duration)
    except Exception as e:
        logger.error(f"[OPS TEST] Sleep interrupted: {str(e)}")
        return Response(
            {'error': 'Sleep interrupted', 'detail': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    # Success response
    logger.info(
        f"[OPS TEST] Sleep test completed: {request.method} /ops/sleep/{sleep_duration}/ "
        f"(correlation_id={correlation_id})"
    )
    
    return Response({
        'slept': sleep_duration,
        'method': request.method,
        'message': f'Successfully slept for {sleep_duration} seconds',
        'correlation_id': correlation_id
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def error_500_view(request):
    """
    Test endpoint that raises a 500 Internal Server Error.
    
    Used to validate 5xx error handling:
    - Frontend error display (snackbar)
    - Retry logic (GET should retry 3x)
    - Error message: "Server error. Try again later."
    
    Returns:
        500 Internal Server Error (always)
    
    ⚠️ SECURITY: Only accessible with authentication.
    """
    correlation_id = getattr(request, 'correlation_id', 'unknown')
    logger.warning(
        f"[OPS TEST] 500 error test triggered (correlation_id={correlation_id}, user={request.user.id})"
    )
    
    # Deliberately raise an exception
    raise Exception("Test 500 error - This is intentional for testing error handling")


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def error_404_view(request):
    """
    Test endpoint that returns a 404 Not Found.
    
    Used to validate 404 error handling:
    - Frontend error display (snackbar, severity=info)
    - No retry (404 is not retryable)
    - Error message: "Resource not found."
    
    Returns:
        404 Not Found (always)
    
    ⚠️ SECURITY: Only accessible with authentication.
    """
    correlation_id = getattr(request, 'correlation_id', 'unknown')
    logger.info(
        f"[OPS TEST] 404 error test triggered (correlation_id={correlation_id}, user={request.user.id})"
    )
    
    return Response(
        {'error': 'Test resource not found - This is intentional for testing'},
        status=status.HTTP_404_NOT_FOUND
    )


@api_view(['GET'])
def health_ops_view(request):
    """
    Simple health check for ops endpoints (no auth required).
    
    Returns:
        200 OK with status message
    """
    return Response({
        'status': 'ok',
        'message': 'Ops test endpoints are available',
        'endpoints': [
            'GET/POST /ops/sleep/<seconds>/',
            'GET /ops/error/500/',
            'GET /ops/error/404/'
        ]
    }, status=status.HTTP_200_OK)