# backend/ops/views.py

"""
Ops Test Endpoints - Development & Testing Only

Provides utility endpoints for testing timeout handling, error scenarios,
and system health checks. These endpoints should be restricted in production
via middleware or removed entirely.

Endpoints:
- GET/POST /ops/sleep/<seconds>/ - Simulate slow operations (for timeout tests)
- GET /ops/error-500/ - Trigger 500 error
- GET /ops/error-404/ - Trigger 404 error  
- GET /ops/health/ - Basic health check with Redis status
"""

import time
import logging
from django.http import JsonResponse, Http404
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.cache_utils import is_redis_healthy
from core.logging.context import get_correlation_id
from rest_framework.permissions import AllowAny

logger = logging.getLogger(__name__)


# ============================================================================
# SLEEP ENDPOINT - Timeout Testing
# ============================================================================

@method_decorator(csrf_exempt, name='dispatch')
class SleepView(View):
    """
    Simulate slow operations for timeout testing.
    
    Usage:
        GET  /ops/sleep/5/  → Sleeps 5 seconds then returns 200
        POST /ops/sleep/12/ → Sleeps 12 seconds then returns 200
    
    Purpose:
        Test frontend timeout profiles (CRITICAL: 8s, WIDGET: 4s, MUTATION: 10s, BULK: 60s)
        Validate that timeouts occur at expected thresholds
    
    ⚠️ WARNING: This endpoint should be REMOVED or RESTRICTED in production!
    """
    permission_classes = [AllowAny]
    
    def get(self, request, seconds):
        return self._handle_sleep(request, seconds, 'GET')
    
    def post(self, request, seconds):
        return self._handle_sleep(request, seconds, 'POST')
    
    def _handle_sleep(self, request, seconds, method):
        """Common handler for GET/POST sleep requests."""
        try:
            sleep_duration = int(seconds)
            
            # Safety: Cap at 120 seconds to prevent abuse
            if sleep_duration > 120:
                return JsonResponse({
                    'error': 'Maximum sleep duration is 120 seconds'
                }, status=400)
            
            if sleep_duration < 0:
                return JsonResponse({
                    'error': 'Sleep duration must be positive'
                }, status=400)
            
            correlation_id = get_correlation_id()
            
            logger.info(
                f"[{correlation_id}] Sleep endpoint called - {method} {sleep_duration}s"
            )
            
            # Sleep for requested duration
            time.sleep(sleep_duration)
            
            logger.info(
                f"[{correlation_id}] Sleep completed - {method} {sleep_duration}s"
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Slept for {sleep_duration} seconds',
                'method': method,
                'duration': sleep_duration,
                'correlation_id': correlation_id,
                'timestamp': time.time()
            }, status=200)
            
        except ValueError:
            return JsonResponse({
                'error': 'Invalid seconds parameter - must be an integer'
            }, status=400)
        except Exception as e:
            logger.error(f"Sleep endpoint error: {e}", exc_info=True)
            return JsonResponse({
                'error': 'Internal server error',
                'detail': str(e)
            }, status=500)


# ============================================================================
# ERROR SIMULATION ENDPOINTS
# ============================================================================

class Error500View(APIView):
    """
    Trigger a 500 Internal Server Error for testing.
    
    Usage:
        GET /ops/error-500/
    
    Purpose:
        Test frontend error handling for 5xx errors
        Validate error logging and correlation ID tracking
    """

    permission_classes = [AllowAny] 
    
    def get(self, request):
        correlation_id = get_correlation_id()
        logger.error(
            f"[{correlation_id}] Simulated 500 error triggered",
            extra={'endpoint': '/ops/error-500/', 'method': 'GET'}
        )
        
        # Raise an exception to trigger 500 error handler
        raise Exception("Simulated 500 Internal Server Error for testing")


class Error404View(APIView):
    """
    Trigger a 404 Not Found error for testing.
    
    Usage:
        GET /ops/error-404/
    
    Purpose:
        Test frontend error handling for 404 errors
        Validate custom 404 error formatting
    """
    permission_classes = [AllowAny] 
    def get(self, request):
        correlation_id = get_correlation_id()
        logger.info(
            f"[{correlation_id}] Simulated 404 error triggered",
            extra={'endpoint': '/ops/error-404/', 'method': 'GET'}
        )
        
        raise Http404("Simulated 404 Not Found for testing")


# ============================================================================
# HEALTH CHECK ENDPOINT
# ============================================================================

class HealthCheckView(APIView):
    """
    Comprehensive health check with Redis status.
    
    Usage:
        GET /ops/health/
    
    Returns:
        {
            "status": "healthy",
            "redis": "connected",
            "timestamp": 1234567890.123
        }
    
    Purpose:
        Verify system dependencies (Redis)
        Monitor service availability
        Useful for load balancer health checks
    """
    permission_classes = [AllowAny] 
    def get(self, request):
        correlation_id = get_correlation_id()
        
        # Check Redis health
        redis_status = "connected" if is_redis_healthy() else "disconnected"
        
        # Determine overall status
        overall_status = "healthy" if redis_status == "connected" else "degraded"
        
        logger.info(
            f"[{correlation_id}] Health check performed",
            extra={
                'redis_status': redis_status,
                'overall_status': overall_status
            }
        )
        
        return Response({
            'status': overall_status,
            'redis': redis_status,
            'correlation_id': correlation_id,
            'timestamp': time.time()
        }, status=status.HTTP_200_OK if overall_status == "healthy" else status.HTTP_503_SERVICE_UNAVAILABLE)