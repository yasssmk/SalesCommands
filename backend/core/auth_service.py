from datetime import timedelta
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from django.contrib.auth.hashers import check_password
from django.contrib.auth import get_user_model
from .jwt_helpers import JWTHelpers

# Shared Auth Logic
class AuthService:
    def __init__(self, user_model, role, refresh_lifetime):
        """
        Shared authentication logic for managing tokens and user authentication.

        :param user_model: Django model for authentication (e.g., ProductAdmin, ProductUser).
        :param role: Role associated with the user (e.g., admin, user_admin, user).
        :param refresh_lifetime: Refresh token lifetime.
        """
        self.user_model = user_model
        self.role = role
        self.refresh_lifetime = refresh_lifetime

        # Use different signing keys based on the model for added security
        if role == 'product_admin':
            self.signing_key = settings.SIMPLE_JWT['SIGNING_KEY_ADMIN']
        else:
            self.signing_key = settings.SIMPLE_JWT['SIGNING_KEY_USER']

    def generate_tokens(self, user):
        """
        Generate access and refresh tokens with role-based claims.

        :param user: The authenticated user.
        :return: Dictionary containing access and refresh tokens.
        """
        refresh = RefreshToken.for_user(user)
        refresh['role'] = self.role
        refresh.set_exp(lifetime=self.refresh_lifetime)

        access = refresh.access_token
        access['role'] = self.role

        return {
            'access': str(access),
            'refresh': str(refresh),
        }

    def authenticate_user(self, email, password, response):
        """
        Authenticate a user with email and password and set tokens in cookies.

        :param email: User email.
        :param password: Raw password.
        :param response: HTTP response object to modify.
        :return: Authenticated user object.
        """
        try:
            user = self.user_model.objects.get(email=email)
        except self.user_model.DoesNotExist:
            raise AuthenticationFailed("Invalid email or password")

        if not check_password(password, user.password):
            raise AuthenticationFailed("Invalid email or password")

        # Generate tokens and set cookies
        tokens = self.generate_tokens(user)
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
            max_age=settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds()
        )
        return user

    def register_user(self, serializer_class, data):
        """
        Register a new user and handle duplicate validation.

        :param serializer_class: Serializer class for the user.
        :param data: Request data for user registration.
        :return: Registered user object.
        """
        email = data.get('email')
        if self.user_model.objects.filter(email=email).exists():
            raise AuthenticationFailed("User with this email already exists.")
        
        serializer = serializer_class(data=data)
        if serializer.is_valid():
            user = serializer.save()
            return user
        raise AuthenticationFailed(serializer.errors)

    def refresh_tokens(self, request, response):
        """
        Refresh tokens for a user based on their role.

        :param request: HTTP request containing refresh token in cookies.
        :param response: HTTP response object to modify.
        :return: Response object with new tokens set in cookies.
        """
        tokens = JWTHelpers.validate_and_refresh_token(request)
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
            max_age=settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds()
        )
        return response

    def logout_user(self, response):
        """
        Logout a user by clearing their cookies.

        :param response: HTTP response object to modify.
        """
        try:
            JWTHelpers.logout(response)
        except Exception as e:
            raise AuthenticationFailed(f"Logout process failed: {str(e)}")

    def validate_token(self, token):
        """
        Validate a JWT token.

        :param token: JWT token string.
        :return: Decoded token payload.
        """
        try:
            return AccessToken(token)
        except Exception as e:
            raise AuthenticationFailed(f"Token validation failed: {str(e)}")

    def enforce_permissions(self, required_role):
        """
        Enforce role-based access control.

        :param required_role: Role required to access the resource.
        """
        if self.role != required_role:
            raise PermissionDenied("You do not have permission to access this resource")

