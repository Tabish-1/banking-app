from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError


class BaseAccountForm(forms.Form):
    """Fields and validation shared by the member and admin sign-up forms.

    Both forms create accounts with `User.objects.create_user()`, which does not
    apply AUTH_PASSWORD_VALIDATORS — Django only runs those from its own
    UserCreationForm. Password strength is therefore enforced here, otherwise
    the validators configured in settings would have no effect at all.
    """

    username = forms.CharField(max_length=150)
    first_name = forms.CharField(max_length=50)
    last_name = forms.CharField(max_length=50)
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)
    password_confirm = forms.CharField(
        widget=forms.PasswordInput, label='Confirm password'
    )

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('Username already taken.')
        return username

    def clean_email(self):
        # Compared case-insensitively and enforced on every sign-up path:
        # Django does not make User.email unique, but the payment views look
        # recipients up by email, so a duplicate would make them ambiguous.
        email = self.cleaned_data['email']
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm = cleaned_data.get('password_confirm')

        if password and confirm and password != confirm:
            self.add_error('password_confirm', 'Passwords do not match.')
            return cleaned_data

        if password:
            # Pass an unsaved User so UserAttributeSimilarityValidator can
            # compare the password against the name/email being registered.
            candidate = User(
                username=cleaned_data.get('username') or '',
                first_name=cleaned_data.get('first_name') or '',
                last_name=cleaned_data.get('last_name') or '',
                email=cleaned_data.get('email') or '',
            )
            try:
                validate_password(password, user=candidate)
            except DjangoValidationError as exc:
                self.add_error('password', exc)

        return cleaned_data


class UserRegistrationForm(BaseAccountForm):

    CURRENCY_CHOICES = [
        ('GBP', 'GB Pounds (£)'),
        ('USD', 'US Dollars ($)'),
        ('EUR', 'Euros (€)'),
    ]

    currency = forms.ChoiceField(choices=CURRENCY_CHOICES)


class AdminRegistrationForm(BaseAccountForm):
    """Admin accounts hold no balance, so there is no currency to choose."""


class LoginForm(AuthenticationForm):
    pass
