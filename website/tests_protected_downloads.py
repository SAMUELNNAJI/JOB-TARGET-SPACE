"""Tests that uploaded files are only served to those entitled to see them.

Before these views existed, templates linked straight to `{{ doc.file.url }}`
and jobspace/urls.py exposed a catch-all `/media/` route. Any CV, payment proof
or voice note was downloadable by anyone who learned or guessed its path.

These tests pin the replacement behaviour down. They are the regression net:
if someone re-adds a public media route, `test_no_public_media_route` fails.

Run with:  python manage.py test website.tests_protected_downloads
"""

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import (
    CandidateDocument, Payment, Profile, SupportMessage, SupportThread,
)

User = get_user_model()


def make_profile(user, role):
    return Profile.objects.create(user=user, role=role)


class ProtectedDownloadTests(TestCase):
    def setUp(self):
        self.candidate = User.objects.create_user(
            username="cand", email="cand@example.com", password="pw-C0rrect!"
        )
        self.other_candidate = User.objects.create_user(
            username="cand2", email="c2@example.com", password="pw-C0rrect!"
        )
        self.employer = User.objects.create_user(
            username="emp", email="emp@example.com", password="pw-C0rrect!"
        )
        self.staff = User.objects.create_user(
            username="admin", email="a@example.com",
            password="pw-C0rrect!", is_staff=True,
        )

        self.cand_profile = make_profile(self.candidate, Profile.Role.CANDIDATE)
        self.other_profile = make_profile(self.other_candidate, Profile.Role.CANDIDATE)
        self.emp_profile = make_profile(self.employer, Profile.Role.EMPLOYER)

        self.document = CandidateDocument.objects.create(
            profile=self.cand_profile,
            file=SimpleUploadedFile("cv.pdf", b"%PDF-1.4 secret", content_type="application/pdf"),
        )
        self.payment = Payment.objects.create(
            employer=self.emp_profile,
            reference="REF-1",
            amount=5000,
            proof=SimpleUploadedFile("proof.png", b"\x89PNG secret", content_type="image/png"),
        )
        self.thread = SupportThread.objects.create(profile=self.cand_profile)
        self.message = SupportMessage.objects.create(
            thread=self.thread,
            sender=self.candidate,
            sender_role=SupportMessage.Role.USER,
            body="",
            audio=SimpleUploadedFile("clip.webm", b"WEBM secret", content_type="audio/webm"),
        )

    def doc_url(self, doc=None):
        return reverse("website:candidate_document_download",
                       args=[(doc or self.document).id])

    def pay_url(self, payment=None):
        return reverse("website:payment_proof_download",
                       args=[(payment or self.payment).id])

    def audio_url(self, message=None):
        return reverse("website:support_audio_download",
                       args=[(message or self.message).id])

    # ── the core guarantee ──────────────────────────────────────────────────

    def test_anonymous_cannot_download_anything(self):
        """The regression this whole change exists for."""
        for url in (self.doc_url(), self.pay_url(), self.audio_url()):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/signin/", response["Location"])

    def test_other_candidate_cannot_read_someone_elses_cv(self):
        self.client.force_login(self.other_candidate)
        self.assertEqual(self.client.get(self.doc_url()).status_code, 403)

    def test_employer_cannot_read_a_cv_by_direct_url(self):
        """Employers review candidates through shortlisting, not raw URLs."""
        self.client.force_login(self.employer)
        self.assertEqual(self.client.get(self.doc_url()).status_code, 403)

    def test_other_employer_cannot_read_a_payment_proof(self):
        intruder = User.objects.create_user(
            username="emp2", email="e2@example.com", password="pw-C0rrect!"
        )
        make_profile(intruder, Profile.Role.EMPLOYER)
        self.client.force_login(intruder)
        self.assertEqual(self.client.get(self.pay_url()).status_code, 403)

    def test_cannot_listen_to_another_conversation(self):
        self.client.force_login(self.employer)
        self.assertEqual(self.client.get(self.audio_url()).status_code, 403)

    # ── legitimate access still works ──────────────────────────────────────

    def test_owner_can_download_their_own_cv(self):
        self.client.force_login(self.candidate)
        response = self.client.get(self.doc_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"%PDF", b"".join(response.streaming_content))

    def test_employer_can_download_their_own_proof(self):
        self.client.force_login(self.employer)
        self.assertEqual(self.client.get(self.pay_url()).status_code, 200)

    def test_staff_can_download_anything(self):
        self.client.force_login(self.staff)
        for url in (self.doc_url(), self.pay_url(), self.audio_url()):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    # ── hardening of the response itself ───────────────────────────────────

    def test_response_forces_a_download_and_blocks_inline_rendering(self):
        """Stops an uploaded .html/.svg executing under our own origin."""
        self.client.force_login(self.candidate)
        response = self.client.get(self.doc_url())
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertIn("no-store", response["Cache-Control"])

    def test_filename_cannot_smuggle_extra_header_parameters(self):
        """A crafted name must not be able to break out of the header."""
        nasty = CandidateDocument.objects.create(
            profile=self.cand_profile,
            file=SimpleUploadedFile('evil.pdf', b"%PDF", content_type="application/pdf"),
        )
        self.client.force_login(self.candidate)
        disposition = self.client.get(self.doc_url(nasty))["Content-Disposition"]
        # Exactly one filename parameter, and no stray quote left behind.
        self.assertEqual(disposition.count('filename="'), 1)
        self.assertEqual(disposition.count('"'), 2)

    def test_missing_file_returns_404_not_500(self):
        empty = Payment.objects.create(
            employer=self.emp_profile, reference="REF-EMPTY", amount=1000
        )
        self.client.force_login(self.employer)
        self.assertEqual(self.client.get(self.pay_url(empty)).status_code, 404)

    def test_nonexistent_record_returns_404(self):
        self.client.force_login(self.candidate)
        self.assertEqual(
            self.client.get(reverse("website:candidate_document_download", args=[999999])).status_code,
            404,
        )

    # ── structural guard ───────────────────────────────────────────────────

    def test_no_public_media_route_exists(self):
        """A catch-all /media/ route would silently undo all of the above.

        /media/ must only resolve when DEBUG is on. With DEBUG=False — what
        production runs — a request for a media path must 404.
        """
        with override_settings(DEBUG=False):
            self.assertEqual(
                self.client.get(
                    "/media/candidate_documents/2026/10/cv.pdf"
                ).status_code,
                404,
            )
