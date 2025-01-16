from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from django.contrib.auth.hashers import check_password
from django.utils.timezone import now
from .jwt_helpers import JWTHelpers

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
        try:
            user = self.user_model.objects.get(email=email)
        except self.user_model.DoesNotExist:
            raise AuthenticationFailed("Invalid email or password")

        if not check_password(password, user.password):
            raise AuthenticationFailed("Invalid email or password")
        
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
        
        return user

    def register_user(self, data):
        """Register a new user with validation."""
        email = data.get('email')
        if self.user_model.objects.filter(email=email).exists():
            raise AuthenticationFailed("User with this email already exists.")
        
        serializer = self.serializer_class(data=data)
        if serializer.is_valid():
            user = serializer.save()
            return self.serializer_class(user).data
        raise AuthenticationFailed(serializer.errors)

    def refresh_tokens(self, request, response):
        """Refresh user tokens."""
        refresh_token = request.COOKIES.get('refresh_token')
        if not refresh_token:
            raise AuthenticationFailed("Refresh token is missing")
        return JWTHelpers.validate_and_refresh_token(refresh_token, response)

    def logout_user(self, request, response):
        """Logout user and clear cookies."""
        JWTHelpers.logout(response)
        return {'message': 'Successfully logged out'}

    def enforce_permissions(self, request, required_origin):
        """
        Enforce role-based access control using JWT token information.
        """
        token_origin = request.auth.get('origin') if request.auth else None
        
        if not token_origin:
            raise PermissionDenied("Authentication required")
            
        if token_origin != required_origin:
            raise PermissionDenied("You do not have permission to make this request")

    def update_password(self, request, response):
        """Update user password with validation."""
        try:
            old_password = request.data.get('old_password')
            new_password = request.data.get('new_password')
            
            if not old_password or not new_password:
                raise AuthenticationFailed("Both old and new passwords are required")
                
            user = request.user
            
            if not check_password(old_password, user.password):
                raise AuthenticationFailed("Current password is incorrect")
            
            if check_password(new_password, user.password):
                raise AuthenticationFailed("New password must be different from current password")
            
            # Validate new password
            if hasattr(self.serializer_class, 'validate_password'):
                try:
                    new_password = self.serializer_class().validate_password(new_password)
                except Exception as e:
                    raise AuthenticationFailed(str(e.detail[0]))
            
            user.set_password(new_password)
            user.save(update_fields=['password'])
            
            self.logout_user(request, response)
            
            return {"message": "Password updated successfully. Please login with your new password"}
            
        except AuthenticationFailed as e:
            raise AuthenticationFailed(str(e))
        except Exception as e:
            raise AuthenticationFailed(f"Password update failed: {str(e)}")
        

# from django.conf import settings
# from rest_framework_simplejwt.tokens import RefreshToken
# from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
# from django.contrib.auth.hashers import check_password
# from .jwt_helpers import JWTHelpers
# from django.utils.timezone import now

# class AuthService:
#     def __init__(self, user_model, origin, refresh_lifetime, serializer_class):
#         self.user_model = user_model
#         self.serializer_class = serializer_class
#         self.origin = origin
#         self.refresh_lifetime = refresh_lifetime
#         self.signing_key = (settings.SIMPLE_JWT['SIGNING_KEY_ADMIN'] 
#                            if origin == 'product_admin' 
#                            else settings.SIMPLE_JWT['SIGNING_KEY_USER'])

#     def generate_tokens(self, user):
#         """Generate access and refresh tokens with claims based on origin."""
#         # Set signing key
#         RefreshToken.signing_key = self.signing_key

#         refresh = RefreshToken.for_user(user)
#         payload = {
#             'origin': self.origin,  
#             'user_id': str(user.id),
#         }

#         # Add additional claims only for end_users
#         if self.origin == 'end_users':
#             payload.update({
#                 'role': user.role.name if user.role else None,
#                 'role_id': str(user.role.id) if user.role else None,
#                 'client_account': str(user.client_account.id) if user.client_account else None,
#             })

#         # Update payload
#         refresh.payload.update(payload)
#         refresh.set_exp(lifetime=self.refresh_lifetime)

#         access = refresh.access_token
#         access.payload.update(payload)

#         return {
#             'access': str(access),
#             'refresh': str(refresh),
#         }

#     def authenticate_user(self, email, password, response):
#         """Authenticate user and set tokens."""
#         try:
#             user = self.user_model.objects.get(email=email)
#         except self.user_model.DoesNotExist:
#             raise AuthenticationFailed("Invalid email or password")

#         if not check_password(password, user.password):
#             raise AuthenticationFailed("Invalid email or password")
        
#         # Update last_login for the user
#         user.last_login = now()
#         user.save(update_fields=['last_login'])

#         tokens = self.generate_tokens(user)
        
#         JWTHelpers.set_cookie(
#             response,
#             'access_token',
#             tokens['access'],
#             max_age=settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds()
#         )
#         JWTHelpers.set_cookie(
#             response,
#             'refresh_token',
#             tokens['refresh'],
#             max_age=self.refresh_lifetime.total_seconds()
#         )
#         return user

#     def register_user(self, data):
#         """Register a new user."""
#         email = data.get('email')
#         if self.user_model.objects.filter(email=email).exists():
#             raise AuthenticationFailed("User with this email already exists.")
        
#         serializer = self.serializer_class(data=data)
#         if serializer.is_valid():
#             return serializer.save()
#         raise AuthenticationFailed(serializer.errors)

#     def refresh_tokens(self, request, response):
#         """Refresh user tokens."""
#         refresh_token = request.COOKIES.get('refresh_token')
#         if not refresh_token:
#             raise AuthenticationFailed("Refresh token is missing")
#         return JWTHelpers.validate_and_refresh_token(refresh_token, response)

#     def logout_user(self, request, response):
#         """Logout user."""
#         JWTHelpers.logout(response)

#     def enforce_permissions(self, required_origin):
#         """Enforce role-based access control."""
#         if self.origin != required_origin:
#             raise PermissionDenied("You do not have permission to access this resource")
    
    # def update_password(self, request, response):
    #     """
    #     Update user password with validation.
    #     """
    #     try:
    #         old_password = request.data.get('old_password')
    #         new_password = request.data.get('new_password')
            
    #         # Validate input
    #         if not old_password or not new_password:
    #             raise AuthenticationFailed("Both old and new passwords are required")
                
    #         user = request.user
            
    #         # Verify old password
    #         if not check_password(old_password, user.password):
    #             raise AuthenticationFailed("Current password is incorrect")
            
    #         # Check if new password is same as old password
    #         if check_password(new_password, user.password):
    #             raise AuthenticationFailed("New password must be different from current password")
            
    #         # Only validate the password field
    #         if hasattr(self.serializer_class, 'validate_password'):
    #             try:
    #                 new_password = self.serializer_class().validate_password(new_password)
    #             except Exception as e:
    #                 raise AuthenticationFailed(str(e.detail[0]))
            
    #         # Update password
    #         user.set_password(new_password)
    #         user.save(update_fields=['password'])
            
    #         # Logout user
    #         self.logout_user(request, response)
            
    #         return {"message": "Password updated successfully. Please login with your new password"}
            
    #     except AuthenticationFailed as e:
    #         raise AuthenticationFailed(str(e))
    #     except Exception as e:
    #         raise AuthenticationFailed(f"Password update failed: {str(e)}")