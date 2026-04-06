from django.core.management.base import BaseCommand

from accounts.models import Module


MODULES = [
    ('dashboard', 'Dashboard', 1),
    ('web_update', 'Web Update', 2),
    ('enquiry_form', 'Enquiry Form', 3),
    ('reference_code', 'Reference Code', 4),
    ('sub_admin', 'Sub Admin', 5),
    ('total_user_status', 'Total User Status', 6),
    ('analytics', 'Analytics', 7),
    ('payment', 'Payment', 8),
    ('job_applications', 'Job Applications', 9),
    ('membership', 'Membership', 10),
    ('employee_status', 'Employee Status', 11),
    ('sales', 'Sales', 12),
]


class Command(BaseCommand):
    help = 'Seed all sidebar modules into the database'

    def handle(self, *args, **kwargs):
        created_count = 0
        for name, display_name, order in MODULES:
            _, created = Module.objects.get_or_create(
                name=name,
                defaults={'display_name': display_name, 'order': order},
            )
            if created:
                created_count += 1
                self.stdout.write(f'Created: {display_name}')
            else:
                self.stdout.write(f'Exists: {display_name}')

        self.stdout.write(self.style.SUCCESS(f'Done. {created_count} new modules created.'))
