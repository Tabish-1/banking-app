"""Create an administrator account for the banking app.

This replaces a post_migrate signal that used to create a hard-coded
`admin1` / `admin1` account on every `migrate`. Fixed credentials in source mean
every clone of this repository ships with the same known admin login, so
creating one is now an explicit, operator-driven step.

The password is never taken as a command-line argument, which would leave it in
shell history and in the process list. It is read from the DJANGO_ADMIN_PASSWORD
environment variable, or prompted for interactively.
"""

import getpass
import os

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from register.models import UserProfile

PASSWORD_ENV_VAR = 'DJANGO_ADMIN_PASSWORD'


class Command(BaseCommand):
    help = 'Create an administrator account for the banking app.'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)
        parser.add_argument('--email', required=True)
        parser.add_argument('--first-name', default='Admin')
        parser.add_argument('--last-name', default='User')
        parser.add_argument(
            '--noinput',
            action='store_true',
            help=f'Never prompt; require the password in ${PASSWORD_ENV_VAR}.',
        )

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']

        if User.objects.filter(username__iexact=username).exists():
            raise CommandError(f'A user named {username!r} already exists.')
        if User.objects.filter(email__iexact=email).exists():
            raise CommandError(f'A user with the email {email!r} already exists.')

        password = self._get_password(noinput=options['noinput'], username=username, email=email)

        with transaction.atomic():
            admin_user = User.objects.create_user(
                username=username,
                password=password,
                first_name=options['first_name'],
                last_name=options['last_name'],
                email=email,
            )
            UserProfile.objects.create(
                user=admin_user,
                currency='GBP',
                balance=0,
                is_admin=True,
            )

        self.stdout.write(self.style.SUCCESS(f'Created administrator {username!r}.'))

    def _get_password(self, *, noinput, username, email):
        password = os.environ.get(PASSWORD_ENV_VAR)

        if password:
            self._validate(password, username=username, email=email)
            return password

        if noinput:
            raise CommandError(
                f'--noinput was given but ${PASSWORD_ENV_VAR} is not set.'
            )

        for _ in range(3):
            password = getpass.getpass('Password: ')
            if password != getpass.getpass('Password (again): '):
                self.stderr.write(self.style.ERROR('Passwords do not match. Try again.'))
                continue
            try:
                self._validate(password, username=username, email=email)
            except CommandError as exc:
                self.stderr.write(self.style.ERROR(str(exc)))
                continue
            return password

        raise CommandError('Too many failed attempts.')

    @staticmethod
    def _validate(password, *, username, email):
        # Pass an unsaved User so the similarity validator has something to
        # compare against, matching what the sign-up forms do.
        candidate = User(username=username, email=email)
        try:
            validate_password(password, user=candidate)
        except ValidationError as exc:
            raise CommandError('\n'.join(exc.messages)) from exc
