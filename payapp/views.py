import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import DatabaseError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from conversionservice.client import convert
from payapp.forms import RequestPaymentForm, SendPaymentForm
from payapp.models import Notification, PaymentRequest, Transaction
from register.models import UserProfile, get_or_create_profile

logger = logging.getLogger(__name__)


class InsufficientFunds(Exception):
    """The payer's balance did not cover the debit at commit time."""


class RequestAlreadySettled(Exception):
    """The payment request was accepted or rejected by a concurrent submit."""


def _transactions_context(user):
    """Everything the transactions page renders, for reuse on error paths."""
    return {
        'sent': Transaction.objects.filter(sender=user)
            .select_related('receiver').order_by('-timestamp'),
        'received': Transaction.objects.filter(receiver=user)
            .select_related('sender').order_by('-timestamp'),
        'payment_requests_sent': PaymentRequest.objects.filter(requester=user)
            .select_related('requestee').order_by('-timestamp'),
        'payment_requests_received': PaymentRequest.objects.filter(requestee=user)
            .select_related('requester').order_by('-timestamp'),
    }


def _lock_profiles(*profile_pks):
    """Re-read the given profiles inside the current transaction, under a lock.

    Checking a balance against a copy loaded earlier in the request is a
    time-of-check / time-of-use race: two concurrent transfers can each see
    sufficient funds and both commit, overdrawing the account. Re-reading here
    makes the check and the debit part of the same locked read-modify-write.

    All rows are locked in a single query so that two transfers touching the
    same pair of accounts cannot deadlock by taking the locks in opposite
    orders. SQLite ignores select_for_update() — its own writer lock serialises
    transactions instead — but the lock is real on PostgreSQL and MySQL.
    """
    return UserProfile.objects.select_for_update().in_bulk(profile_pks)


@login_required
def dashboard_view(request):
    profile = get_or_create_profile(request.user)
    if profile.is_admin:
        return redirect('admin_dashboard')

    recent_transactions = sorted(
        list(Transaction.objects.filter(sender=request.user)
             .select_related('receiver').order_by('-timestamp')[:5])
        + list(Transaction.objects.filter(receiver=request.user)
               .select_related('sender').order_by('-timestamp')[:5]),
        key=lambda t: t.timestamp,
        reverse=True,
    )[:5]

    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()

    return render(request, 'payapp/dashboard.html', {
        'profile': profile,
        'recent_transactions': recent_transactions,
        'unread_notifications': unread_count,
        'unread_count': unread_count,
        'sent_count': Transaction.objects.filter(sender=request.user).count(),
        'received_count': Transaction.objects.filter(receiver=request.user).count(),
    })


def _perform_transfer(*, sender, receiver, sender_profile, receiver_profile, amount, converted):
    """Debit the sender, credit the receiver, and record the transaction."""
    with transaction.atomic():
        locked = _lock_profiles(sender_profile.pk, receiver_profile.pk)
        sender_row = locked[sender_profile.pk]
        receiver_row = locked[receiver_profile.pk]

        if sender_row.balance < amount:
            raise InsufficientFunds

        sender_row.balance -= amount
        receiver_row.balance += converted
        sender_row.save(update_fields=['balance'])
        receiver_row.save(update_fields=['balance'])

        record = Transaction.objects.create(
            sender=sender,
            receiver=receiver,
            amount=amount,
            sender_currency=sender_row.currency,
            receiver_currency=receiver_row.currency,
            converted_amount=converted,
        )
        Notification.objects.bulk_create([
            Notification(
                user=receiver,
                message=f"{sender.get_full_name() or sender.username} sent you "
                        f"{converted} {receiver_row.currency}.",
            ),
            Notification(
                user=sender,
                message=f"You sent {amount} {sender_row.currency} to "
                        f"{receiver.get_full_name() or receiver.username}.",
            ),
        ])
        return record


