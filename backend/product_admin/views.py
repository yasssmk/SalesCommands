from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from core.auth_service import AuthService
from core.jwt_helpers import JWTHelpers
from .models import ProductAdmin
from .serializers import ProductAdminSerializer
from datetime import timedelta
from django.conf import settings

refresh_token_lifetime_product_admin = timedelta(days=1)

auth_service = AuthService(
    user_model=ProductAdmin,
    role='product_admin',
    refresh_lifetime=settings.ROLE_REFRESH_LIFETIMES['product_admin']
)

class RegisterProductAdminView(APIView):
    
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            user = auth_service.register_user(ProductAdminSerializer, request.data)
            return Response({"message": "Product admin created successfully"}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class LoginProductAdminView(APIView):
    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')

        try:
            response = Response({"message": "Login successful"}, status=status.HTTP_200_OK)
            auth_service.authenticate_user(email, password, response)
            return response
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_401_UNAUTHORIZED)

class LogoutProductAdminView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            response = Response({"message": "Logout successful"}, status=status.HTTP_200_OK)
            JWTHelpers.logout(response)
            return response
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class RefreshTokenView(APIView):
    def post(self, request):
        try:
            response = Response({"message": "Token refreshed"}, status=status.HTTP_200_OK)
            auth_service.refresh_tokens(request, response)
            return response
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_401_UNAUTHORIZED)