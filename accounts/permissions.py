from rest_framework.permissions import BasePermission
from .models import SubAdminProfile
from payments.models import StudentSubscription
from datetime import date


class IsAdmin(BasePermission):
    """
    Allows access only to users with role = 'admin'.
    """

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role == 'admin'
        )


class IsStudent(BasePermission):
    """
    Allows access only to users with role = 'student'.
    """

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role == 'student'
        )


class IsSuperAdmin(BasePermission):
    message = 'SuperAdmin access required.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == 'superadmin'
        )


class IsAdminPortalUser(BasePermission):
    message = 'Admin portal access required.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in ('superadmin', 'subadmin', 'sales')
        )


class IsSalesUser(BasePermission):
    message = 'Sales access required.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == 'sales'
        )


class HasModuleAccess(BasePermission):
    message = 'You do not have access to this module.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.role == 'superadmin':
            return True

        if request.user.role in ('subadmin', 'sales'):
            required_module = getattr(view, 'required_module', None)
            if not required_module:
                return True
            try:
                return request.user.subadmin_profile.has_module_access(required_module)
            except SubAdminProfile.DoesNotExist:
                return False

        return False


class CanManageSubadmins(BasePermission):
    message = 'You do not have permission to manage subadmins.'

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if user.role == 'superadmin':
            return True

        if user.role != 'subadmin':
            return False

        try:
            return user.subadmin_profile.has_module_access('sub_admin')
        except SubAdminProfile.DoesNotExist:
            return False


# create a permission class for the  active subscriber to check the active subscription status whether it is expired or the active
class IsActiveSubscriber(BasePermission):
    def has_permission(self, request, view):
        try:
            sub = StudentSubscription.objects.get(student=request.user)

            if sub.expiry_date < date.today():
                sub.status = "EXPIRED"
                sub.save()
                return False

            return sub.status == "ACTIVE"

        except:
            return False