@login_required
def send_payment_view(request):
    profile = get_or_create_profile(request.user)
    if profile.is_admin:
        return redirect('admin_dashboard')

    form = SendPaymentForm(request.POST or None)
    error = None

    if request.method == 'POST' and form.is_valid():
        cd = form.cleaned_data
        receiver = User.objects.filter(email__iexact=cd['receiver_email']).first()

        if receiver is None:
            error = 'No account found with that email address. Please check and try again.'
        elif receiver == request.user:
            error = 'You cannot send money to yourself.'
        else:
            receiver_profile = get_or_create_profile(receiver)
            amount = cd['amount']

            # Converted before opening the transaction: this is a blocking HTTP
            # call to the conversion service and must not run while row locks
            # are held.
            converted = convert(profile.currency, receiver_profile.currency, amount)

            try:
                _perform_transfer(
                    sender=request.user,
                    receiver=receiver,
                    sender_profile=profile,
                    receiver_profile=receiver_profile,
                    amount=amount,
                    converted=converted,
                )
                return redirect('transactions')
            except InsufficientFunds:
                error = 'Insufficient funds.'
            except DatabaseError:
                logger.exception('Transfer from %s to %s failed.', request.user.pk, receiver.pk)
                error = 'Transaction failed. Please try again.'

    return render(request, 'payapp/send_payment.html', {
        'form': form, 'error': error, 'profile': profile,
    })


@login_required
def request_payment_view(request):
    profile = get_or_create_profile(request.user)
    if profile.is_admin:
        return redirect('admin_dashboard')

    form = RequestPaymentForm(request.POST or None)
    error = None

    if request.method == 'POST' and form.is_valid():
        cd = form.cleaned_data
        requestee = User.objects.filter(email__iexact=cd['requestee_email']).first()

        if requestee is None:
            error = 'No account found with that email address. Please check and try again.'
        elif requestee == request.user:
            error = 'You cannot request money from yourself.'
        else:
            with transaction.atomic():
                PaymentRequest.objects.create(
                    requester=request.user,
                    requestee=requestee,
                    amount=cd['amount'],
                    currency=profile.currency,
                )
                Notification.objects.create(
                    user=requestee,
                    message=f"{request.user.get_full_name() or request.user.username} requested "
                            f"{cd['amount']} {profile.currency} from you.",
                )
            return redirect('transactions')

    return render(request, 'payapp/request_payment.html', {'form': form, 'error': error})


@login_required
def transactions_view(request):
    if get_or_create_profile(request.user).is_admin:
        return redirect('admin_dashboard')
    return render(request, 'payapp/transactions.html', _transactions_context(request.user))


@login_required
def notifications_view(request):
    if get_or_create_profile(request.user).is_admin:
        return redirect('admin_dashboard')

    # Read notifications stay in the list — marking one as read only changes
    # how it is styled, it does not remove it.
    notifications = Notification.objects.filter(user=request.user).order_by('-timestamp')

    return render(request, 'payapp/notifications.html', {
        'notifications': notifications,
        'unread_count': notifications.filter(is_read=False).count(),
    })


# ── Notification read-state (AJAX) ───────────────────────────────────────────

@login_required
@require_POST
def mark_notification_read(request, pk):
    """Mark a single notification as read."""
    # Scoped to the current user, so one account cannot touch another's rows.
    updated = Notification.objects.filter(pk=pk, user=request.user).update(is_read=True)
    if not updated:
        return JsonResponse(
            {'status': 'error', 'message': 'Notification not found'}, status=404
        )
    return JsonResponse({'status': 'success', 'message': 'Notification marked as read'})


@login_required
@require_POST
def mark_all_notifications_read(request):
    """Mark every unread notification for the current user as read."""
    updated_count = Notification.objects.filter(
        user=request.user, is_read=False
    ).update(is_read=True)

    if updated_count == 0:
        message = 'No unread notifications found! All notifications are already read.'
    else:
        message = f'{updated_count} notification(s) marked as read'

    return JsonResponse({
        'status': 'success',
        'message': message,
        'updated_count': updated_count,
    })


# ── Payment requests ─────────────────────────────────────────────────────────

