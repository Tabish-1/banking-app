import requests
import urllib3
from decimal import Decimal

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.conf import settings

from register.forms import UserRegistrationForm, LoginForm, AdminRegistrationForm
from register.models import UserProfile


def _get_initial_balance(currency):
    base_gbp = Decimal(str(settings.INITIAL_BALANCE_GBP))
    if currency == 'GBP':
        return base_gbp
    try:
        url = f"{settings.CONVERSION_SERVICE_URL}/GBP/{currency}/{base_gbp}"
        resp = requests.get(url, timeout=3, verify=False)
        if resp.status_code == 200:
            data = resp.json()
            return Decimal(str(data['converted_amount']))
    except Exception:
        pass
    fallback_rates = {'USD': Decimal('1.27'), 'EUR': Decimal('1.17')}
    return (base_gbp * fallback_rates.get(currency, Decimal('1'))).quantize(Decimal('0.01'))


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = UserRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        cd = form.cleaned_data
        user = User.objects.create_user(
            username=cd['username'],
            password=cd['password'],
            first_name=cd['first_name'],
            last_name=cd['last_name'],
            email=cd['email'],
        )
        balance = _get_initial_balance(cd['currency'])
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
        if hasattr(user, 'profile') and user.profile.is_admin:
            return redirect('admin_dashboard')
        return redirect('dashboard')
    return render(request, 'register/login.html', {'form': form})


@login_required
def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def admin_register_view(request):
    if not request.user.profile.is_admin:
        return redirect('dashboard')
    form = AdminRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        cd = form.cleaned_data
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