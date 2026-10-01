"""Tests for the Flutterwave subscription webhook.

The webhook is @csrf_exempt and publicly reachable, so its signature check is
the only thing standing between an attacker and free subscriptions. These
tests pin down the behaviour that used to be wrong: when
FLUTTERWAVE_WEBHOOK_HASH was unset, the old check

    if secret_hash and received_hash != secret_hash

short-circuited on an empty secret_hash and accepted EVERY request.

Run with:  python manage.py test website.tests_webhook
"""

import json

from django.test import TestCase, override_settings

from . import views


WEBHOOK_URL = "/dashboard/employer/subscription/webhook/"

CHARGE_COMPLETED = {
    "event": "charge.completed",
    "data": {"status": "successful", "tx_ref": "anything", "id": 1},
}


class WebhookSignatureTests(TestCase):
    """A request without a valid verif-hash must never be processed."""

    def post_webhook(self, hash_header=None, payload=None):
        body = json.dumps(payload if payload is not None else CHARGE_COMPLETED)
        headers = {}
        if hash_header is not None:
            headers["HTTP_VERIF_HASH"] = hash_header
        return self.client.post(
            WEBHOOK_URL, data=body, content_type="application/json", **headers
        )

    @override_settings(FLUTTERWAVE_WEBHOOK_HASH="s3cret-hash")
    def test_correct_hash_is_accepted(self):
        """The happy path still works — Flutterwave itself is not locked out."""
        response = self.post_webhook(hash_header="s3cret-hash")
        self.assertNotEqual(response.status_code, 403)

    @override_settings(FLUTTERWAVE_WEBHOOK_HASH="s3cret-hash")
    def test_wrong_hash_is_rejected(self):
        response = self.post_webhook(hash_header="wrong")
        self.assertEqual(response.status_code, 403)

    @override_settings(FLUTTERWAVE_WEBHOOK_HASH="s3cret-hash")
    def test_missing_hash_header_is_rejected(self):
        response = self.post_webhook(hash_header=None)
        self.assertEqual(response.status_code, 403)

    @override_settings(FLUTTERWAVE_WEBHOOK_HASH="")
    def test_unconfigured_hash_rejects_everything(self):
        """The regression test.

        With no hash configured, a forged body must be refused. The old code
        accepted it, which let anyone mark a subscription paid for free.
        """
        response = self.post_webhook(hash_header="")
        self.assertEqual(response.status_code, 503)

    @override_settings(FLUTTERWAVE_WEBHOOK_HASH="")
    def test_unconfigured_hash_rejects_even_a_plausible_header(self):
        response = self.post_webhook(hash_header="anything-at-all")
        self.assertEqual(response.status_code, 503)

    def test_get_is_not_allowed(self):
        response = self.client.get(WEBHOOK_URL)
        self.assertEqual(response.status_code, 405)

    def test_view_uses_constant_time_comparison(self):
        """Guard against the comparison being reverted to `!=`.

        Only executable lines are inspected. The view's comments deliberately
        quote the old buggy expression to explain why it changed, so scanning
        the raw source would match the explanation, not the code.
        """
        import inspect

        code = [
            line
            for line in inspect.getsource(views.subscription_webhook).splitlines()
            if not line.strip().startswith("#")
        ]
        code = "\n".join(code)

        self.assertIn("secrets.compare_digest", code)
        self.assertNotIn("secret_hash and received_hash !=", code)
        # The short-circuit is the actual bug: it skipped verification
        # entirely whenever the secret was unset.
        self.assertNotIn("if secret_hash and", code)

