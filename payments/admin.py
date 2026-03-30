from django.contrib import admin
from .models import Payment,PaymentHistory
# Register your models here.
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display=(
        'user',
        'plan',
        'status',
    )




@admin.register(PaymentHistory)
class PaymentHistoryAdmin(admin.ModelAdmin):

    list_display = (
        "transaction_id",
        "user",
        "registration_date",
        "amount",
        "end_date",
        "payment_status",
        "payment_method",
        "payment_details",
        "membership_id",
    )

    list_filter = (
        "payment_status",
        "payment_method",
        "registration_date",
    )

    search_fields = (
        "transaction_id",
        "user__username",
        "user__email",
        "membership_id",
    )

    ordering = ("-registration_date",)

    readonly_fields = (
        "transaction_id",
        "membership_id",
        "registration_date",
    )