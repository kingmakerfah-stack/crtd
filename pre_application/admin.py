from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import PreApplication,ReferalCode


@admin.register(PreApplication)
class PreApplicationAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'email', 'whatsapp_no', 'verified', 'create_referral_button')
    def create_referral_button(self, obj):
        if  obj.verified:
            return format_html('<span style="color: green;">Verified</span>')
        return format_html(
            '<a class="button" target="_blank" href="/api/pre-application/referral/create/{}/">Generate Referral</a>',
            obj.pk
        )

    create_referral_button.short_description = "Referral"
admin.site.register(ReferalCode)