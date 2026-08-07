"""Authentication that accepts either a username or an email address.

Every user-facing feature in this application addresses people by email —
payments and payment requests are both sent to an email address — so requiring
a separate username at the login screen is a needless trip hazard. This backend
lets either work.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class UsernameOrEmailBackend(ModelBackend):
    """Authenticate against username or email, both case-insensitively."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()

        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if username is None or password is None:
            return None

        try:
            user = UserModel.objects.get(
                Q(username__iexact=username) | Q(email__iexact=username)
            )
        except UserModel.DoesNotExist:
            # Run the hasher anyway so that a missing account takes the same
            # time as a wrong password, and cannot be identified by timing.
            UserModel().set_password(password)
            return None
        except UserModel.MultipleObjectsReturned:
            # Sign-up forbids duplicate emails, so this means one account's
            # username collides with another's email. Refuse rather than guess.
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
