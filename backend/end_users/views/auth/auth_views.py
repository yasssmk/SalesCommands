# backend/end_users/views/auth/auth_views.py

from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from core.apps_shared_methods import BaseAPIView
from core.auth_service import AuthService
from core.jwt_helpers import CustomJWTAuthentication
from core.throttling import LoginRateThrottle, PasswordChangeThrottle, BurstRateThrottle

from ...models import User
from ...serializers.user_serializer import (
    UserSerializer
)
import logging
from permissions import compat
from core.logging import get_logger, ctx_from_request 

logger = get_logger(__name__)



class UserLoginView(BaseAPIView):
    """View to authenticate users and return tokens."""
    authentication_classes = []  # Pas d'auth requise pour login
    permission_classes = []

    throttle_classes = [LoginRateThrottle, BurstRateThrottle]
    
    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        

        if not email or not password:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='Email and Password')
            )
        
        # ================================================================
        # CRITICAL SECURITY CHECK: Hard lockout enforcement
        # ================================================================
        # Check throttle BEFORE authentication to prevent post-throttle success.
        # This is a defense-in-depth measure that ensures throttle limits are
        # enforced even if DRF middleware has edge cases or race conditions.
        
        from core.throttle_enforcer import check_dual_throttle
        from rest_framework.exceptions import Throttled
        import math
        
        throttle_result = check_dual_throttle(
            request=request,
            email=email,
            scope='login'
        )
        
        if throttle_result['is_throttled']:
            wait_seconds = throttle_result.get('wait_seconds', 0)
            wait_seconds = max(0, int(math.ceil(wait_seconds)))
            
            # Log the blocked attempt
            ctx = ctx_from_request(request)
            ctx.update({
                'email': (email[:3] + '***') if email else '-',
                'event': 'login_blocked_throttled',
                'wait_seconds': wait_seconds,
                'violated_key': throttle_result.get('violated_key', '-')
            })
            logger.warning("login_blocked_throttled", extra=ctx)
            
            # Construct user-friendly message
            if wait_seconds >= 60:
                wait_minutes = math.ceil(wait_seconds / 60)
                time_msg = f"{wait_minutes} minute{'s' if wait_minutes > 1 else ''}"
            else:
                time_msg = f"{wait_seconds} second{'s' if wait_seconds != 1 else ''}"
            
            message = (
                f"Too many login attempts. Please wait {time_msg} before trying again."
            )
            
            # Raise Throttled exception BEFORE authentication runs
            # This ensures authentication is never called during lockout
            raise Throttled(detail=message)
        
        # ================================================================
        # END SECURITY CHECK
        # ================================================================

        # Log login attempt (safe extras)
        ctx = ctx_from_request(request)
        ctx.update({
            'email': (email[:3] + '***') if email else '-',
            'event': 'login_attempt',
            'throttle_key': f"{request.META.get('REMOTE_ADDR')}:{email.lower()}" if email else '-'
        })
        logger.info("login_attempt", extra=ctx)

        from django.conf import settings
        auth_service = AuthService(
            user_model=User,
            origin='end_users',
            refresh_lifetime=settings.ROLE_REFRESH_LIFETIMES['end_users'],
            serializer_class=UserSerializer
        )
        
        response = Response(status=status.HTTP_200_OK)
        
        # Pass request to auth_service for context
        user = auth_service.authenticate_user(email, password, response)

        # Log successful login with full context (safe extras)
        ctx = ctx_from_request(request)
        ctx.update({
            'user_id': str(user.id),
            'client_id': str(user.client_account_id) if user.client_account_id else '-',
            'origin': 'end_users',
            'event': 'login_success',
            'role_name': user.role_name if hasattr(user, 'role_name') else '-'
        })
        logger.info("login_success", extra=ctx)

        # AJOUT CRITIQUE : Définir request.user pour que get_auth_ctx() ne retourne pas "Anonymous"
        request.user = user
        
        # Peupler request.auth pour que get_auth_ctx puisse l'extraire
        client_id_val = getattr(user, 'client_account_id', None)
        request.auth = {
            "user_id": str(user.id),
            "client_account": str(client_id_val) if client_id_val else None,
            "origin": "end_users",
        }

        # IMPORTANT: pas de .update() sur Response(data=None) -> on assigne directement
        response.data = {
            "origin": "end_users",
            "message": "Login successful",
            "user": {
                "id": str(user.id),
                "name": user.get_full_name(),
                "email": user.email,
                "role": getattr(user, 'role_name', None),
                "client_id": str(client_id_val) if client_id_val else None,
                "client_name": getattr(getattr(user, "client_account", None), "name", None),
            }
        }

        return response


