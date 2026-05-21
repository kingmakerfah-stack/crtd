from django.db import migrations


def forward_copy_testimonials(apps, schema_editor):
    AdminTestimonial = apps.get_model("admin_analytics", "Testimonial")
    JobTestimonial = apps.get_model("jobs", "Testimonial")

    for old in AdminTestimonial.objects.all().iterator():
        old_status = (old.status or "").strip().lower()
        if old_status == "active":
            mapped_status = "published"
        else:
            mapped_status = "draft"

        JobTestimonial.objects.update_or_create(
            id=old.id,
            defaults={
                "name": old.name,
                "profile": old.qualification or "N/A",
                "feedback": old.feedback,
                "rating": "5 Star",
                "status": mapped_status,
                "created_at": old.created_at,
                "updated_at": old.updated_at,
            },
        )


def backward_copy_testimonials(apps, schema_editor):
    JobTestimonial = apps.get_model("jobs", "Testimonial")
    AdminTestimonial = apps.get_model("admin_analytics", "Testimonial")

    for new in JobTestimonial.objects.all().iterator():
        new_status = (new.status or "").strip().lower()
        if new_status == "published":
            mapped_status = "active"
        else:
            mapped_status = "inactive"

        AdminTestimonial.objects.update_or_create(
            id=new.id,
            defaults={
                "name": new.name,
                "qualification": new.profile,
                "feedback": new.feedback,
                "status": mapped_status,
                "created_at": new.created_at,
                "updated_at": new.updated_at,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0003_testimonial"),
        ("admin_analytics", "0005_alter_enquiryanalytics_enquiry_token"),
    ]

    operations = [
        migrations.RunPython(forward_copy_testimonials, backward_copy_testimonials),
    ]
