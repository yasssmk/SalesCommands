from datetime import timedelta, datetime
import uuid
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from product_admin.models import ProductAdmin

from core.error_messages import AuthErrorMessages

class UUIDEncoder:
    @staticmethod
    def encode(obj):
        if isinstance(obj, uuid.UUID):
            return str(obj)
        return obj

    @staticmethod
    def decode(obj):
        try:
            return uuid.UUID(obj)
        except (TypeError, ValueError):
            return obj

class CustomJWTAuthentication(JWTAuthentication):

    def authenticate(self, request):
        try:
            return super().authenticate(request)
        except InvalidToken:
            raise AuthenticationFailed(AuthErrorMessages.AUTH_REQUIRED)
        except TokenError:
            raise AuthenticationFailed(AuthErrorMessages.AUTH_REQUIRED)
        except Exception:
            raise AuthenticationFailed(AuthErrorMessages.AUTH_REQUIRED)
        
    def get_validated_token(self, raw_token):
        """Override to use custom token class if needed"""
        validated_token = super().get_validated_token(raw_token)
        # Convert string UUID back to UUID object if needed
        if 'user_id' in validated_token:
            validated_token['user_id'] = UUIDEncoder.decode(validated_token['user_id'])
        return validated_token

    def get_user(self, validated_token):
        """Resolve user model based on the token payload with UUID support"""
        user_id = validated_token.get("user_id")
        origin = validated_token.get("origin")
        from end_users.models import User

        if not user_id or not origin:
            raise InvalidToken("Invalid token payload")

        # Determine user model based on origin
        if origin == "product_admin":
            user_model = ProductAdmin
        elif origin == "end_users":
            user_model = User
        else:
            raise InvalidToken("Invalid origin in token")
        

        # Convert string to UUID if needed
        if isinstance(user_id, str):
            try:
                user_id = UUIDEncoder.decode(user_id)
            except (TypeError, ValueError):
                raise InvalidToken("Invalid user ID format")

        try:
            user = user_model.objects.get(pk=user_id)

            if not user.is_active:
                raise InvalidToken("User is inactive")

            return user

        except user_model.DoesNotExist:
            raise InvalidToken("User not found")
        except Exception as e:
            raise InvalidToken(f"Authentication failed: {str(e)}")

class JWTHelpers:
    @staticmethod
    def set_cookie(response, key, value, max_age):
        """Securely set an HTTP-only cookie."""
        response.set_cookie(
            key,
            value,
            max_age=max_age,
            httponly=True,
            secure=True,
            samesite='Lax',
        )

    @staticmethod
    def clear_cookie(response, key):
        """Clear an HTTP-only cookie."""
        response.delete_cookie(key)

    @staticmethod
    def logout(response):
        """Clear authentication cookies."""
        JWTHelpers.clear_cookie(response, 'access_token')
        JWTHelpers.clear_cookie(response, 'refresh_token')

    @staticmethod
    def generate_token_response(user, origin, refresh_lifetime):
        """Generate tokens with proper UUID handling"""
        RefreshToken.signing_key = (
            settings.SIMPLE_JWT['SIGNING_KEY_ADMIN'] 
            if origin == 'product_admin' 
            else settings.SIMPLE_JWT['SIGNING_KEY_USER']
        )

        refresh = RefreshToken.for_user(user)
        
        # Prepare payload with UUID handling
        payload = {
            'origin': origin,
            'user_id': UUIDEncoder.encode(user.id),
        }

        if origin == 'end_users':
            payload.update({
                'role': user.role.name if user.role else None,
                'role_id': UUIDEncoder.encode(user.role.id) if user.role else None,
                'client_account': UUIDEncoder.encode(user.client_account.id) if user.client_account else None,
            })

        refresh.payload.update(payload)
        refresh.set_exp(lifetime=refresh_lifetime)

        access = refresh.access_token
        access.payload.update(payload)

        return {
            'access': str(access),
            'refresh': str(refresh),
            'user_id': str(user.id)
        }

    @staticmethod
    def validate_and_refresh_token(refresh_token, response):
        """Validate and refresh tokens with UUID support"""
        try:
            refresh = RefreshToken(refresh_token)

            # Check if token has expired using the exp claim
            if refresh.get('exp') < datetime.now().timestamp():
                JWTHelpers.logout(response)
                raise AuthenticationFailed("Token has expired, please login again")
            
            # Get origin and set correct signing key
            origin = refresh.get('origin', 'default')
            RefreshToken.signing_key = (
                settings.SIMPLE_JWT['SIGNING_KEY_ADMIN']
                if origin == 'product_admin'
                else settings.SIMPLE_JWT['SIGNING_KEY_USER']
            )
            
            # Create new tokens preserving UUID handling
            new_access = refresh.access_token
            new_refresh = RefreshToken()
            
            # Copy claims preserving UUID format
            for claim in refresh.payload:
                if claim not in ('jti', 'exp', 'iat'):
                    value = refresh[claim]
                    if claim in ['user_id', 'role_id', 'client_account']:
                        value = UUIDEncoder.encode(UUIDEncoder.decode(value))
                    new_refresh[claim] = value
            
            # Set cookies
            JWTHelpers.set_cookie(
                response,
                'access_token',
                str(new_access),
                max_age=settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds()
            )
            JWTHelpers.set_cookie(
                response,
                'refresh_token',
                str(new_refresh),
                max_age=settings.ROLE_REFRESH_LIFETIMES.get(origin, settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME']).total_seconds()
            )
            
            return {
                'access': str(new_access),
                'refresh': str(new_refresh)
            }
        except Exception as e:
            raise AuthenticationFailed(f"Token refresh failed: {str(e)}")

