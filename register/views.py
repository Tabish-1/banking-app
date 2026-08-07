from decimal import Decimal

from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from conversionservice.client import convert
from register.forms import AdminRegistrationForm, LoginForm, UserRegistrationForm
from register.models import UserProfile, get_or_create_profile


def _initial_balance(currency):
    """New members start with the configured amount, held in their own currency."""
    return convert('GBP', currency, Decimal(str(settings.INITIAL_BALANCE_GBP)))


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    form = UserRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        cd = form.cleaned_data

        # Resolved before opening the transaction: this makes a blocking HTTP
        # call to the conversion service and must not run inside atomic().
        balance = _initial_balance(cd['currency'])

        with transaction.atomic():
            user = User.objects.create_user(
                username=cd['username'],
                password=cd['password'],
                first_name=cd['first_name'],
                last_name=cd['last_name'],
                email=cd['email'],
            )
            UserProfile.objects.create(
                user=user,
                currency=cd['currency'],
                balance=balance,
                is_admin=False,
            )

        login(request, user)
        return redirect('dashboard')

    return render(request, 'register/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        login(request, user)
        if get_or_create_profile(user).is_admin:
            return redirect('admin_dashboard')
        return redirect('dashboard')

    return render(request, 'register/login.html', {'form': form})


@login_required
@require_POST
def logout_view(request):
    """Sign out. POST-only, so a third-party page cannot force a logout.

    Django's own LogoutView has required POST since 4.1 for the same reason.
    """
    logout(request)
    return redirect('login')


@login_required
def admin_register_view(request):
    if not get_or_create_profile(request.user).is_admin:
        return redirect('dashboard')

    form = AdminRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        cd = form.cleaned_data
        with transaction.atomic():
            user = User.objects.create_user(
                username=cd['username'],
                password=cd['password'],
                first_name=cd['first_name'],
                last_name=cd['last_name'],
                email=cd['email'],
            )
            UserProfile.objects.create(
                user=user,
                currency='GBP',
                balance=Decimal('0.00'),
                is_admin=True,
            )
        return redirect('admin_dashboard')

    return render(request, 'admin/register_admin.html', {'form': form})
