from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import authenticate
from .models import ProductAdmin
from .serializers import ProductAdminSerializer, ProductAdminLoginSerializer
from django.conf import settings
from datetime import timedelta
from core.jwt_helpers import generate_tokens, clear_cookie, set_cookie
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()

refresh_token_lifetime_product_admin = timedelta(days=1)

class RegisterProductAdminView(APIView):
    def post(self, request):

        serializer = ProductAdminSerializer(data=request.data)
        email = request.data.get('email')
        print(email)
        if ProductAdmin.objects.filter(email=email).exists():
            return Response({"error": "Product admin already exists."}, status=status.HTTP_409_CONFLICT)
        
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Product admin created successfully."}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LoginProductAdminView(APIView):
     def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')

        print(request.data)

        try:
            # Fetch the user based on the email
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "Invalid email or password"}, status=status.HTTP_401_UNAUTHORIZED)

        # Check if the password matches
        if not check_password(password, user.password):
            return Response({"error": "Invalid email or password"}, status=status.HTTP_401_UNAUTHORIZED)

        # Generate JWT tokens
        tokens = generate_tokens(user)

        # Set HTTP-only cookies
        response = Response({"message": "Login successful", "access_token": tokens['access_token'], "refresh": tokens['refresh_token']}, status=status.HTTP_200_OK)
        set_cookie(response, settings.SIMPLE_JWT['AUTH_COOKIE'], tokens['access_token'], 
                   max_age=settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds())
        set_cookie(response, 'refresh_token', tokens['refresh_token'], 
                   max_age=settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds())

        return response

class LogoutProductAdminView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            # Validate the access token explicitly
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith("Bearer "):
                raise AuthenticationFailed("No valid Authorization header provided")

            token = auth_header.split(" ")[1]
            AccessToken(token)  # Decode and validate the access token

            # If token is valid, clear cookies and return success response
            response = Response({"message": "Logout successful"}, status=200)
            response.delete_cookie('access_token')
            response.delete_cookie('refresh_token')
            return response

        except AuthenticationFailed as e:
            return Response({"detail": str(e)}, status=401)

class ProductAdminRefreshTokenView(APIView):
    """
    View to refresh JWT tokens using the refresh token.
    """
    def post(self, request):

        refresh_token = request.COOKIES.get('refresh_token')
        print(refresh_token)
        if not refresh_token:
            return Response({"error": "Refresh token not provided"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            refresh = RefreshToken(refresh_token)
            new_access_token = str(refresh.access_token)
            print(new_access_token)

            # Rotate refresh token
            if settings.SIMPLE_JWT.get('ROTATE_REFRESH_TOKENS', False):
                refresh.blacklist()
                refresh.set_exp(lifetime=settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'])
                new_refresh_token = str(refresh)
            else:
                new_refresh_token = refresh_token

            # Set new tokens in cookies
            response = Response({"message": "Token refreshed", "access_token": new_access_token})
            set_cookie(response, settings.SIMPLE_JWT['AUTH_COOKIE'], new_access_token, 
                       max_age=settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds())
            set_cookie(response, 'refresh_token', new_refresh_token, 
                       max_age=settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds())
            return response
        except Exception as e:
            return Response({"error": "Invalid refresh token"}, status=status.HTTP_401_UNAUTHORIZED)
        