class UserCurrentView(BaseAPIView):
    """View to get current authenticated user info."""
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]
    



    http_method_names = ['get']

    def get(self, request):
        """Return current user information"""
        try:
            user = request.user

            ctx = ctx_from_request(request)
            ctx.update({
                'event': 'get_current_user',
                'user_id': str(user.id),
                'client_id': str(user.client_account_id) if getattr(user, 'client_account_id', None) else '-',
                'role_name': user.role_name if hasattr(user, 'role_name') else '-'
            })
            logger.debug("get_current_user", extra=ctx)
            
            serializer = UserSerializer(user)
            
            return Response({
                "success": True,
                "user": {
                    "id": str(user.id),
                    "name": user.get_full_name(),
                    "email": user.email,
                    "role": user.role_name if hasattr(user, 'role_name') else None,
                    "avatar": None, 
                    "client_id": str(user.client_account_id) if user.client_account_id else None,
                    "client_name": user.client_account.name if getattr(user, "client_account", None) else None,
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            ctx = ctx_from_request(request)
            ctx.update({
                'error': str(e)[:200],
                'event': 'get_current_user_failed'
            })
            logger.error("get_current_user_failed", extra=ctx)
            raise StandardizedValidationError(f"Failed to get user info: {str(e)}")


class UserLogoutView(BaseAPIView):
    """View to logout users and clear tokens."""
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:

            ctx = ctx_from_request(request)
            ctx.update({'event': 'logout_attempt'})
            logger.info("logout_attempt", extra=ctx)

            
            from django.conf import settings
            auth_service = AuthService(
                user_model=User,
                origin='end_users',
                refresh_lifetime=settings.ROLE_REFRESH_LIFETIMES['end_users'],
                serializer_class=UserSerializer
            )
            
            response = Response({"message": "Logout successful"}, status=status.HTTP_200_OK)
            
            # Pass request for context
            auth_service.logout_user(request, response)
            
            # Log success after logout
            ctx = ctx_from_request(request)
            ctx.update({
                'event': 'logout_success',
                'role_name': request.user.role_name if hasattr(request.user, 'role_name') else '-'
            })
            logger.info("logout_success", extra=ctx)
            
            return response
        except Exception as e:
            ctx = ctx_from_request(request)
            ctx.update({
                'error': str(e)[:200],
                'event': 'logout_failed'
            })
            logger.error("logout_failed", extra=ctx)
            # raise StandardizedValidationError(str(e))
            raise


class UserRefreshTokenView(BaseAPIView):
    """View to refresh user tokens."""
    authentication_classes = []
    permission_classes = []
    
    def post(self, request):
        try:
        
            ctx = ctx_from_request(request)
            ctx.update({'event': 'token_refresh_attempt'})
            logger.info("token_refresh_attempt", extra=ctx)
            
            from django.conf import settings
            auth_service = AuthService(
                user_model=User,
                origin='end_users',
                refresh_lifetime=settings.ROLE_REFRESH_LIFETIMES['end_users'],
                serializer_class=UserSerializer
            )

            response = Response(status=status.HTTP_200_OK)
            result = auth_service.refresh_tokens(request, response)

            # Log success with user info
            ctx = ctx_from_request(request)
            ctx.update({
                'user_id': result.get('user', {}).get('id', '-'),
                'client_id': result.get('user', {}).get('client_id', '-'),
                'event': 'token_refresh_success',
                'role_name': result.get('user', {}).get('role', '-')
            })
            logger.info("token_refresh_success", extra=ctx)
            
            # Peupler request.user et request.auth pour le middleware
            user_id = result.get('user', {}).get('id')
            client_id_val = result.get('user', {}).get('client_id')
            
            if user_id:
                # Récupérer l'objet user pour request.user
                user = User.objects.get(id=user_id)
                request.user = user
                
                request.auth = {
                    "user_id": str(user_id),
                    "client_account": str(client_id_val) if client_id_val else None,
                    "origin": "end_users",
                }
            
            response.data = result
            
            return response
        
        except Exception as e:
            ctx = ctx_from_request(request)
            ctx.update({
                'error': str(e)[:200],
                'event': 'token_refresh_failed'
            })
            logger.error("token_refresh_failed", extra=ctx)
            raise 
