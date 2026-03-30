from django.contrib import admin

from .models import SubscriptionPlan


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'price', 'duration_months', 'discount_percent', 'is_active', 'updated_at')
    search_fields = ('name', 'description')
    list_filter = (['is_active'])