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
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    is_admin = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} ({self.currency} {self.balance})"