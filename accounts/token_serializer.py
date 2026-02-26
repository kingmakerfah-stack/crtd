from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom serializer to:
    - Allow login using email
    - Add extra data (email + role) inside JWT token
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Add custom fields to token payload
        token['email'] = user.email
        token['role'] = user.role

        return token


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom view that uses our custom serializer.
    """
    serializer_class = CustomTokenObtainPairSerializer