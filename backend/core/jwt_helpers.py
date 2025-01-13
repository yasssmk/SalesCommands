from datetime import timedelta
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken, Token
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from django.contrib.auth.hashers import check_password
from django.contrib.auth import get_user_model
from django.http import JsonResponse


# JWT Helpers for Cookies and Security
class JWTHelpers:
    @staticmethod
    def set_cookie(response, key, value, max_age):
        """
        Securely set an HTTP-only cookie.

        :param response: The HTTP response object.
        :param key: Cookie name.
        :param value: Cookie value.
        :param max_age: Maximum age of the cookie in seconds.
        """
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
        """
        Clear an HTTP-only cookie.
        """
        response.delete_cookie(key)


    @staticmethod
    def logout(response):
        """
        Clear cookies to logout the user.
        """
        JWTHelpers.clear_cookie(response, 'access_token')
        JWTHelpers.clear_cookie(response, 'refresh_token')



    @staticmethod
    def validate_and_refresh_token(refresh_token, response):
        """Validate and refresh tokens."""
        try:
            refresh = RefreshToken(refresh_token)
            
            # Get role and set correct signing key
            role = refresh.get('role', 'default')
            if role == 'product_admin':
                RefreshToken.signing_key = settings.SIMPLE_JWT['SIGNING_KEY_ADMIN']
            else:
                RefreshToken.signing_key = settings.SIMPLE_JWT['SIGNING_KEY_USER']
            
            # Create new tokens
            new_access = refresh.access_token
            new_refresh = RefreshToken()
            
            # Copy claims from old refresh token
            for claim in refresh.payload:
                if claim not in ('jti', 'exp', 'iat'):
                    new_refresh[claim] = refresh[claim]
            
            # Set cookies with new tokens
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
                max_age=settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds()
            )
            
            return {'access': str(new_access), 'refresh': str(new_refresh)}
        except Exception as e:
            raise AuthenticationFailed(f"Token refresh failed: {str(e)}")
        
        
# Usage Example
# Set cookies on login response
# from django.http import JsonResponse
# response = JsonResponse({"message": "Login successful"})
# JWTHelpers.set_cookie(response, 'access_token', 'your_access_token_here', max_age=3600)
# JWTHelpers.set_cookie(response, 'refresh_token', 'your_refresh_token_here', max_age=86400)
