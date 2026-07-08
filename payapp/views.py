import requests
import urllib3
from decimal import Decimal

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from payapp.forms import SendPaymentForm, RequestPaymentForm
from payapp.models import Transaction, PaymentRequest, Notification
from register.models import UserProfile


def _convert_currency(from_currency, to_currency, amount):
    """Call REST conversion service. Falls back to hard-coded rates."""
    if from_currency == to_currency:
        return Decimal(str(amount))
    try:
        url = f"{settings.CONVERSION_SERVICE_URL}/{from_currency}/{to_currency}/{amount}"
        resp = requests.get(url, timeout=3, verify=False)
        if resp.status_code == 200:
            data = resp.json()
            return Decimal(str(data['converted_amount']))
    except Exception:
        pass
    # Hard-coded fallback rates
    rates = {
        ('GBP', 'USD'): Decimal('1.27'),
        ('GBP', 'EUR'): Decimal('1.17'),
        ('USD', 'GBP'): Decimal('0.79'),
        ('USD', 'EUR'): Decimal('0.92'),
        ('EUR', 'GBP'): Decimal('0.85'),
        ('EUR', 'USD'): Decimal('1.08'),
    }
    rate = rates.get((from_currency, to_currency), Decimal('1'))
    return (Decimal(str(amount)) * rate).quantize(Decimal('0.01'))


@login_required
def dashboard_view(request):
    if request.user.profile.is_admin:
        return redirect('admin_dashboard')
    recent_transactions = list(
        Transaction.objects.filter(sender=request.user).order_by('-timestamp')[:3]
    ) + list(
        Transaction.objects.filter(receiver=request.user).order_by('-timestamp')[:3]
    )
    recent_transactions = sorted(recent_transactions, key=lambda x: x.timestamp, reverse=True)[:5]

    sent_count = Transaction.objects.filter(sender=request.user).count()
    received_count = Transaction.objects.filter(receiver=request.user).count()
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()

    return render(request, 'payapp/dashboard.html', {
        'profile': request.user.profile,
        'recent_transactions': recent_transactions,
        'unread_notifications': unread_count,
        'unread_count': unread_count,
        'sent_count': sent_count,
        'received_count': received_count,
    })


@login_required
def send_payment_view(request):
    if request.user.profile.is_admin:
        return redirect('admin_dashboard')
    form = SendPaymentForm(request.POST or None)
    error = None
    if request.method == 'POST' and form.is_valid():
        cd = form.cleaned_data
        try:
            receiver = User.objects.get(email=cd['receiver_email'])
        except User.DoesNotExist:
            error = 'No account found with that email address. Please check and try again.'
            return render(request, 'payapp/send_payment.html', {'form': form, 'error': error})

        if receiver == request.user:
            error = 'You cannot send money to yourself.'
        else:
            sender_profile = request.user.profile
            receiver_profile = receiver.profile
            send_amount = Decimal(str(cd['amount']))

            if sender_profile.balance < send_amount:
                error = 'Insufficient funds.'
            else:
                converted = _convert_currency(
                    sender_profile.currency,
                    receiver_profile.currency,
                    send_amount
                )
                try:
                    with transaction.atomic():
                        sender_profile.balance -= send_amount
                        sender_profile.save()
                        receiver_profile.balance += converted
                        receiver_profile.save()
                        Transaction.objects.create(
                            sender=request.user,
                            receiver=receiver,
                            amount=send_amount,
                            sender_currency=sender_profile.currency,
                            receiver_currency=receiver_profile.currency,
                            converted_amount=converted,
                        )
                        Notification.objects.create(
                            user=receiver,
                            message=f"{request.user.get_full_name()} sent you "
                                    f"{converted} {receiver_profile.currency}.",
                        )
                        Notification.objects.create(
                            user=request.user,
                            message=f"You sent {send_amount} {sender_profile.currency} "
                                    f"to {receiver.get_full_name()}.",
                        )
                    return redirect('transactions')
                except Exception:
                    error = 'Transaction failed. Please try again.'

    return render(request, 'payapp/send_payment.html', {'form': form, 'error': error})


@login_required
def request_payment_view(request):
    if request.user.profile.is_admin:
        return redirect('admin_dashboard')
    form = RequestPaymentForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        cd = form.cleaned_data
        try:
            requestee = User.objects.get(email=cd['requestee_email'])
        except User.DoesNotExist:
            error = 'No account found with that email address. Please check and try again.'
            return render(request, 'payapp/request_payment.html', {'form': form, 'error': error})
        PaymentRequest.objects.create(
            requester=request.user,
            requestee=requestee,
            amount=cd['amount'],
            currency=request.user.profile.currency,
        )
        Notification.objects.create(
            user=requestee,
            message=f"{request.user.get_full_name()} requested "
                    f"{cd['amount']} {request.user.profile.currency} from you.",
        )
        return redirect('transactions')
    return render(request, 'payapp/request_payment.html', {'form': form})


