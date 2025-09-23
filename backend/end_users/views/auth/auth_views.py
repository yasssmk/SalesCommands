
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

# Import robuste de get_correlation_id
try:
    from backend.core.logging.context import get_correlation_id
except ImportError:
    try:
        from core.logging.context import get_correlation_id
    except ImportError:
        def get_correlation_id():
            return '-'

logger = logging.getLogger(__name__)


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


        from django.conf import settings
        auth_service = AuthService(
            user_model=User,
            origin='end_users',
            refresh_lifetime=settings.ROLE_REFRESH_LIFETIMES['end_users'],
            serializer_class=UserSerializer
        )
        
        response = Response(status=status.HTTP_200_OK)
        user = auth_service.authenticate_user(email, password, response)

        logger.info("user_login_view_success", extra={
            'correlation_id': get_correlation_id(),
            'user_id': str(user.id),
            'client_id': str(user.client_account_id) if user.client_account_id else '-',
            'origin': 'end_users',
            'event': 'login_view_success'
        })

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

            logger.debug("get_current_user", extra={
                'correlation_id': get_correlation_id(),
                'user_id': str(request.user.id) if hasattr(request, 'user') else '-',
                'client_id': str(user.client_account_id) if user.client_account_id else '-',
                'event': 'get_current_user'
            })
            
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
            raise StandardizedValidationError(f"Failed to get user info: {str(e)}")


class UserLogoutView(BaseAPIView):
    """View to logout users and clear tokens."""
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:

            logger.info("user_logout_view", extra={
                'correlation_id': get_correlation_id(),
                'user_id': str(request.user.id) if hasattr(request, 'user') else '-',
                'client_id': getattr(request, 'client_id', '-'),
                'event': 'logout_view'
            })
            
            from django.conf import settings
            auth_service = AuthService(
                user_model=User,
                origin='end_users',
                refresh_lifetime=settings.ROLE_REFRESH_LIFETIMES['end_users'],
                serializer_class=UserSerializer
            )
            
            response = Response({"message": "Logout successful"}, status=status.HTTP_200_OK)
            auth_service.logout_user(request, response)
            return response
        except Exception as e:
            raise StandardizedValidationError(str(e))


class UserRefreshTokenView(BaseAPIView):
    """View to refresh user tokens."""
    authentication_classes = []
    permission_classes = []
    
    def post(self, request):
        try:
            logger.info("token_refresh_view", extra={
                'correlation_id': get_correlation_id(),
                'event': 'token_refresh_view'
            })
            
            from django.conf import settings
            auth_service = AuthService(
                user_model=User,
                origin='end_users',
                refresh_lifetime=settings.ROLE_REFRESH_LIFETIMES['end_users'],
                serializer_class=UserSerializer
            )

             # Create response object first so cookies can be set on it
            response = Response(status=status.HTTP_200_OK)
            
            # refresh_tokens will set cookies on the response and return user data
            result = auth_service.refresh_tokens(request, response)

            logger.info("token_refresh_view_success", extra={
                'correlation_id': get_correlation_id(),
                'user_id': result.get('user', {}).get('id', '-'),
                'event': 'token_refresh_view_success'
            })
            
            # Set the enriched data (message + user)
            response.data = result
            
            return response
        
        except Exception as e:
            raise StandardizedValidationError(str(e))