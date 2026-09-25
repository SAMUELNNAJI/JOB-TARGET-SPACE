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
    path("dashboard/employer/", views.employer_dashboard, name="employer_dashboard"),
    path("dashboard/employer/<slug:section>/", views.employer_section, name="employer_section"),
    path("dashboard/employer/candidates/<int:match_id>/shortlist/", views.shortlist_candidate, name="shortlist_candidate"),
    path("dashboard/admin/", views.admin_dashboard, name="admin_dashboard"),
    path("dashboard/admin/<slug:section>/", views.admin_section, name="admin_section"),
    path("dashboard/admin/matching/push/<int:match_id>/", views.push_candidate, name="push_candidate"),
    path("dashboard/admin/candidates/<int:profile_id>/verify/", views.admin_verify_candidate, name="admin_verify_candidate"),
    path("dashboard/admin/candidates/<int:profile_id>/reject/", views.admin_reject_candidate, name="admin_reject_candidate"),
    path("dashboard/admin/candidates/<int:profile_id>/revoke/", views.admin_revoke_verification, name="admin_revoke_verification"),
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
