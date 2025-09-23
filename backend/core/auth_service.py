from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from django.contrib.auth.hashers import check_password
from django.utils.timezone import now
from .jwt_helpers import JWTHelpers
import logging

# Import de get_correlation_id avec fallback
try:
    from core.logging.context import get_correlation_id
except ImportError:
    def get_correlation_id():
        return '-'

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self, user_model, origin, refresh_lifetime, serializer_class):
        self.user_model = user_model
        self.serializer_class = serializer_class
        self.origin = origin
        self.refresh_lifetime = refresh_lifetime
        self.signing_key = (
            settings.SIMPLE_JWT['SIGNING_KEY_ADMIN'] 
            if origin == 'product_admin' 
            else settings.SIMPLE_JWT['SIGNING_KEY_USER']
        )

    def authenticate_user(self, email, password, response):
        """Authenticate user and set tokens."""

        # Contexte de log
        log_context = {
            'correlation_id': get_correlation_id(),
            'email': email[:3] + '***' if email else '-',  # Mask email
            'origin': self.origin,
            'event': 'login_attempt'
        }

        try:
            user = self.user_model.objects.get(email=email)
            log_context['user_id'] = str(user.id)
        except self.user_model.DoesNotExist:
            logger.warning("login_failed_user_not_found", extra=log_context)
            raise AuthenticationFailed("Invalid email or password")

        if not check_password(password, user.password):
            logger.warning("login_failed_invalid_password", extra={**log_context, 'user_id': str(user.id)})
            raise AuthenticationFailed("Invalid email or password")
        
        if not user.is_active:
            logger.warning("login_failed_account_disabled", extra={**log_context, 'user_id': str(user.id)})
            raise PermissionDenied
        
        # Update last_login
        user.last_login = now()
        user.save(update_fields=['last_login'])

        # Generate tokens with UUID support
        tokens = JWTHelpers.generate_token_response(
            user=user,
            origin=self.origin,
            refresh_lifetime=self.refresh_lifetime
        )
        
        # Set cookies
        JWTHelpers.set_cookie(
            response,
            'access_token',
            tokens['access'],
            max_age=settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds()
        )
        JWTHelpers.set_cookie(
            response,
            'refresh_token',
            tokens['refresh'],
            max_age=self.refresh_lifetime.total_seconds()
        )

        # Add user data to response
        response.data = {
            'user': self.serializer_class(user).data,
            'tokens': tokens
        }

        # Log successful login
        logger.info("login_success", extra={
            **log_context,
            'user_id': str(user.id),
            'client_id': str(user.client_account_id) if hasattr(user, 'client_account_id') and user.client_account_id else '-'
        })
        
        return user

    def register_user(self, data):
        """Register a new user with validation."""
        email = data.get('email')
        
        log_context = {
            'correlation_id': get_correlation_id(),
            'email': email[:3] + '***' if email else '-',
            'origin': self.origin,
            'event': 'registration_attempt'
        }
        
        if self.user_model.objects.filter(email=email).exists():
            logger.warning("registration_failed_email_exists", extra=log_context)
            raise AuthenticationFailed("User with this email already exists.")
        
        serializer = self.serializer_class(data=data)
        if serializer.is_valid():
            user = serializer.save()
            
            # Log successful registration
            logger.info("registration_success", extra={
                **log_context,
                'user_id': str(user.id),
                'client_id': str(user.client_account_id) if hasattr(user, 'client_account_id') and user.client_account_id else '-'
            })
            
            return self.serializer_class(user).data
        
        # Log registration failure
        logger.warning("registration_failed_validation", extra={
            **log_context,
            'errors': str(serializer.errors)[:200]  # Tronquer les erreurs
        })
        raise AuthenticationFailed(serializer.errors)

    def refresh_tokens(self, request, response):
        """
        Refresh user tokens and return user data.
        
        Returns both new tokens (set as cookies) and complete user data
        to maintain frontend state consistency during token refresh.
        
        Returns:
            dict: {"message": str, "user": dict} with serialized user data
        """
        log_context = {
            'correlation_id': get_correlation_id(),
            'origin': self.origin,
            'event': 'token_refresh_attempt'
        }
        
        refresh_token = request.COOKIES.get('refresh_token')
        if not refresh_token:
            logger.warning("token_refresh_failed_missing", extra=log_context)
            raise AuthenticationFailed("Refresh token is missing")
        
        try:
            # Validate and refresh tokens, get back the user_id
            token_result = JWTHelpers.validate_and_refresh_token(refresh_token, response)
            
            # Retrieve the user from the token's user_id
            user_id = token_result.get('user_id')
            if not user_id:
                logger.warning("token_refresh_failed_invalid", extra=log_context)
                raise AuthenticationFailed("Invalid token: no user identifier")
            
            # Get the user instance
            # Convert string UUID to actual UUID if needed
            import uuid
            if isinstance(user_id, str):
                user_id = uuid.UUID(user_id)
            
            user = self.user_model.objects.get(pk=user_id)
            
            if not user.is_active:
                logger.warning("token_refresh_failed_disabled", extra={
                    **log_context,
                    'user_id': str(user_id)
                })
                raise AuthenticationFailed("User account is deactivated")
            
            user_data = {
                "id": str(user.id),
                "name": user.get_full_name(),
                "email": user.email,
                "role": user.role_name if hasattr(user, 'role_name') else None,
                "avatar": None,
                "client_id": str(user.client_account_id) if hasattr(user, 'client_account_id') and user.client_account_id else None,
                "client_name": user.client_account.name if getattr(user, "client_account", None) else None,
            }
            
            # Log successful token refresh
            logger.info("token_refresh_success", extra={
                **log_context,
                'user_id': str(user.id),
                'client_id': str(user.client_account_id) if hasattr(user, 'client_account_id') and user.client_account_id else '-'
            })
            
            # Return both message and user data
            return {
                "message": "Token refreshed successfully",
                "user": user_data
            }
            
        except self.user_model.DoesNotExist:
            logger.warning("token_refresh_failed_user_not_found", extra={
                **log_context,
                'user_id': str(user_id) if 'user_id' in locals() else '-'
            })
            raise AuthenticationFailed("User not found")
        except Exception as e:
            logger.error("token_refresh_failed_unexpected", extra={
                **log_context,
                'error': str(e)[:200]
            }, exc_info=settings.DEBUG)
            raise AuthenticationFailed(f"Failed to retrieve user: {str(e)}")

    def logout_user(self, request, response):
        """Logout user and clear cookies."""
        log_context = {
            'correlation_id': get_correlation_id(),
            'origin': self.origin,
            'event': 'logout',
            'user_id': str(request.user.id) if hasattr(request, 'user') and hasattr(request.user, 'id') else '-',
            'client_id': getattr(request, 'client_id', '-')
        }
        
        JWTHelpers.logout(response)
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate, private'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        
        # Log successful logout
        logger.info("logout_success", extra=log_context)
        
        return {'message': 'Successfully logged out'}

    def enforce_permissions(self, request, required_origin):
        """
        Enforce role-based access control using JWT token information.
        """
        token_origin = request.auth.get('origin') if request.auth else None
        
        if not token_origin:
            raise PermissionDenied("Authentication required")
            
        if token_origin != required_origin:
            # Log permission denied
            logger.warning("permission_denied_wrong_origin", extra={
                'correlation_id': get_correlation_id(),
                'required_origin': required_origin,
                'token_origin': token_origin,
                'user_id': str(request.user.id) if hasattr(request, 'user') and hasattr(request.user, 'id') else '-',
                'path': getattr(request, 'path', '-')
            })
            raise PermissionDenied("You do not have permission to make this request")

    # Code Mort
    # def update_password(self, request, response):
    #     """Update user password with validation."""
    #     try:
    #         old_password = request.data.get('old_password')
    #         new_password = request.data.get('new_password')
            
    #         if not old_password or not new_password:
    #             raise AuthenticationFailed("Both old and new passwords are required")
                
    #         user = request.user
            
    #         if not check_password(old_password, user.password):
    #             raise AuthenticationFailed("Current password is incorrect")
            
    #         if check_password(new_password, user.password):
    #             raise AuthenticationFailed("New password must be different from current password")
            
    #         # Validate new password
    #         if hasattr(self.serializer_class, 'validate_password'):
    #             try:
    #                 new_password = self.serializer_class().validate_password(new_password)
    #             except Exception as e:
    #                 raise AuthenticationFailed(str(e.detail[0]))
            
    #         user.set_password(new_password)
    #         user.save(update_fields=['password'])
            
    #         self.logout_user(request, response)
            
    #         return {"message": "Password updated successfully. Please login with your new password"}
            
    #     except AuthenticationFailed as e:
    #         raise AuthenticationFailed(str(e))
    #     except Exception as e:
    #         raise AuthenticationFailed(f"Password update failed: {str(e)}")
        