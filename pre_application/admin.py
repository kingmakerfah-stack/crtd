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
        "verified",
    )
    search_fields = ("enquiry_token", "first_name", "last_name", "email")
    actions = ["generate_referral_codes"]

    @admin.action(description="Generate referral code for selected pre-applications")
    def generate_referral_codes(self, request, queryset):
        created_count = 0
        skipped_count = 0

        for pre_application in queryset:
            try:
                create_referral_for_pre_application(pre_application)
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


admin.site.register(ReferalCode)
admin.site.register(EnquiryTokenSequence)
