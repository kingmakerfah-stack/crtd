from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework.exceptions import AuthenticationFailed

from .utils import is_user_invalidated


class SessionAwareJWTAuthentication(JWTAuthentication):
    """JWT auth with Redis-backed session invalidation checks."""

    def get_raw_token(self, header):
        """Accept standard Bearer token and fallback to single-part token headers."""
        if not header:
            return None

        try:
            raw_token = super().get_raw_token(header)
        except AuthenticationFailed:
            raw_token = None

        if raw_token is not None:
            return raw_token

        parts = header.split()
        if len(parts) == 1:
            return parts[0]
        return None

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if is_user_invalidated(user.pk):
            raise InvalidToken('Session invalidated. Please log in again.')
        return user
