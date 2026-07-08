from django import forms
from django.contrib.auth.models import User


class SendPaymentForm(forms.Form):
    receiver_email = forms.EmailField(label='Recipient Email')
    amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0.01)

    def clean_receiver_email(self):
        email = self.cleaned_data['receiver_email']
        if not User.objects.filter(email=email).exists():
            raise forms.ValidationError('No user found with this email.')
        return email


class RequestPaymentForm(forms.Form):
    requestee_email = forms.EmailField(label='Request From (Email)')
    amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0.01)

    def clean_requestee_email(self):
        email = self.cleaned_data['requestee_email']
        if not User.objects.filter(email=email).exists():
            raise forms.ValidationError('No user found with this email.')
        return email