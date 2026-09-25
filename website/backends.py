from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User


class EmailOrUsernameModelBackend(ModelBackend):
    """Allow login with either username or email (case-insensitive).

    Django's default ModelBackend only matches ``username`` exactly, so a
    superuser created as ``username='admin'`` can never log in through the
    site's email-based SignInForm. This backend first tries an exact
    username match, then falls back to a case-insensitive email match.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        candidates = []
        # 1) Exact username match (default behaviour, keeps /admin/ working).
        try:
            candidates.append(User.objects.get(username=username))
        except User.DoesNotExist:
            pass
        # 2) Case-insensitive email match (makes /signin/ work for
        #    superusers whose username != email). Use filter()+order_by so
        #    duplicate email rows don't raise MultipleObjectsReturned.
        candidates.extend(
            User.objects.filter(email__iexact=username).exclude(
                pk__in=[u.pk for u in candidates]
            ).order_by("id")
        )
        for user in candidates:
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        return None
