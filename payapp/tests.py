from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from conversionservice.testutils import LocalRatesMixin
from payapp.models import Notification, PaymentRequest, Transaction
from register.models import UserProfile

STRONG_PASSWORD = 'Zebra-Quilt-Harbour-71'


def make_member(username, *, currency='GBP', balance='500.00', is_admin=False,
                first_name=None, email=None):
    user = User.objects.create_user(
        username=username,
        password=STRONG_PASSWORD,
        email=email or f'{username}@example.com',
        first_name=first_name or username.title(),
        last_name='Tester',
    )
    UserProfile.objects.create(
        user=user,
        currency=currency,
        balance=Decimal(balance),
        is_admin=is_admin,
    )
    return user


class SendPaymentTests(LocalRatesMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.alice = make_member('alice')
        self.bob = make_member('bob')
        self.client.force_login(self.alice)

    def balances(self):
        return (
            UserProfile.objects.get(user=self.alice).balance,
            UserProfile.objects.get(user=self.bob).balance,
        )

    def test_moves_money_and_records_the_transaction(self):
        response = self.client.post(
            reverse('send_payment'), {'receiver_email': 'bob@example.com', 'amount': '100.00'}
        )

        self.assertRedirects(response, reverse('transactions'))
        self.assertEqual(self.balances(), (Decimal('400.00'), Decimal('600.00')))

        record = Transaction.objects.get()
        self.assertEqual(record.sender, self.alice)
        self.assertEqual(record.receiver, self.bob)
        self.assertEqual(record.amount, Decimal('100.00'))
        self.assertEqual(record.converted_amount, Decimal('100.00'))

        # One notification for each side of the transfer.
        self.assertEqual(Notification.objects.filter(user=self.alice).count(), 1)
        self.assertEqual(Notification.objects.filter(user=self.bob).count(), 1)

    def test_converts_when_currencies_differ(self):
        UserProfile.objects.filter(user=self.bob).update(currency='USD')

        self.client.post(
            reverse('send_payment'), {'receiver_email': 'bob@example.com', 'amount': '100.00'}
        )

        # Alice is debited in GBP, Bob credited the USD equivalent at 1.27.
        self.assertEqual(self.balances(), (Decimal('400.00'), Decimal('627.00')))
        self.assertEqual(Transaction.objects.get().converted_amount, Decimal('127.00'))

    def test_rejects_a_transfer_larger_than_the_balance(self):
        response = self.client.post(
            reverse('send_payment'), {'receiver_email': 'bob@example.com', 'amount': '10000.00'}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Insufficient funds')
        self.assertEqual(self.balances(), (Decimal('500.00'), Decimal('500.00')))
        self.assertFalse(Transaction.objects.exists())

    def test_rejects_sending_to_yourself(self):
        response = self.client.post(
            reverse('send_payment'), {'receiver_email': 'alice@example.com', 'amount': '10.00'}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'cannot send money to yourself')
        self.assertFalse(Transaction.objects.exists())

    def test_rejects_an_unknown_recipient(self):
        response = self.client.post(
            reverse('send_payment'), {'receiver_email': 'ghost@example.com', 'amount': '10.00'}
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.exists())

    def test_recipient_email_is_matched_case_insensitively(self):
        response = self.client.post(
            reverse('send_payment'), {'receiver_email': 'BOB@example.com', 'amount': '10.00'}
        )

        self.assertRedirects(response, reverse('transactions'))
        self.assertEqual(self.balances(), (Decimal('490.00'), Decimal('510.00')))

    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('send_payment'))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response['Location'])

    def test_admins_are_redirected_away(self):
        self.client.force_login(make_member('boss', balance='0.00', is_admin=True))
        response = self.client.get(reverse('send_payment'))

        self.assertRedirects(response, reverse('admin_dashboard'))


