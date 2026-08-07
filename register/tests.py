from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from conversionservice.testutils import LocalRatesMixin
from register.models import UserProfile, get_or_create_profile

# Long enough, not numeric, not a common password, and unlike any username used
# here — so it satisfies every configured AUTH_PASSWORD_VALIDATOR.
STRONG_PASSWORD = 'Zebra-Quilt-Harbour-71'


class RegistrationTests(LocalRatesMixin, TestCase):

    def payload(self, **overrides):
        data = {
            'username': 'alice',
            'first_name': 'Alice',
            'last_name': 'Adams',
            'email': 'alice@example.com',
            'password': STRONG_PASSWORD,
            'password_confirm': STRONG_PASSWORD,
            'currency': 'GBP',
        }
        data.update(overrides)
        return data

    def test_creates_user_and_profile(self):
        response = self.client.post(reverse('register'), self.payload())

        self.assertRedirects(response, reverse('dashboard'))
        profile = UserProfile.objects.get(user__username='alice')
        self.assertEqual(profile.currency, 'GBP')
        self.assertEqual(profile.balance, Decimal('500.00'))
        self.assertFalse(profile.is_admin)

    def test_starting_balance_is_converted_into_chosen_currency(self):
        self.client.post(reverse('register'), self.payload(currency='USD'))

        profile = UserProfile.objects.get(user__username='alice')
        self.assertEqual(profile.currency, 'USD')
        self.assertEqual(profile.balance, Decimal('635.00'))  # 500 GBP at 1.27

    def test_rejects_weak_password(self):
        """AUTH_PASSWORD_VALIDATORS must actually apply to this form.

        create_user() does not run them, so without explicit validation in the
        form the validators configured in settings would have no effect.
        """
        response = self.client.post(
            reverse('register'),
            self.payload(password='password', password_confirm='password'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='alice').exists())
        self.assertIn('password', response.context['form'].errors)

    def test_rejects_short_password(self):
        response = self.client.post(
            reverse('register'), self.payload(password='ab1', password_confirm='ab1')
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='alice').exists())

    def test_rejects_mismatched_passwords(self):
        response = self.client.post(
            reverse('register'), self.payload(password_confirm='something-else-97')
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='alice').exists())
        self.assertIn('password_confirm', response.context['form'].errors)

    def test_rejects_duplicate_email_case_insensitively(self):
        User.objects.create_user('existing', 'ALICE@example.com', STRONG_PASSWORD)

        response = self.client.post(reverse('register'), self.payload())

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='alice').exists())
        self.assertIn('email', response.context['form'].errors)

    def test_rejects_duplicate_username_case_insensitively(self):
        User.objects.create_user('Alice', 'other@example.com', STRONG_PASSWORD)

        response = self.client.post(reverse('register'), self.payload())

        self.assertEqual(response.status_code, 200)
        self.assertIn('username', response.context['form'].errors)

    def test_no_profile_is_left_behind_when_registration_fails(self):
        self.client.post(reverse('register'), self.payload(password_confirm='nope-1234'))
        self.assertEqual(UserProfile.objects.count(), 0)


class ProfileHelperTests(TestCase):

    def test_creates_a_missing_profile(self):
        """Accounts made outside the sign-up flow used to 500 on every page."""
        user = User.objects.create_user('nobody', 'nobody@example.com', STRONG_PASSWORD)
        self.assertFalse(UserProfile.objects.filter(user=user).exists())

        profile = get_or_create_profile(user)

        self.assertEqual(profile.balance, Decimal('0.00'))
        self.assertEqual(profile.currency, 'GBP')
        self.assertFalse(profile.is_admin)

    def test_superuser_gets_the_in_app_admin_role(self):
        superuser = User.objects.create_superuser(
            'root', 'root@example.com', STRONG_PASSWORD
        )
        self.assertTrue(get_or_create_profile(superuser).is_admin)

    def test_is_idempotent(self):
        user = User.objects.create_user('nobody', 'nobody@example.com', STRONG_PASSWORD)

        first = get_or_create_profile(user)
        first.balance = Decimal('42.00')
        first.save()

        self.assertEqual(get_or_create_profile(user).pk, first.pk)
        self.assertEqual(UserProfile.objects.count(), 1)
        self.assertEqual(get_or_create_profile(user).balance, Decimal('42.00'))


class LoginTests(LocalRatesMixin, TestCase):

    def test_member_lands_on_the_member_dashboard(self):
        user = User.objects.create_user('member', 'member@example.com', STRONG_PASSWORD)
        UserProfile.objects.create(user=user, currency='GBP', balance=Decimal('10.00'))

        response = self.client.post(
            reverse('login'), {'username': 'member', 'password': STRONG_PASSWORD}
        )
        self.assertRedirects(response, reverse('dashboard'))

    def test_admin_lands_on_the_admin_dashboard(self):
        user = User.objects.create_user('boss', 'boss@example.com', STRONG_PASSWORD)
        UserProfile.objects.create(user=user, balance=Decimal('0.00'), is_admin=True)

        response = self.client.post(
            reverse('login'), {'username': 'boss', 'password': STRONG_PASSWORD}
        )
        self.assertRedirects(response, reverse('admin_dashboard'))

    def test_superuser_without_a_profile_can_sign_in(self):
        """Regression: this path used to raise RelatedObjectDoesNotExist."""
        User.objects.create_superuser('root', 'root@example.com', STRONG_PASSWORD)

        response = self.client.post(
            reverse('login'), {'username': 'root', 'password': STRONG_PASSWORD}
        )
        self.assertRedirects(response, reverse('admin_dashboard'))


