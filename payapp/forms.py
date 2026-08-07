from decimal import Decimal

from django import forms
from django.contrib.auth.models import User


class _CounterpartyEmailForm(forms.Form):
    """Shared validation for the two forms that address another user by email."""

    #: Guards against a request that would round to nothing after conversion.
    MIN_AMOUNT = Decimal('0.01')

    amount = forms.DecimalField(
        max_digits=12, decimal_places=2, min_value=MIN_AMOUNT
    )

    def _clean_counterparty_email(self, field):
        # Matched case-insensitively so that the lookup here and the one in the
        # view agree; addresses are not case-sensitive in practice.
        email = self.cleaned_data[field]
        if not User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('No user found with this email.')
        return email


class SendPaymentForm(_CounterpartyEmailForm):
    receiver_email = forms.EmailField(label='Recipient Email')

    field_order = ['receiver_email', 'amount']

    def clean_receiver_email(self):
        return self._clean_counterparty_email('receiver_email')


class RequestPaymentForm(_CounterpartyEmailForm):
    requestee_email = forms.EmailField(label='Request From (Email)')

    field_order = ['requestee_email', 'amount']

    def clean_requestee_email(self):
        return self._clean_counterparty_email('requestee_email')
