from django.contrib import admin
from .models import Payment,PaymentHistory
# Register your models here.
admin.site.register(Payment)
@admin.register(PaymentHistory)
class PaymentHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "transaction_id",
        "membership_id",
        "amount",
        "payment_method",
        "payment_status",
        "registration_date",
        "end_date",
    )

    readonly_fields = ("membership_id",)