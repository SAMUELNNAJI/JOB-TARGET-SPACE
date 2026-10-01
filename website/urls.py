from django.urls import path

from . import views

app_name = "website"

urlpatterns = [
    path("", views.page, {"page_name": "home"}, name="home"),
    path("about/", views.page, {"page_name": "about"}, name="about"),
    path("employers/", views.page, {"page_name": "employers"}, name="employers"),
    path("candidates/", views.page, {"page_name": "candidates"}, name="candidates"),
    path("how-it-works/", views.page, {"page_name": "how_it_works"}, name="how_it_works"),
    path("contact/", views.page, {"page_name": "contact"}, name="contact"),
    path("privacy/", views.page, {"page_name": "privacy"}, name="privacy"),
    path("terms/", views.page, {"page_name": "terms"}, name="terms"),
    path("signin/", views.SignInView.as_view(), name="signin"),
    path("signup/", views.signup, name="signup"),
    path("dashboard/candidate/", views.candidate_dashboard, name="candidate_dashboard"),
    path("dashboard/candidate/submit/", views.submit_candidate_profile, name="submit_candidate_profile"),
    path("dashboard/candidate/documents/", views.candidate_documents_legacy, name="candidate_documents_legacy"),
    path("dashboard/candidate/specialization/add/", views.add_specialization, name="add_specialization"),
    path("dashboard/candidate/<slug:section>/", views.candidate_section, name="candidate_section"),
    path("logout/", views.logout_view, name="logout"),
    # Protected uploads. These replace direct `file.url` links so that a CV,
    # payment proof or voice note is only served to its owner or to staff.
    path("documents/<int:document_id>/download/", views.candidate_document_download, name="candidate_document_download"),
    path("payments/<int:payment_id>/proof/", views.payment_proof_download, name="payment_proof_download"),
    path("support/messages/<int:message_id>/audio/", views.support_audio_download, name="support_audio_download"),
    path("dashboard/employer/", views.employer_dashboard, name="employer_dashboard"),
    # Direct bank transfer: the employer uploads proof of payment and an admin
    # approves it. There is no payment gateway and no webhook.
    path("dashboard/employer/subscription/proof/", views.submit_payment_proof, name="submit_payment_proof"),
    path("dashboard/employer/candidates/<int:match_id>/shortlist/", views.shortlist_candidate, name="shortlist_candidate"),
    path("dashboard/employer/candidates/<int:match_id>/detail/", views.employer_candidate_detail, name="employer_candidate_detail"),
    path("dashboard/employer/candidates/<int:match_id>/accept/", views.accept_candidate, name="accept_candidate"),
    path("dashboard/employer/<slug:section>/", views.employer_section, name="employer_section"),
    path("dashboard/admin/", views.admin_dashboard, name="admin_dashboard"),
    # ── Support chat (htmx) ─────────────────────────────────────────────
    # These MUST come before the `admin/<slug:section>/` catch-all below,
    # otherwise "support" is matched as a section slug and 404s.
    path("dashboard/admin/support/messages/", views.admin_support_messages, name="admin_support_messages"),
    path("dashboard/admin/support/send/", views.admin_support_send, name="admin_support_send"),
    path("dashboard/admin/support/", views.admin_support_inbox, name="admin_support_inbox"),
    path("dashboard/admin/payments/<int:payment_id>/action/", views.admin_payment_action, name="admin_payment_action"),
    path("dashboard/admin/<slug:section>/", views.admin_section, name="admin_section"),
    path("dashboard/admin/matching/push/<int:match_id>/", views.push_candidate, name="push_candidate"),
    path("dashboard/admin/matching/create/", views.create_match, name="create_match"),
    path("dashboard/admin/matching/<int:match_id>/remove/", views.remove_match, name="remove_match"),
    path("dashboard/admin/employer/<int:profile_id>/detail/", views.admin_employer_detail, name="admin_employer_detail"),
    path("dashboard/admin/candidates/<int:profile_id>/verify/", views.admin_verify_candidate, name="admin_verify_candidate"),
    path("dashboard/admin/candidates/<int:profile_id>/reject/", views.admin_reject_candidate, name="admin_reject_candidate"),
    path("dashboard/admin/candidates/<int:profile_id>/revoke/", views.admin_revoke_verification, name="admin_revoke_verification"),
    path("dashboard/search/", views.dashboard_search, name="dashboard_search"),
    path("dashboard/notifications/json/", views.notifications_json, name="notifications_json"),
    path("dashboard/notifications/mark-read/", views.notifications_mark_read, name="notifications_mark_read"),
    path("dashboard/admin/matching/search/", views.matching_candidate_search, name="matching_candidate_search"),
    # ── Support chat — user side ───────────────────────────────────────
    path("dashboard/support/chat/messages/", views.support_chat_messages, name="support_chat_messages"),
    path("dashboard/support/chat/send/", views.support_chat_send, name="support_chat_send"),
    path("dashboard/support/chat/", views.support_chat, name="support_chat"),
    path("about.html", views.page, {"page_name": "about"}),
    path("employers.html", views.page, {"page_name": "employers"}),
    path("candidates.html", views.page, {"page_name": "candidates"}),
    path("how-it-works.html", views.page, {"page_name": "how_it_works"}),
    path("contact.html", views.page, {"page_name": "contact"}),
    path("privacy.html", views.page, {"page_name": "privacy"}),
    path("terms.html", views.page, {"page_name": "terms"}),
    path("signin.html", views.SignInView.as_view()),
    path("signup.html", views.signup),
]
