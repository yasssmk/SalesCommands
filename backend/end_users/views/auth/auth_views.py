# Modifications dans backend/end_users/views/auth/auth_views.py

from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from core.apps_shared_methods import BaseAPIView
from core.auth_service import AuthService
from core.jwt_helpers import CustomJWTAuthentication
from ...models import User
from ...serializers.user_serializer import (
    UserSerializer
)
import logging

from core.logging import get_logger, ctx_from_request  

logger = get_logger(__name__)


class UserLoginView(BaseAPIView):
    """View to authenticate users and return tokens."""
    authentication_classes = []  # Pas d'auth requise pour login
    permission_classes = []
    
    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')

        if not email or not password:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='Email and Password')
            )

        # Log login attempt (safe extras)
        ctx = ctx_from_request(request)
        ctx.update({
            'email': (email[:3] + '***') if email else '-',
            'event': 'login_attempt'
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
            'event': 'login_success'
        })
        logger.info("login_success", extra=ctx)

        response.data.update({
            "origin": "end_users",
            "message": "Login successful",
            "user": {
                "id": str(user.id),
                "name": user.get_full_name(),
                "email": user.email,
                "role": user.role_name
            }
        })

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
            ctx.update({'event': 'get_current_user'})
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
            ctx.update({'event': 'logout_success'})
            logger.info("logout_success", extra=ctx)
            
            return response
        except Exception as e:
            ctx = ctx_from_request(request)
            ctx.update({
                'error': str(e)[:200],
                'event': 'logout_failed'
            })
            logger.error("logout_failed", extra=ctx)
            raise StandardizedValidationError(str(e))


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

            # Create response object first so cookies can be set on it
            response = Response(status=status.HTTP_200_OK)
            
            # Pass request for context
            result = auth_service.refresh_tokens(request, response)

            # Log success with user info
            ctx = ctx_from_request(request)
            ctx.update({
                'user_id': result.get('user', {}).get('id', '-'),
                'event': 'token_refresh_success'
            })
            logger.info("token_refresh_success", extra=ctx)
            
            # Set the enriched data (message + user)
            response.data = result
            
            return response
        
        except Exception as e:
            ctx = ctx_from_request(request)
            ctx.update({
                'error': str(e)[:200],
                'event': 'token_refresh_failed'
            })
            logger.error("token_refresh_failed", extra=ctx)
            raise StandardizedValidationError(str(e))
