"""
Management command to test the EmailService with sample data.

Usage:
    python manage.py test_email_service [--email your-email@example.com]
"""

from django.core.management.base import BaseCommand
from utils.email_service import EmailService


class Command(BaseCommand):
    help = "Test the EmailService by sending a sample approval email"

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            default='test@example.com',
            help='Email address to send the test email to (default: test@example.com)'
        )
        parser.add_argument(
            '--firstname',
            type=str,
            default='Test User',
            help='First name for the email template (default: Test User)'
        )
        parser.add_argument(
            '--refcode',
            type=str,
            default='CRTD-2026-12345',
            help='Reference code for the email template (default: CRTD-2026-12345)'
        )

    def handle(self, *args, **options):
        email = options['email']
        first_name = options['firstname']
        ref_code = options['refcode']

        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("Testing EmailService"))
        self.stdout.write(self.style.SUCCESS("=" * 60))

        self.stdout.write(f"\n📧 Sending approval email to: {email}")
        self.stdout.write(f"👤 Student Name: {first_name}")
        self.stdout.write(f"🔑 Reference Code: {ref_code}\n")

        try:
            context = {
                'first_name': first_name,
                'reference_code': ref_code
            }

            # Send the email asynchronously
            EmailService.send_approval_email(email, context)

            self.stdout.write(self.style.SUCCESS("✓ Email sent successfully!"))
            self.stdout.write(
                self.style.WARNING(
                    "\n⚠️  Note: With EMAIL_BACKEND='console.EmailBackend',\n"
                    "   the email will be printed to console/logs instead of being sent.\n"
                    "   Check your console output for the email content."
                )
            )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Error sending email: {str(e)}"))

        self.stdout.write(self.style.SUCCESS("\n" + "=" * 60))
        self.stdout.write(self.style.SUCCESS("Test completed!"))
        self.stdout.write(self.style.SUCCESS("=" * 60 + "\n"))
