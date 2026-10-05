from django.core.management.base import BaseCommand
from django.utils import timezone

from website.models import Subscription
from website.subscription_sweep import sweep_subscriptions


class Command(BaseCommand):
    help = (
        "Send the subscription lifecycle emails: the 10-day renewal warning "
        "and the expiry notice, exactly once per subscription row. Safe to "
        "run any number of times a day — timestamp markers on each row "
        "deduplicate it. Intended for a daily cron entry (see DEPLOY.md)."
    )

    def handle(self, *args, **options):
        qs = Subscription.objects.filter(is_active=True).select_related("employer__user")
        reminded, expired = sweep_subscriptions(qs)
        stamp = timezone.now().strftime("%Y-%m-%d %H:%M")
        self.stdout.write(self.style.SUCCESS(
            f"[{stamp}] renewal reminders sent: {reminded} | "
            f"expiry notices sent: {expired}"
        ))
