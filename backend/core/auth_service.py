from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied, APIException
from django.contrib.auth.hashers import check_password
from django.utils.timezone import now
from .jwt_helpers import JWTHelpers
import logging

from core.logging import get_logger, ctx_from_request, get_correlation_id
from core.logging.audit import audit_log
from core.error_messages import CoreErrorMessages

try:
    import psycopg2
    DB_OPERATIONAL_ERROR = psycopg2.OperationalError
except ImportError:
    # Fallback si psycopg2 n'est pas installé (ex: tests avec SQLite)
    from django.db import OperationalError as DB_OPERATIONAL_ERROR

logger = get_logger(__name__)

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
        # Contexte de base (pas de request ici): on garantit une corrélation + champs standardisés
        log_context = {
            'correlation_id': get_correlation_id(),
            'event': 'login_attempt',
            'origin': self.origin,
            'email': email[:3] + '***' if email else '-',
            'user_id': '-',
            'client_id': '-',
            'method': '-',   # Uniformisation des clés
            'path': '-',
            'ip': '-',
        }

        try:
            user = self.user_model.objects.get(email=email)
            log_context['user_id'] = str(user.id)
            log_context['client_id'] = (
                str(user.client_account_id)
                if hasattr(user, 'client_account_id') and user.client_account_id
                else '-'
            )
        except self.user_model.DoesNotExist:
            logger.warning("login_failed_user_not_found", extra=log_context)

            audit_log(
                event='login_failed',
                action='login',
                actor_id='-',
                client_id='-',
                target_type='session',
                outcome='failed',
                extra={
                    'origin': self.origin,
                    'reason': 'user_not_found'
                }
            )
            

            raise AuthenticationFailed("Authentication failed")

        if not check_password(password, user.password):
            logger.warning("login_failed_invalid_password", extra=log_context)

            audit_log(
                event='login_failed',
                action='login',
                actor_id=str(user.id),
                client_id=str(user.client_account_id) if hasattr(user, 'client_account_id') and user.client_account_id else '-',
                target_type='session',
                outcome='failed',
                extra={
                    'origin': self.origin,
                    'reason': 'invalid_password'
                }
            )

            raise AuthenticationFailed("Invalid email or password")

        if not user.is_active:
            logger.warning("login_failed_account_disabled", extra=log_context)

            audit_log(
                event='login_failed',
                action='login',
                actor_id=str(user.id),
                client_id=str(user.client_account_id) if hasattr(user, 'client_account_id') and user.client_account_id else '-',
                target_type='session',
                outcome='failed',
                extra={
                    'origin': self.origin,
                    'reason': 'account_disabled'
                }
            )

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
        log_context['role_name'] = user.role_name if hasattr(user, 'role_name') else '-'
        logger.info("login_success", extra=log_context)

        audit_log(
            event='login_success',
            action='login',
            actor_id=str(user.id),
            client_id=str(user.client_account_id) if hasattr(user, 'client_account_id') and user.client_account_id else '-',
            target_type='session',
            outcome='success',
            extra={
                'origin': self.origin,
                'role_name': user.role_name if hasattr(user, 'role_name') else '-'
            }
        )

        return user

    def register_user(self, data):
        """Register a new user with validation."""
        email = data.get('email')

        # Contexte de base (pas de request ici)
        log_context = {
            'correlation_id': get_correlation_id(),
            'event': 'registration_attempt',
            'origin': self.origin,
            'email': email[:3] + '***' if email else '-',
            'user_id': '-',
            'client_id': '-',
            'method': '-',
            'path': '-',
            'ip': '-',
        }

        if self.user_model.objects.filter(email=email).exists():
            logger.warning("registration_failed_email_exists", extra=log_context)

            audit_log(
                event='registration_failed',
                action='register',
                actor_id='-',
                client_id='-',
                target_type='user',
                outcome='failed',
                extra={
                    'origin': self.origin,
                    'reason': 'email_exists'
                }
            )

            raise AuthenticationFailed("User with this email already exists.")

        serializer = self.serializer_class(data=data)
        if serializer.is_valid():
            user = serializer.save()

            # Mettre à jour le contexte
            log_context['user_id'] = str(user.id)
            log_context['client_id'] = (
                str(user.client_account_id)
                if hasattr(user, 'client_account_id') and user.client_account_id
                else '-'
            )
            log_context['role_name'] = user.role_name if hasattr(user, 'role_name') else '-'

            logger.info("registration_success", extra=log_context)
            audit_log(
                event='registration_success',
                action='register',
                actor_id=str(user.id),
                client_id=str(user.client_account_id) if hasattr(user, 'client_account_id') and user.client_account_id else '-',
                target_type='user',
                outcome='success',
                extra={
                    'origin': self.origin,
                    'role_name': user.role_name if hasattr(user, 'role_name') else '-'
                }
            )

            return self.serializer_class(user).data

        logger.warning("registration_failed_validation", extra={
            **log_context,
            'errors': str(serializer.errors)[:200]
        })
        audit_log(
            event='registration_failed',
            action='register',
            actor_id='-',
            client_id='-',
            target_type='user',
            outcome='failed',
            extra={
                'origin': self.origin,
                'reason': 'validation_error'
            }
        )
        raise AuthenticationFailed(serializer.errors)

    def refresh_tokens(self, request, response):
        """
        Refresh user tokens and return user data.

        Returns both new tokens (set as cookies) and complete user data
        to maintain frontend state consistency during token refresh.

        Returns:
            dict: {"message": str, "user": dict} with serialized user data
        """
        # Ici on a la request : on enrichit complètement le contexte
        log_context = {
            **ctx_from_request(request),
            'origin': self.origin,
            'event': 'token_refresh_attempt',
        }

        refresh_token = request.COOKIES.get('refresh_token')
        if not refresh_token:
            logger.warning("token_refresh_failed_missing", extra=log_context)

            audit_log(
                event='token_refresh_failed',
                action='token_refresh',
                actor_id='-',
                client_id='-',
                target_type='session',
                outcome='failed',
                extra={
                    'origin': self.origin,
                    'reason': 'missing_token'
                }
            )

            raise AuthenticationFailed("Refresh token is missing")

        try:
            # Validate and refresh tokens, get back the user_id
            token_result = JWTHelpers.validate_and_refresh_token(refresh_token, response)

            # Retrieve the user from the token's user_id
            user_id = token_result.get('user_id')
            if not user_id:
                logger.warning("token_refresh_failed_invalid", extra=log_context)

                audit_log(
                    event='token_refresh_failed',
                    action='token_refresh',
                    actor_id='-',
                    client_id='-',
                    target_type='session',
                    outcome='failed',
                    extra={
                        'origin': self.origin,
                        'reason': 'invalid_token'
                    }
                )
                raise AuthenticationFailed("Invalid token: no user identifier")

            # Get the user instance
            import uuid
            if isinstance(user_id, str):
                user_id = uuid.UUID(user_id)

            try:
                user = self.user_model.objects.get(id=user_id)
            except DB_OPERATIONAL_ERROR as db_err:
                # Log complet côté serveur (avec stack trace)
                logger.error(
                    "token_refresh_failed_db_unavailable",
                    extra={**log_context, 'db_error': str(db_err)[:200]},
                    exc_info=True
                )
                # Lever 503 avec message court standardisé (pas de détails techniques)
                raise APIException(
                    detail=str(CoreErrorMessages.SERVICE_UNAVAILABLE),
                    code=503
                )

            if not user.is_active:
                logger.warning("token_refresh_failed_disabled", extra={
                    **log_context,
                    'user_id': str(user_id)
                })

                audit_log(
                    event='token_refresh_failed',
                    action='token_refresh',
                    actor_id=str(user_id),
                    client_id=str(user.client_account_id) if hasattr(user, 'client_account_id') and user.client_account_id else '-',
                    target_type='session',
                    outcome='failed',
                    extra={
                        'origin': self.origin,
                        'reason': 'account_disabled'
                    }
                )

                raise AuthenticationFailed("User account is deactivated")

            user_data = {
                "id": str(user.id),
                "name": user.get_full_name(),
                "email": user.email,
                "role": user.role_name if hasattr(user, 'role_name') else None,
                "role_tier": user.role.get_tier() if user.role else None,
                "avatar": None,
                "client_id": str(user.client_account_id) if hasattr(user, 'client_account_id') and user.client_account_id else None,
                "client_name": user.client_account.name if getattr(user, "client_account", None) else None,
            }

            logger.info("token_refresh_success", extra={
                **log_context,
                'user_id': str(user.id),
                'client_id': str(user.client_account_id) if hasattr(user, 'client_account_id') and user.client_account_id else '-',
                'role_name': user.role_name if hasattr(user, 'role_name') else '-'
            })

            audit_log(
                event='token_refresh_success',
                action='token_refresh',
                actor_id=str(user.id),
                client_id=str(user.client_account_id) if hasattr(user, 'client_account_id') and user.client_account_id else '-',
                target_type='session',
                outcome='success',
                extra={
                    'origin': self.origin,
                    'role_name': user.role_name if hasattr(user, 'role_name') else '-'
                }
            )

            return {
                "message": "Token refreshed successfully",
                "user": user_data
            }
        
        
        except APIException:
            # Re-lever les APIException (503, etc.) sans transformation
            raise
        
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
            **ctx_from_request(request),
            'origin': self.origin,
            'event': 'logout'
        }

        JWTHelpers.logout(response)
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate, private'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'

        logger.info("logout_success", extra=log_context)

        audit_log(
            event='logout_success',
            action='logout',
            actor_id=str(request.user.id) if hasattr(request, 'user') and request.user else '-',
            client_id=str(request.user.client_account_id) if hasattr(request, 'user') and hasattr(request.user, 'client_account_id') and request.user.client_account_id else '-',
            target_type='session',
            outcome='success',
            extra={'origin': self.origin}
        )

        return {'message': 'Successfully logged out'}

    def enforce_permissions(self, request, required_origin):
        """
        Enforce role-based access control using JWT token information.
        """
        token_origin = request.auth.get('origin') if request.auth else None

        if not token_origin:
            raise PermissionDenied("Authentication required")

        if token_origin != required_origin:
            log_context = {
                **ctx_from_request(request),
                'required_origin': required_origin,
                'token_origin': token_origin,
                'event': 'permission_denied_wrong_origin'
            }
            logger.warning("permission_denied_wrong_origin", extra=log_context)
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
        