def _settle_payment_request(*, pay_request, payer, payer_profile, payee_profile, debit):
    """Accept a payment request: debit the payer, credit the requester."""
    with transaction.atomic():
        # The request row is locked and re-checked as well, so a double submit
        # cannot settle the same request twice.
        locked_request = PaymentRequest.objects.select_for_update().get(pk=pay_request.pk)
        if locked_request.status != 'PENDING':
            raise RequestAlreadySettled

        locked = _lock_profiles(payer_profile.pk, payee_profile.pk)
        payer_row = locked[payer_profile.pk]
        payee_row = locked[payee_profile.pk]

        if payer_row.balance < debit:
            raise InsufficientFunds

        payer_row.balance -= debit
        payee_row.balance += locked_request.amount
        payer_row.save(update_fields=['balance'])
        payee_row.save(update_fields=['balance'])

        locked_request.status = 'ACCEPTED'
        locked_request.save(update_fields=['status'])

        Transaction.objects.create(
            sender=payer,
            receiver=locked_request.requester,
            amount=debit,
            sender_currency=payer_row.currency,
            receiver_currency=locked_request.currency,
            converted_amount=locked_request.amount,
        )
        Notification.objects.bulk_create([
            Notification(
                user=locked_request.requester,
                message=f"{payer.get_full_name() or payer.username} accepted your request and "
                        f"sent {locked_request.amount} {locked_request.currency}.",
            ),
            Notification(
                user=payer,
                message=f"You paid {debit} {payer_row.currency} to "
                        f"{locked_request.requester.get_full_name() or locked_request.requester.username}.",
            ),
        ])


@login_required
@require_POST
def handle_payment_request_view(request, pk):
    """Accept or reject an incoming payment request."""
    payer_profile = get_or_create_profile(request.user)
    if payer_profile.is_admin:
        return redirect('admin_dashboard')

    pay_request = get_object_or_404(
        PaymentRequest, pk=pk, requestee=request.user, status='PENDING'
    )
    action = request.POST.get('action')

    if action == 'reject':
        with transaction.atomic():
            updated = PaymentRequest.objects.filter(
                pk=pay_request.pk, status='PENDING'
            ).update(status='REJECTED')
            if updated:
                Notification.objects.create(
                    user=pay_request.requester,
                    message=f"{request.user.get_full_name() or request.user.username} rejected "
                            f"your payment request of {pay_request.amount} {pay_request.currency}.",
                )
        return redirect('transactions')

    if action != 'accept':
        messages.error(request, 'Unrecognised action.')
        return redirect('transactions')

    payee_profile = get_or_create_profile(pay_request.requester)

    # Converted outside the transaction — see the note in send_payment_view.
    debit = convert(pay_request.currency, payer_profile.currency, pay_request.amount)

    try:
        _settle_payment_request(
            pay_request=pay_request,
            payer=request.user,
            payer_profile=payer_profile,
            payee_profile=payee_profile,
            debit=debit,
        )
    except InsufficientFunds:
        messages.error(
            request,
            f'Insufficient funds: you need {debit} {payer_profile.currency} '
            'to accept this request.',
        )
    except RequestAlreadySettled:
        messages.info(request, 'That payment request has already been handled.')
    except DatabaseError:
        logger.exception('Settling payment request %s failed.', pay_request.pk)
        messages.error(request, 'Could not complete the payment. Please try again.')
    else:
        messages.success(
            request,
            f'Paid {pay_request.amount} {pay_request.currency} to '
            f'{pay_request.requester.get_full_name() or pay_request.requester.username}.',
        )

    return redirect('transactions')


# ── Admin views ──────────────────────────────────────────────────────────────

@login_required
def admin_dashboard_view(request):
    if not get_or_create_profile(request.user).is_admin:
        return redirect('dashboard')

    return render(request, 'admin/dashboard.html', {
        'users': UserProfile.objects.select_related('user').filter(is_admin=False),
        'total_transactions': Transaction.objects.count(),
        'admin_count': UserProfile.objects.filter(is_admin=True).count(),
    })


@login_required
def admin_transactions_view(request):
    if not get_or_create_profile(request.user).is_admin:
        return redirect('dashboard')

    return render(request, 'admin/transactions.html', {
        'transactions': Transaction.objects.select_related('sender', 'receiver')
            .order_by('-timestamp'),
    })


@login_required
def admin_users_view(request):
    if not get_or_create_profile(request.user).is_admin:
        return redirect('dashboard')

    return render(request, 'admin/users.html', {
        'users': UserProfile.objects.select_related('user').all(),
    })
