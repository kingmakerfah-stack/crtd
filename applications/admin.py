
from django.contrib import admin
from .models import Application,CoolDown

admin.site.register(CoolDown)

@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'student_name',
        'student_email',
        'contact_number',
        'job_role',
        'experience',
        'skills',
        'status',
        'applied_at',
        'cooldown_days_used',
        'reason'
    )

    list_filter = (
        'status',
        'applied_at',
        'job'
    )

    search_fields = (
        'student__user__email',
        'student__personal_detail__first_name',
        'job__job_role'
    )

    ordering = ('-applied_at',)

    list_editable = ('status',)

    readonly_fields = ('reference_id', 'applied_at')

    # =========================

    def student_name(self, obj):
        try:
            personal = obj.student.personal_detail
            return f"{personal.first_name} {personal.last_name}"
        except:
            return "-"
    student_name.short_description = "Name"

    def student_email(self, obj):
        return obj.student.user.email
    student_email.short_description = "Email"

    def contact_number(self, obj):
        try:
            return obj.student.personal_detail.whatsapp_no
        except:
            return "-"
    contact_number.short_description = "Contact"

    def job_role(self, obj):
        return obj.job.job_role if obj.job else "-"
    job_role.short_description = "Job Role"

    def experience(self, obj):
        try:
            return obj.student.career_preference.experience
        except:
            return "-"
    experience.short_description = "Experience"

    def skills(self, obj):
        try:
            skills = obj.student.education.skills
            return ", ".join(skills) if skills else "-"
        except:
            return "-"
    skills.short_description = "Skills"