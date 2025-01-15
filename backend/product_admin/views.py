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



auth_service = AuthService(
    user_model=ProductAdmin,
    serializer_class=ProductAdminSerializer,
    role='product_admin',
    refresh_lifetime=settings.ROLE_REFRESH_LIFETIMES['product_admin']
)

class RegisterProductAdminView(APIView):
    
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            auth_service.register_user(request.data)
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
            auth_service.logout_user(request, response)
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

# class UpdatePasswordView(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         try:
#             response = Response(status=status.HTTP_200_OK)
#             result = auth_service.update_password(request, response)
#             response.data = result
#             return response
            
#         except Exception as e:
#             return Response(
#                 {"error": "An unexpected error occurred"}, 
#                 status=status.HTTP_400_BAD_REQUEST
#             )

from end_users.models import ClientAccount, UserRole
from end_users.serializers import ClientAccountSerializer
from end_users.views import RegisterUserView
from rest_framework.test import APIRequestFactory

class CreateClientView(APIView):
    """
    View to create a new client account and its default admin user.
    Only accessible by product_admin users.
    """

    def post(self, request):
        # Check if the role in the JWT is 'product_admin'
        # auth_user_role = request.auth.get('role')  # Extract the role from the JWT
        # if auth_user_role != 'product_admin':
        #     return Response(
        #         {"error": "You do not have permission to create a client."},
        #         status=status.HTTP_403_FORBIDDEN,
        #     )

        # Extract data for client and admin from the request
        client_data = request.data.get('client')
        admin_data = request.data.get('admin')

        if not client_data or not admin_data:
            return Response(
                {"error": "Both client and admin data are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Serialize and create the client account
        client_serializer = ClientAccountSerializer(data=client_data)
        if not client_serializer.is_valid():
            return Response(
                {"error": "Invalid client data.", "details": client_serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        client = client_serializer.save()  # Save the client account
        print(f"BOOM ID du yenyen {client.id}")

        # Automatically assign the new client's UUID to the admin
        admin_data['client_account'] = client.id

        # Retrieve the Admin role for the new client (created via signals)
        try:
            admin_role = UserRole.objects.get(client_account=client, name="Admin")
            admin_data['role'] = admin_role.id
        except UserRole.DoesNotExist:
            client.delete()  # Rollback the client creation
            return Response(
                {"error": "Admin role not found for the new client."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Call RegisterUserView directly to create the admin user
        factory = APIRequestFactory()
        admin_request = factory.post(
            '/client/register/',
            data=admin_data,
            format='json',
            HTTP_AUTHORIZATION=request.headers.get('Authorization'),
        )
        register_user_view = RegisterUserView.as_view()

        response = register_user_view(admin_request)
        if response.status_code != 201:
            client.delete()  # Rollback the client creation if admin creation fails
            return Response(
                {"error": "Failed to create admin user.", "details": response.data},
                status=response.status_code,
            )

        return Response(
            {
                "message": "Client and admin user created successfully.",
                "client": client_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )