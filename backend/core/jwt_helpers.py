from datetime import timedelta, timezone
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed

def generate_tokens(user, refresh_lifetime=None):
    """
    Generate access and refresh tokens for the given user.
    """
    # Dynamically set refresh token lifetime if provided
    refresh_lifetime = refresh_lifetime or settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME']
    
    # Generate tokens using SimpleJWT
    refresh = RefreshToken.for_user(user)
    refresh.set_exp(lifetime=refresh_lifetime)
    
    return {
        'access_token': str(refresh.access_token),
        'refresh_token': str(refresh),
    }

def decode_token(token):
    """
    Decode and validate a JWT using SimpleJWT utilities.
    """
    from rest_framework_simplejwt.tokens import UntypedToken
    from rest_framework_simplejwt.exceptions import TokenError

    try:
        UntypedToken(token)  # Validates token
        return True
    except TokenError:
        raise AuthenticationFailed("Invalid or expired token")

def set_cookie(response, key, value, max_age, http_only=True):
    """
    Helper function to set a secure HTTP-only cookie.
    """
    response.set_cookie(
        key=key,
        value=value,
        max_age=max_age,
        httponly=http_only,
        secure=settings.SIMPLE_JWT.get('AUTH_COOKIE_SECURE', True),
        samesite=settings.SIMPLE_JWT.get('AUTH_COOKIE_SAMESITE', 'Lax')
    )

def clear_cookie(response, key):
    """
    Helper function to clear a cookie.
    """
    response.delete_cookie(key)
