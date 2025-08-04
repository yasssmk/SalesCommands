# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework import status
# from rest_framework.permissions import IsAuthenticated
# from rest_framework.exceptions import PermissionDenied
# from core.auth_service import AuthService
# from end_users.models import User, UserRole, Team, ClientAccount
# from end_users.serializers import UserSerializer
# from django.conf import settings

# auth_service = AuthService(
#     user_model=User,
#     origin='end_users',
#     refresh_lifetime=settings.ROLE_REFRESH_LIFETIMES['end_users'],
#     serializer_class=UserSerializer
# )


# class UserLoginView(APIView):
#     """View to authenticate users and return tokens."""
#     def post(self, request):
#         email = request.data.get('email')
#         password = request.data.get('password')

#         try:
#             response = Response(status=status.HTTP_200_OK)
#             user = auth_service.authenticate_user(email, password, response)
#             response.data.update({
#                 "origin": "end_users",
#                 "message": "Login successful"
#             })
#             return response
#         except Exception as e:
#             return Response(
#                 {"error": str(e)}, 
#                 status=status.HTTP_401_UNAUTHORIZED
#             )
    
# class UserLogoutView(APIView):
#     """
#     View to logout users and clear tokens.
#     """
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         try:
#             response = Response({"message": "Logout successful"}, status=status.HTTP_200_OK)
#             auth_service.logout_user(request, response)
#             return response
#         except Exception as e:
#             return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

# class UserRefreshTokenView(APIView):
#     """
#     View to refresh user tokens.
#     """
#     def post(self, request):
#         try:
#             response = Response({"message": "Token refreshed"}, status=status.HTTP_200_OK)
#             auth_service.refresh_tokens(request, response)
#             return response
#         except Exception as e:
#             return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

# class AdminCreateUserView(APIView):
#     """
#     View to allow admin users to create users within their client account.
#     """
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         try:
#             # Verify end_users origin
#             auth_service.enforce_permissions(request, 'end_users')

#             # Extract role and client account from JWT
#             user_role = request.auth.get('role')
#             client_account_id = request.auth.get('client_account')

#             # Verify admin role
#             if user_role != "Admin":
#                 raise PermissionDenied("Only Admin users can create other users.")

#             # Check max users limit
#             user_count = User.objects.filter(client_account_id=client_account_id).count()
#             client_account = ClientAccount.objects.get(id=client_account_id)
#             if user_count >= client_account.max_users:
#                 return Response(
#                     {"error": "Cannot create more users. Maximum user limit reached for this client."},
#                     status=status.HTTP_400_BAD_REQUEST,
#                 )

#             # Prepare user data
#             user_data = request.data.copy()
#             user_data['client_account'] = client_account_id

#             # Validate required fields
#             required_fields = ['email', 'password', 'role']
#             missing_fields = [field for field in required_fields if field not in user_data]
#             if missing_fields:
#                 return Response(
#                     {"error": f"Missing required fields: {', '.join(missing_fields)}"},
#                     status=status.HTTP_400_BAD_REQUEST,
#                 )

#             # Get role by name for this client account
#             try:
#                 role = UserRole.objects.get(
#                     name=user_data['role'], 
#                     client_account_id=client_account_id
#                 )
#                 user_data['role'] = str(role.id)  # Convert UUID to string for serializer
#             except UserRole.DoesNotExist:
#                 # Get available roles for better error message
#                 available_roles = UserRole.objects.filter(
#                     client_account_id=client_account_id
#                 ).values_list('name', flat=True)
                
#                 return Response(
#                     {
#                         "error": f"Invalid role. Available roles for your client account are: {', '.join(available_roles)}"
#                     },
#                     status=status.HTTP_400_BAD_REQUEST,
#                 )

#             # Validate team if provided
#             if 'team' in user_data:
#                 try:
#                     team = Team.objects.get(
#                         id=user_data['team'],
#                         organization__client_account_id=client_account_id
#                     )
#                     # Automatically set organization based on the team
#                     user_data['organization'] = team.organization.id
#                 except Team.DoesNotExist:
#                     return Response(
#                         {"error": "Invalid team or team does not belong to your client account."},
#                         status=status.HTTP_400_BAD_REQUEST,
#                     )

#             # Register the user using auth_service
#             try:
#                 user = auth_service.register_user(user_data)
#                 return Response(
#                     {
#                         "message": "User created successfully.",
#                         "user": user
#                     },
#                     status=status.HTTP_201_CREATED,
#                 )
#             except Exception as e:
#                 return Response(
#                     {"error": f"Failed to create user: {str(e)}"},
#                     status=status.HTTP_400_BAD_REQUEST,
#                 )

#         except PermissionDenied as e:
#             return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
#         except Exception as e:
#             return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)