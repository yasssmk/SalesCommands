from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from core.auth_service import AuthService
from end_users.models import User, UserRole, Team
from end_users.serializers import UserSerializer
from django.conf import settings

auth_service = AuthService(
    user_model=User,
    role='user',
    refresh_lifetime=settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'],
    serializer_class=UserSerializer
)


class RegisterUserView(APIView):
    """
    View to register a new user with additional fields.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user_data = request.data

        # Validate required fields
        required_fields = ['email', 'password', 'client_account', 'role']
        missing_fields = [field for field in required_fields if field not in user_data]
        if missing_fields:
            return Response(
                {"error": f"Missing required fields: {', '.join(missing_fields)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Ensure the role belongs to the same client_account
        try:
            role = UserRole.objects.get(id=user_data['role'], client_account_id=user_data['client_account'])
        except UserRole.DoesNotExist:
            return Response(
                {"error": "Invalid role or role does not belong to the specified client account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Ensure the team (if provided) belongs to the same client_account
        team = None
        if 'team' in user_data:
            try:
                team = Team.objects.get(id=user_data['team'], organization__client_account_id=user_data['client_account'])
            except Team.DoesNotExist:
                return Response(
                    {"error": "Invalid team or team does not belong to the specified client account."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Automatically set organization based on the team
            user_data['organization'] = team.organization.id

        # Register the user
        try:
            user = auth_service.register_user(UserSerializer, user_data)
            user_serializer = UserSerializer(user)
            return Response(
                {"message": "User registered successfully.", "user": user_serializer.data},
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return Response(
                {"error": "Failed to register user.", "details": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

