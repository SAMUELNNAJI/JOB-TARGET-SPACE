from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from .forms import SignInForm, SignUpForm
from .models import Profile


PAGE_NAMES = {
    "home": "index.html",
    "about": "about.html",
    "employers": "employers.html",
    "candidates": "candidates.html",
    "how_it_works": "how-it-works.html",
    "contact": "contact.html",
    "signin": "signin.html",
    "signup": "signup.html",
}


def page(request, page_name):
    return render(request, PAGE_NAMES[page_name])


def signup(request):
    role = request.GET.get("role") or request.POST.get("role")
    if role not in Profile.Role.values:
        return render(request, "auth/signup.html")

    form = SignUpForm(request.POST or None, initial={"role": role})
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("website:candidate_dashboard" if role == Profile.Role.CANDIDATE else "website:employer_dashboard")

    return render(request, "auth/signup.html", {"form": form, "role": role})


class SignInView(LoginView):
    template_name = "auth/signin.html"
    authentication_form = SignInForm
    redirect_authenticated_user = True

    def get_success_url(self):
        if self.request.user.is_staff or self.request.user.is_superuser:
            return "/admin/"
        profile = getattr(self.request.user, "profile", None)
        if profile and profile.role == Profile.Role.EMPLOYER:
            return "/dashboard/employer/"
        return "/dashboard/candidate/"


@login_required
def candidate_dashboard(request):
    return render(request, "dashboard/candidate/index.html")


@login_required
def employer_dashboard(request):
    return render(request, "dashboard/employer/index.html")
