from django.conf import settings
from django.contrib.auth import get_user_model
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

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
