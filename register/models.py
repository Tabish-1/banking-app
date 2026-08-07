from decimal import Decimal

from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):

    CURRENCY_CHOICES = [
        ('GBP', 'GB Pounds (£)'),
        ('USD', 'US Dollars ($)'),
        ('EUR', 'Euros (€)'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='GBP')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    is_admin = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} ({self.currency} {self.balance})"


def get_or_create_profile(user):
    """Return the user's profile, creating a default one if it is missing.

    Accounts created outside the sign-up flow — `createsuperuser`, a fixture, a
    data import — have no UserProfile, and every view in this project reads
    `user.profile.is_admin`. Without this, those accounts raise
    RelatedObjectDoesNotExist and return a 500 on every page.
    """
    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={
            'currency': 'GBP',
            'balance': Decimal('0.00'),
            # A Django superuser operates this system, so give them the in-app
            # admin view rather than a member account holding money.
            'is_admin': user.is_superuser,
        },
    )
    return profile