class SignInIdentifierTests(LocalRatesMixin, TestCase):
    """Payments are addressed by email, so the login screen accepts one too."""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            'tabish', 'Tabish@Example.com', STRONG_PASSWORD
        )
        UserProfile.objects.create(user=self.user, balance=Decimal('10.00'))

    def _login(self, identifier):
        return self.client.post(
            reverse('login'), {'username': identifier, 'password': STRONG_PASSWORD}
        )

    def test_username_works(self):
        self.assertRedirects(self._login('tabish'), reverse('dashboard'))

    def test_email_works(self):
        self.assertRedirects(self._login('Tabish@Example.com'), reverse('dashboard'))

    def test_email_is_case_insensitive(self):
        self.assertRedirects(self._login('tabish@example.com'), reverse('dashboard'))

    def test_username_is_case_insensitive(self):
        self.assertRedirects(self._login('TABISH'), reverse('dashboard'))

    def test_wrong_password_is_rejected(self):
        response = self.client.post(
            reverse('login'), {'username': 'tabish', 'password': 'not-the-password'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_unknown_identifier_is_rejected(self):
        response = self._login('nobody@example.com')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_the_form_says_it_accepts_either(self):
        page = self.client.get(reverse('login'))
        self.assertContains(page, 'Username or email')


class EntryPointTests(LocalRatesMixin, TestCase):
    """The addresses a newcomer actually types must not 404.

    Every page lives under a sub-path, so the site root and the bare
    /webapps2026/ prefix both used to return 404 — including the URL the
    README tells people to open.
    """

    def test_site_root_reaches_the_login_page(self):
        response = self.client.get('/', follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain[-1][0], f'{reverse("login")}?next={reverse("dashboard")}')

    def test_documented_prefix_reaches_the_login_page(self):
        response = self.client.get('/webapps2026/', follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'csrfmiddlewaretoken')

    def test_signed_in_user_lands_on_the_dashboard(self):
        user = User.objects.create_user('member', 'member@example.com', STRONG_PASSWORD)
        UserProfile.objects.create(user=user, balance=Decimal('10.00'))
        self.client.force_login(user)

        response = self.client.get('/', follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain[-1][0], reverse('dashboard'))


class LogoutTests(LocalRatesMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user('member', 'member@example.com', STRONG_PASSWORD)
        UserProfile.objects.create(user=self.user, balance=Decimal('10.00'))
        self.client.force_login(self.user)

    def test_post_signs_the_user_out(self):
        response = self.client.post(reverse('logout'))

        self.assertRedirects(response, reverse('login'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_get_cannot_sign_the_user_out(self):
        """A third-party page must not be able to force a logout via a link."""
        response = self.client.get(reverse('logout'))

        self.assertEqual(response.status_code, 405)
        self.assertIn('_auth_user_id', self.client.session)

    def test_the_sign_out_control_is_a_csrf_protected_form(self):
        page = self.client.get(reverse('dashboard'))

        self.assertContains(page, f'action="{reverse("logout")}"')
        self.assertContains(page, 'csrfmiddlewaretoken')


class AdminRegistrationTests(LocalRatesMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user('boss', 'boss@example.com', STRONG_PASSWORD)
        UserProfile.objects.create(user=self.admin, balance=Decimal('0.00'), is_admin=True)

        self.member = User.objects.create_user('member', 'member@example.com', STRONG_PASSWORD)
        UserProfile.objects.create(user=self.member, balance=Decimal('50.00'))

    def test_anonymous_visitor_is_sent_to_login(self):
        response = self.client.get(reverse('admin_register'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response['Location'])

    def test_member_cannot_reach_it(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('admin_register'))
        self.assertRedirects(response, reverse('dashboard'))

    def test_admin_can_create_another_admin(self):
        self.client.force_login(self.admin)

        response = self.client.post(reverse('admin_register'), {
            'username': 'deputy',
            'first_name': 'Dana',
            'last_name': 'Deputy',
            'email': 'deputy@example.com',
            'password': STRONG_PASSWORD,
            'password_confirm': STRONG_PASSWORD,
        })

        self.assertRedirects(response, reverse('admin_dashboard'))
        profile = UserProfile.objects.get(user__username='deputy')
        self.assertTrue(profile.is_admin)
        self.assertEqual(profile.balance, Decimal('0.00'))

    def test_admin_creation_also_rejects_duplicate_emails(self):
        """Without this, two accounts share an email and payment lookups break."""
        self.client.force_login(self.admin)

        response = self.client.post(reverse('admin_register'), {
            'username': 'deputy',
            'first_name': 'Dana',
            'last_name': 'Deputy',
            'email': 'MEMBER@example.com',
            'password': STRONG_PASSWORD,
            'password_confirm': STRONG_PASSWORD,
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='deputy').exists())
