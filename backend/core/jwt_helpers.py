from datetime import timedelta
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
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

        :param response: The HTTP response object.
        :param key: Cookie name to clear.
        """
        response.delete_cookie(key)

    @staticmethod
    def blacklist_refresh_token(token):
        """
        Add a refresh token to the blacklist (if not handled automatically by SimpleJWT).

        :param token: Refresh token string.
        """
        try:
            refresh = RefreshToken(token)
            refresh.blacklist()
        except Exception as e:
            raise AuthenticationFailed(f"Error blacklisting token: {str(e)}")

    @staticmethod
    def handle_token_rotation(old_token, new_refresh_token, response):
        """
        Handle token rotation by blacklisting the old refresh token and setting new cookies.

        :param old_token: Old refresh token to blacklist.
        :param new_refresh_token: New refresh token to set in cookies.
        :param response: HTTP response object to modify.
        """
        # Blacklist the old token
        if settings.SIMPLE_JWT['ROTATE_REFRESH_TOKENS']:
            JWTHelpers.blacklist_refresh_token(old_token)

        # Set the new refresh token in cookies
        JWTHelpers.set_cookie(
            response,
            'refresh_token',
            new_refresh_token,
            max_age=settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds()
        )

    @staticmethod
    def logout(response):
        """
        Clear cookies to logout the user.

        :param response: HTTP response object to modify.
        """
        JWTHelpers.clear_cookie(response, 'access_token')
        JWTHelpers.clear_cookie(response, 'refresh_token')

    @staticmethod
    def validate_and_refresh_token(request):
        """
        Validate the refresh token and issue a new access token.

        :param request: HTTP request object containing the refresh token.
        :return: Dictionary containing new tokens.
        """
        refresh_token = request.COOKIES.get('refresh_token')
        if not refresh_token:
            raise AuthenticationFailed("Refresh token is missing")

        try:
            refresh = RefreshToken(refresh_token)
            new_access_token = str(refresh.access_token)
            new_refresh_token = str(refresh)

            return {
                'access': new_access_token,
                'refresh': new_refresh_token,
            }
        except Exception as e:
            raise AuthenticationFailed(f"Token refresh failed: {str(e)}")

# Usage Example
# Set cookies on login response
# from django.http import JsonResponse
# response = JsonResponse({"message": "Login successful"})
# JWTHelpers.set_cookie(response, 'access_token', 'your_access_token_here', max_age=3600)
# JWTHelpers.set_cookie(response, 'refresh_token', 'your_refresh_token_here', max_age=86400)
