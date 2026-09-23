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
    path("signin/", views.SignInView.as_view(), name="signin"),
    path("signup/", views.signup, name="signup"),
    path("dashboard/candidate/", views.candidate_dashboard, name="candidate_dashboard"),
    path("dashboard/employer/", views.employer_dashboard, name="employer_dashboard"),
    path("about.html", views.page, {"page_name": "about"}),
    path("employers.html", views.page, {"page_name": "employers"}),
    path("candidates.html", views.page, {"page_name": "candidates"}),
    path("how-it-works.html", views.page, {"page_name": "how_it_works"}),
    path("contact.html", views.page, {"page_name": "contact"}),
    path("signin.html", views.SignInView.as_view()),
    path("signup.html", views.signup),
]
