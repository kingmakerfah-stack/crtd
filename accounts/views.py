from django.conf import settings
from django.contrib.auth import get_user_model
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from .serializers import RoleBasedRegisterSerializer as RegisterSerializer
from .serializers import GoogleAuthSerializer

User = get_user_model()


class GoogleAuthView(APIView):
	permission_classes = [AllowAny]

	def post(self, request):
		serializer = GoogleAuthSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)

		token_value = serializer.validated_data["id_token"]
		role = serializer.validated_data.get("role")

		if not settings.GOOGLE_OAUTH_CLIENT_ID:
			return Response(
				{"detail": "Google OAuth client ID is not configured."},
				status=status.HTTP_500_INTERNAL_SERVER_ERROR,
			)

		try:
			id_info = google_id_token.verify_oauth2_token(
				token_value,
				google_requests.Request(),
				settings.GOOGLE_OAUTH_CLIENT_ID,
			)
		except ValueError:
			return Response(
				{"detail": "Invalid Google ID token."},
				status=status.HTTP_400_BAD_REQUEST,
			)

		email = id_info.get("email")
		email_verified = id_info.get("email_verified", False)

		if not email or not email_verified:
			return Response(
				{"detail": "Google account email is not verified."},
				status=status.HTTP_400_BAD_REQUEST,
			)

		user = User.objects.filter(email=email).first()

		if not user and not role:
			return Response(
				{"detail": "Role is required for first-time Google login."},
				status=status.HTTP_400_BAD_REQUEST,
			)

		if user and role and user.role != role:
			return Response(
				{"detail": "Role does not match existing account."},
				status=status.HTTP_400_BAD_REQUEST,
			)

		if not user:
			user = User.objects.create_user(
				email=email,
				password=None,
				role=role,
			)
			user.set_unusable_password()
			user.save(update_fields=["password"])

		refresh = RefreshToken.for_user(user)

		return Response(
			{
				"refresh": str(refresh),
				"access": str(refresh.access_token),
				"user": {
					"id": user.id,
					"email": user.email,
					"role": user.role,
				},
			},
			status=status.HTTP_200_OK,
		)

# -------------------------------------------------------
# REGISTER VIEW
# -------------------------------------------------------

class RegisterView(APIView):
    """
    Handles user registration.

    Accepts:
    - email
    - password
    - confirm_password
    - role

    Returns:
    - Success message
    - Basic user info
    """

    permission_classes = [AllowAny]  # Anyone can register

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()

            return Response(
                {
                    "message": "User registered successfully.",
                    "email": user.email,
                    "role": user.role
                },
                status=status.HTTP_201_CREATED
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# -------------------------------------------------------
# LOGIN VIEW (JWT TOKEN GENERATION)
# -------------------------------------------------------

class LoginView(APIView):
    """
    Handles user login.

    Accepts:
    - email
    - password

    If credentials are valid:
    - Generates JWT access and refresh tokens
    - Returns tokens + user role
    """

    permission_classes = [AllowAny]  # Anyone can attempt login

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        # Authenticate user using Django's authentication system
        user = authenticate(request, email=email, password=password)

        if user is not None:

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    "message": "Login successful.",
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                    "email": user.email,
                    "role": user.role
                },
                status=status.HTTP_200_OK
            )

        return Response(
            {"error": "Invalid email or password."},
            status=status.HTTP_401_UNAUTHORIZED
        )