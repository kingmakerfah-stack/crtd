from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Module, SubAdminProfile


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser

    list_display = ('email', 'role', 'email_verified', 'is_staff', 'is_active')
    ordering = ('email',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('name',)}),
        ('Role', {'fields': ('role',)}),
        ('Verification', {'fields': ('email_verified',)}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email',
                'role',
                'email_verified',   # 👈 added here
                'password1',
                'password2',
                'is_staff',
                'is_superuser'
            ),
        }),
    )

    search_fields = ('email', 'name')


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_name', 'order', 'is_active')
    list_filter = ('is_active',)
    ordering = ('order',)
    search_fields = ('name', 'display_name')


@admin.register(SubAdminProfile)
class SubAdminProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_by', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('user__email', 'created_by__email')
    filter_horizontal = ('allowed_modules',)