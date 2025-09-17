from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

UserModel = get_user_model()


class EmailOrUsernameModelBackend(ModelBackend):
    """
    Authenticate with either username OR email (both case-insensitive).

    - Looks up the user by username__iexact OR email__iexact
    - Uses ModelBackend's password checking and permissions
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None

        # Accept both username and email in the same "username" field.
        identifier = (username or "").strip()

        try:
            user = (
                UserModel.objects
                .filter(Q(username__iexact=identifier) | Q(email__iexact=identifier))
                .order_by("id")
                .first()
            )
        except Exception:
            user = None

        if not user:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def user_can_authenticate(self, user):
        """
        Keep ModelBackend behavior: reject users with is_active=False.
        """
        is_active = getattr(user, "is_active", None)
        return is_active or is_active is None
