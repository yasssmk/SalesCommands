from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from django.contrib.auth.hashers import check_password
from .jwt_helpers import JWTHelpers

class AuthService:
    def __init__(self, user_model, role, refresh_lifetime):
        self.user_model = user_model
        self.role = role
        self.refresh_lifetime = refresh_lifetime
        self.signing_key = (settings.SIMPLE_JWT['SIGNING_KEY_ADMIN'] 
                           if role == 'product_admin' 
                           else settings.SIMPLE_JWT['SIGNING_KEY_USER'])

    def generate_tokens(self, user):
        """Generate access and refresh tokens with role-based claims."""
        # Set signing key
        RefreshToken.signing_key = self.signing_key
        
        refresh = RefreshToken.for_user(user)
        refresh.payload.update({
            'role': self.role,
            'user_id': str(user.id),
        })
        refresh.set_exp(lifetime=self.refresh_lifetime)
        
        access = refresh.access_token
        access.payload.update({
            'role': self.role,
            'user_id': str(user.id)
        })
        
        return {
            'access': str(access),
            'refresh': str(refresh),
        }

    def authenticate_user(self, email, password, response):
        """Authenticate user and set tokens."""
        try:
            user = self.user_model.objects.get(email=email)
        except self.user_model.DoesNotExist:
            raise AuthenticationFailed("Invalid email or password")

        if not check_password(password, user.password):
            raise AuthenticationFailed("Invalid email or password")

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
            max_age=self.refresh_lifetime.total_seconds()
        )
        return user

    def register_user(self, serializer_class, data):
        """Register a new user."""
        email = data.get('email')
        if self.user_model.objects.filter(email=email).exists():
            raise AuthenticationFailed("User with this email already exists.")
        
        serializer = serializer_class(data=data)
        if serializer.is_valid():
            return serializer.save()
        raise AuthenticationFailed(serializer.errors)

    def refresh_tokens(self, request, response):
        """Refresh user tokens."""
        refresh_token = request.COOKIES.get('refresh_token')
        if not refresh_token:
            raise AuthenticationFailed("Refresh token is missing")
        return JWTHelpers.validate_and_refresh_token(refresh_token, response)

    def logout_user(self, request, response):
        """Logout user."""
        JWTHelpers.logout(response)

    def enforce_permissions(self, required_role):
        """Enforce role-based access control."""
        if self.role != required_role:
            raise PermissionDenied("You do not have permission to access this resource")