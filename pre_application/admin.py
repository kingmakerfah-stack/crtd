from django.contrib import admin
from django.contrib import messages

from .models import EnquiryTokenSequence, PreApplication, ReferalCode
from .services import ReferralGenerationError, create_referral_for_pre_application



@admin.register(PreApplication)
class PreApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "enquiry_token",
        "first_name",
        "last_name",
        "email",
        "whatsapp_no",
        "status",
        "verified",
        "is_deleted",
        "deleted_at",
        "deleted_by",
    )
    list_filter = ("is_deleted", "status", "verified", "deleted_at")
    search_fields = ("enquiry_token", "first_name", "last_name", "email")
    actions = ["generate_referral_codes"]

    def get_queryset(self, request):
        # Show active + soft-deleted rows for audit and manual restore workflows.
        return PreApplication.all_objects.select_related("deleted_by")

    @admin.action(description="Generate referral code for selected pre-applications")
    def generate_referral_codes(self, request, queryset):
        created_count = 0
        skipped_count = 0

        for pre_application in queryset:
            try:
                create_referral_for_pre_application(pre_application, created_by=request.user)
                created_count += 1
            except ReferralGenerationError:
                skipped_count += 1

        if created_count:
            self.message_user(
                request,
                f"Created referral codes for {created_count} pre-application(s).",
            )
        if skipped_count:
            self.message_user(
                request,
                f"Skipped {skipped_count} pre-application(s) that already had a referral.",
                level=messages.WARNING,
            )

@admin.register(ReferalCode)
class ReferalCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "student", "status", "is_used", "created_by_email", "created_at")
    list_filter = ("status", "is_used", "created_at")
    search_fields = ("code", "student__enquiry_token", "student__email", "admin__email")

    @admin.display(description="Created By")
    def created_by_email(self, obj):
        return obj.admin.email if obj.admin else "-"


admin.site.register(EnquiryTokenSequence)
