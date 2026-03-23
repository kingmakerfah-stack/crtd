from rest_framework.permissions import BasePermission


class IsSuperuserOrAdminOrSubadmin(BasePermission):
    """Allow access to superuser, admin/subadmin roles, and staff users."""

    message = "You do not have permission to perform this action."

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        if getattr(user, "is_superuser", False):
            return True

        if getattr(user, "is_staff", False):
            return True

        return getattr(user, "role", None) in {"admin", "subadmin"}
