from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    """
    Allows access only to users with role = 'admin'.
    This is used for admin-specific APIs.
    """

    def has_permission(self, request, view):
        # Ensure user is authenticated first
        if not request.user or not request.user.is_authenticated:
            return False

        return request.user.role == 'admin'


class IsStudent(BasePermission):
    """
    Allows access only to users with role = 'student'.
    This will be used for student-only APIs.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        return request.user.role == 'student'