class NotificationEscapingTests(LocalRatesMixin, TestCase):

    def test_a_users_name_cannot_inject_script_into_someone_elses_page(self):
        """Regression: notifications were rendered with |safe.

        Names are user-supplied and end up inside notification text, so any
        account could store script in a recipient's notifications page.
        """
        payload = '<script>alert(1)</script>'
        attacker = make_member('mallory', first_name=payload)
        victim = make_member('victim')

        self.client.force_login(attacker)
        self.client.post(
            reverse('send_payment'), {'receiver_email': 'victim@example.com', 'amount': '1.00'}
        )

        self.client.force_login(victim)
        response = self.client.get(reverse('notifications'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, payload)
        self.assertContains(response, '&lt;script&gt;')


class PaymentRequestTests(LocalRatesMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.alice = make_member('alice')   # requester
        self.bob = make_member('bob')       # requestee / payer
        self.request = PaymentRequest.objects.create(
            requester=self.alice,
            requestee=self.bob,
            amount=Decimal('100.00'),
            currency='GBP',
        )
        self.client.force_login(self.bob)

    def url(self):
        return reverse('handle_request', args=[self.request.pk])

    def balances(self):
        return (
            UserProfile.objects.get(user=self.alice).balance,
            UserProfile.objects.get(user=self.bob).balance,
        )

    def test_accepting_settles_the_request(self):
        response = self.client.post(self.url(), {'action': 'accept'})

        self.assertRedirects(response, reverse('transactions'))
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, 'ACCEPTED')
        self.assertEqual(self.balances(), (Decimal('600.00'), Decimal('400.00')))
        self.assertEqual(Transaction.objects.count(), 1)

    def test_accepting_converts_into_the_payers_currency(self):
        UserProfile.objects.filter(user=self.alice).update(currency='USD')
        PaymentRequest.objects.filter(pk=self.request.pk).update(
            currency='USD', amount=Decimal('127.00')
        )

        self.client.post(self.url(), {'action': 'accept'})

        # Bob pays 100 GBP so that Alice receives the 127 USD she asked for.
        self.assertEqual(self.balances(), (Decimal('627.00'), Decimal('400.00')))

    def test_rejecting_moves_no_money(self):
        response = self.client.post(self.url(), {'action': 'reject'})

        self.assertRedirects(response, reverse('transactions'))
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, 'REJECTED')
        self.assertEqual(self.balances(), (Decimal('500.00'), Decimal('500.00')))
        self.assertFalse(Transaction.objects.exists())
        self.assertTrue(Notification.objects.filter(user=self.alice).exists())

    def test_a_second_accept_cannot_pay_twice(self):
        self.client.post(self.url(), {'action': 'accept'})
        response = self.client.post(self.url(), {'action': 'accept'})

        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.balances(), (Decimal('600.00'), Decimal('400.00')))
        self.assertEqual(Transaction.objects.count(), 1)

    def test_accepting_without_the_funds_leaves_it_pending(self):
        UserProfile.objects.filter(user=self.bob).update(balance=Decimal('10.00'))

        response = self.client.post(self.url(), {'action': 'accept'}, follow=True)

        self.assertContains(response, 'Insufficient funds')
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, 'PENDING')
        self.assertEqual(self.balances(), (Decimal('500.00'), Decimal('10.00')))
        self.assertFalse(Transaction.objects.exists())

    def test_get_is_not_allowed(self):
        """Money must not move on a request that a link could trigger."""
        self.assertEqual(self.client.get(self.url()).status_code, 405)

    def test_another_user_cannot_settle_the_request(self):
        self.client.force_login(make_member('charlie'))

        response = self.client.post(self.url(), {'action': 'accept'})

        self.assertEqual(response.status_code, 404)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, 'PENDING')

    def test_unknown_action_does_nothing(self):
        response = self.client.post(self.url(), {'action': 'sideways'})

        self.assertRedirects(response, reverse('transactions'))
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, 'PENDING')
        self.assertEqual(self.balances(), (Decimal('500.00'), Decimal('500.00')))

    def test_cannot_request_money_from_yourself(self):
        self.client.force_login(self.alice)
        response = self.client.post(
            reverse('request_payment'),
            {'requestee_email': 'alice@example.com', 'amount': '5.00'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(PaymentRequest.objects.count(), 1)  # only the one from setUp


class NotificationReadStateTests(LocalRatesMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.alice = make_member('alice')
        self.bob = make_member('bob')
        self.note = Notification.objects.create(user=self.bob, message='For Bob only')
        self.client.force_login(self.bob)

    def test_marks_a_notification_as_read(self):
        response = self.client.post(
            reverse('mark_notification_read', args=[self.note.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')
        self.note.refresh_from_db()
        self.assertTrue(self.note.is_read)

    def test_cannot_mark_another_users_notification(self):
        self.client.force_login(self.alice)

        response = self.client.post(
            reverse('mark_notification_read', args=[self.note.pk])
        )

        self.assertEqual(response.status_code, 404)
        self.note.refresh_from_db()
        self.assertFalse(self.note.is_read)

    def test_get_is_not_allowed(self):
        response = self.client.get(reverse('mark_notification_read', args=[self.note.pk]))
        self.assertEqual(response.status_code, 405)

    def test_marks_all_as_read_for_the_current_user_only(self):
        alice_note = Notification.objects.create(user=self.alice, message='For Alice')

        response = self.client.post(reverse('mark_all_notifications_read'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['updated_count'], 1)
        self.note.refresh_from_db()
        alice_note.refresh_from_db()
        self.assertTrue(self.note.is_read)
        self.assertFalse(alice_note.is_read)

    def test_marking_all_when_none_are_unread(self):
        Notification.objects.all().update(is_read=True)

        response = self.client.post(reverse('mark_all_notifications_read'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['updated_count'], 0)


class AdminAccessTests(LocalRatesMixin, TestCase):

    ADMIN_VIEWS = ['admin_dashboard', 'admin_transactions', 'admin_users']

    def setUp(self):
        super().setUp()
        self.member = make_member('member')
        self.admin = make_member('boss', balance='0.00', is_admin=True)

    def test_members_are_turned_away(self):
        self.client.force_login(self.member)
        for name in self.ADMIN_VIEWS:
            with self.subTest(view=name):
                self.assertRedirects(self.client.get(reverse(name)), reverse('dashboard'))

    def test_anonymous_visitors_are_sent_to_login(self):
        for name in self.ADMIN_VIEWS:
            with self.subTest(view=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse('login'), response['Location'])

    def test_admins_get_through(self):
        self.client.force_login(self.admin)
        for name in self.ADMIN_VIEWS:
            with self.subTest(view=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)
