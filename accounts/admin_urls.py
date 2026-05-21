from django.urls import path

from .views import (
    RBACAdminLoginView,
    RBACAdminOTPVerifyView,
    RBACMeView,
    CreateSubAdminView,
    SubAdminDetailView,
    ListSubAdminsView,
    UpdateSubAdminAccessView,
    UpdateSubAdminRoleView,
    ToggleSubAdminStatusView,
    DeleteSubAdminView,
    ModuleListView,
)

urlpatterns = [
    path('auth/login/', RBACAdminLoginView.as_view(), name='rbac-admin-login'),
    path('auth/verify-otp/', RBACAdminOTPVerifyView.as_view(), name='rbac-admin-otp-verify'),
    path('auth/me/', RBACMeView.as_view(), name='rbac-admin-me'),
    path('subadmin/create/', CreateSubAdminView.as_view(), name='rbac-subadmin-create'),
    path('subadmin/list/', ListSubAdminsView.as_view(), name='rbac-subadmin-list'),
    path('subadmin/<int:user_id>/', SubAdminDetailView.as_view(), name='rbac-subadmin-detail'),
    path('subadmin/<int:user_id>/access/', UpdateSubAdminAccessView.as_view(), name='rbac-subadmin-update-access'),
    path('subadmin/<int:user_id>/role/', UpdateSubAdminRoleView.as_view(), name='rbac-subadmin-update-role'),
    path('subadmin/<int:user_id>/toggle/', ToggleSubAdminStatusView.as_view(), name='rbac-subadmin-toggle'),
    path('subadmin/<int:user_id>/delete/', DeleteSubAdminView.as_view(), name='rbac-subadmin-delete'),
    path('modules/', ModuleListView.as_view(), name='rbac-module-list'),
]
