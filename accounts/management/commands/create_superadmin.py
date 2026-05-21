import getpass

from django.core.management.base import BaseCommand

from accounts.models import CustomUser


class Command(BaseCommand):
    help = 'Create a SuperAdmin user for the admin portal'

    def handle(self, *args, **kwargs):
        self.stdout.write('--- Create SuperAdmin ---')

        email = input('Email: ').strip()
        name = input('Name: ').strip()

        if CustomUser.objects.filter(email=email).exists():
            self.stdout.write(self.style.ERROR(f'User {email} already exists.'))
            return

        password = getpass.getpass('Password: ')
        confirm = getpass.getpass('Confirm Password: ')

        if password != confirm:
            self.stdout.write(self.style.ERROR('Passwords do not match.'))
            return

        user = CustomUser.objects.create_superuser(
            email=email,
            password=password,
            role='superadmin',
            name=name,
        )

        self.stdout.write(self.style.SUCCESS(f'SuperAdmin {user.email} created successfully.'))