@login_required
def transactions_view(request):
    if request.user.profile.is_admin:
        return redirect('admin_dashboard')
    sent = Transaction.objects.filter(sender=request.user).order_by('-timestamp')
    received = Transaction.objects.filter(receiver=request.user).order_by('-timestamp')
    payment_requests_sent = PaymentRequest.objects.filter(
        requester=request.user).order_by('-timestamp')
    payment_requests_received = PaymentRequest.objects.filter(
        requestee=request.user).order_by('-timestamp')
    return render(request, 'payapp/transactions.html', {
        'sent': sent,
        'received': received,
        'payment_requests_sent': payment_requests_sent,
        'payment_requests_received': payment_requests_received,
    })


@login_required
def notifications_view(request):
    if request.user.profile.is_admin:
        return redirect('admin_dashboard')
    
    # SHOW ALL NOTIFICATIONS (read + unread both)
    # Jab mark as read click karega to notification read ho jayegi
    # Lekin list mein dikhti rahegi (with normal white background)
    notifications = Notification.objects.filter(
        user=request.user
    ).order_by('-timestamp')
    
    # Count unread notifications for badge
    unread_count = notifications.filter(is_read=False).count()
    
    return render(request, 'payapp/notifications.html', {
        'notifications': notifications,
        'unread_count': unread_count
    })


# ========== Notification Mark as Read Views ==========

@login_required
@require_POST
def mark_notification_read(request, pk):
    """Mark a single notification as read via AJAX"""
    try:
        notification = Notification.objects.get(pk=pk, user=request.user)
        if not notification.is_read:
            notification.is_read = True
            notification.save()
            return JsonResponse({
                'status': 'success', 
                'message': 'Notification marked as read'
            })
        return JsonResponse({
            'status': 'success', 
            'message': 'Notification already read'
        })
    except Notification.DoesNotExist:
        return JsonResponse({
            'status': 'error', 
            'message': 'Notification not found'
        }, status=404)


@login_required
@require_POST
def mark_all_notifications_read(request):
    """Mark all notifications as read for the current user via AJAX"""
    try:
        updated_count = Notification.objects.filter(
            user=request.user, 
            is_read=False
        ).update(is_read=True)
        
        # Agar 0 notifications mark hui hain, toh bhi success return karo with message
        if updated_count == 0:
            return JsonResponse({
                'status': 'success', 
                'message': 'No unread notifications found! All notifications are already read.',
                'updated_count': 0
            })
        
        return JsonResponse({
            'status': 'success', 
            'message': f'{updated_count} notification(s) marked as read',
            'updated_count': updated_count
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error', 
            'message': str(e)
        }, status=500)


# ========== END NOTIFICATION VIEWS ==========


@login_required
def handle_payment_request_view(request, pk):
    """Accept or reject an incoming payment request."""
    if request.user.profile.is_admin:
        return redirect('admin_dashboard')
    pay_request = get_object_or_404(
        PaymentRequest, pk=pk, requestee=request.user, status='PENDING'
    )
    action = request.POST.get('action')

    if action == 'reject':
        pay_request.status = 'REJECTED'
        pay_request.save()
        Notification.objects.create(
            user=pay_request.requester,
            message=f"{request.user.get_full_name()} rejected your payment request of "
                    f"{pay_request.amount} {pay_request.currency}.",
        )
        return redirect('transactions')

    if action == 'accept':
        sender_profile = request.user.profile
        receiver_profile = pay_request.requester.profile
        amount = pay_request.amount

        converted = _convert_currency(
            pay_request.currency,
            sender_profile.currency,
            amount
        )

        if sender_profile.balance < converted:
            return render(request, 'payapp/transactions.html', {
                'error': 'Insufficient funds to accept this request.'
            })

        try:
            with transaction.atomic():
                sender_profile.balance -= converted
                sender_profile.save()
                receiver_profile.balance += amount
                receiver_profile.save()
                pay_request.status = 'ACCEPTED'
                pay_request.save()
                Transaction.objects.create(
                    sender=request.user,
                    receiver=pay_request.requester,
                    amount=converted,
                    sender_currency=sender_profile.currency,
                    receiver_currency=pay_request.currency,
                    converted_amount=amount,
                )
                Notification.objects.create(
                    user=pay_request.requester,
                    message=f"{request.user.get_full_name()} accepted your request and sent "
                            f"{amount} {pay_request.currency}.",
                )
        except Exception:
            pass

    return redirect('transactions')


# ── Admin views ──────────────────────────────────────────────────────────────

@login_required
def admin_dashboard_view(request):
    if not request.user.profile.is_admin:
        return redirect('dashboard')
    from register.models import UserProfile
    users = UserProfile.objects.select_related('user').filter(is_admin=False)
    total_transactions = Transaction.objects.count()
    admin_count = UserProfile.objects.filter(is_admin=True).count()
    return render(request, 'admin/dashboard.html', {
        'users': users,
        'total_transactions': total_transactions,
        'admin_count': admin_count,
    })

@login_required
def admin_transactions_view(request):
    if not request.user.profile.is_admin:
        return redirect('dashboard')
    all_transactions = Transaction.objects.select_related(
        'sender', 'receiver').order_by('-timestamp')
    return render(request, 'admin/transactions.html', {
        'transactions': all_transactions
    })


@login_required
def admin_users_view(request):
    if not request.user.profile.is_admin:
        return redirect('dashboard')
    from register.models import UserProfile
    users = UserProfile.objects.select_related('user').all()
    return render(request, 'admin/users.html', {'users': users})