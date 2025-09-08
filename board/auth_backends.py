from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

UserModel = get_user_model()

class EmailOrUsernameBackend(ModelBackend):
    """Authenticate with email OR username."""
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            return None
        username = (username or "").strip()
        # Try email match (case-insensitive), fall back to username
        users = UserModel.objects.filter(email__iexact=username) or UserModel.objects.filter(username__iexact=username)
        user = users.first()
        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
