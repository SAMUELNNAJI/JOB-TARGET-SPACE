from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Count, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import (
    CandidateDocumentForm, CandidateProfileForm, EmployerProfileForm,
    QualificationForm, RecruitmentRequestForm, SignInForm, SignUpForm,
)
from .models import (
    AuditLog, CandidateMatch, Notification, Payment, Profile,
    Qualification, RecruitmentRequest, ReplacementRequest,
    Shortlist, Specialization, Subscription,
)

# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

PAGE_NAMES = {
    "home": "index.html",
    "about": "about.html",
    "employers": "employers.html",
    "candidates": "candidates.html",
    "how_it_works": "how-it-works.html",
    "contact": "contact.html",
    "privacy": "privacy.html",
    "terms": "terms.html",
    "signin": "signin.html",
    "signup": "signup.html",
}

PER_PAGE = 20  # rows per page across all paginated tables


def paginate(request, queryset, per_page=PER_PAGE):
    """Return a Page object for *queryset* based on ?page= param."""
    paginator = Paginator(queryset, per_page)
    page_num  = request.GET.get("page", 1)
    try:
        return paginator.page(page_num)
    except PageNotAnInteger:
        return paginator.page(1)
    except EmptyPage:
        return paginator.page(paginator.num_pages)


def _unread_count(profile):
    """Return integer unread notification count for *profile*."""
    return profile.notifications.filter(is_read=False).count()


# ─────────────────────────────────────────────────────────────
# Public / auth views
# ─────────────────────────────────────────────────────────────

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
        return redirect(
            "website:candidate_dashboard"
            if role == Profile.Role.CANDIDATE
            else "website:employer_dashboard"
        )
    return render(request, "auth/signup.html", {"form": form, "role": role})


class SignInView(LoginView):
    template_name = "auth/signin.html"
    authentication_form = SignInForm
    redirect_authenticated_user = True

    def get_success_url(self):
        if self.request.user.is_staff or self.request.user.is_superuser:
            return "/dashboard/admin/"
        profile = getattr(self.request.user, "profile", None)
        if profile and profile.role == Profile.Role.EMPLOYER:
            return "/dashboard/employer/"
        return "/dashboard/candidate/"


def logout_view(request):
    from django.contrib.auth import logout
    logout(request)
    return redirect("website:signin")


# ─────────────────────────────────────────────────────────────
# Candidate helpers
# ─────────────────────────────────────────────────────────────

def _candidate_profile(request):
    return get_object_or_404(Profile, user=request.user, role=Profile.Role.CANDIDATE)


# ─────────────────────────────────────────────────────────────
# Candidate views
# ─────────────────────────────────────────────────────────────

@login_required
def candidate_dashboard(request):
    profile = _candidate_profile(request)
    return render(request, "dashboard/candidate/index.html", {
        "profile":        profile,
        "unread_count":   _unread_count(profile),
        "notifications":  profile.notifications.all()[:5],
        "matches":        profile.matches.filter(is_active=True)[:5],
    })


@login_required
def candidate_section(request, section):
    sections = {
        "profile": (
            "My Profile",
            "Keep your personal details and professional story current.",
            "Complete your profile to become more visible to the right employers.",
        ),
        "verification": (
            "Verification Status",
            "Track the review of your professional profile.",
            "Your information is reviewed by JobSPACE administrators before you enter the talent pool.",
        ),
        "matches": (
            "Opportunities / Matches",
            "See opportunities selected for you by JobSPACE administrators.",
            "Candidates cannot browse or contact employers directly. Only approved matches appear here.",
        ),
        "jobs": (
            "Opportunities / Matches",
            "See opportunities selected for you by JobSPACE administrators.",
            "Candidates cannot browse or contact employers directly. Only approved matches appear here.",
        ),
        "applications": (
            "Applications",
            "Track applications created through an administrator-approved match.",
            "Application updates will appear here when an administrator advances your match.",
        ),
        "notifications": (
            "Notifications",
            "See profile updates, matches, and important reminders.",
            "Your latest JobSpace activity will appear here.",
        ),
    }
    if section not in sections:
        raise Http404

    title, description, detail = sections[section]
    profile = _candidate_profile(request)

    if section == "profile":
        return _candidate_profile_edit(request, profile, title, description)

    if section == "verification":
        return render(request, "dashboard/candidate/verification.html", {
            "profile":      profile,
            "unread_count": _unread_count(profile),
        })

    if section in {"matches", "jobs"}:
        matches_qs = profile.matches.filter(is_active=True).select_related("employer")
        return render(request, "dashboard/candidate/matches.html", {
            "profile":      profile,
            "unread_count": _unread_count(profile),
            "page_obj":     paginate(request, matches_qs),
        })

    if section == "notifications":
        # Mark all unread as read, then paginate
        profile.notifications.filter(is_read=False).update(is_read=True)
        notifications_qs = profile.notifications.all()
        return render(request, "dashboard/candidate/notifications.html", {
            "profile":      profile,
            "unread_count": 0,
            "page_obj":     paginate(request, notifications_qs, per_page=15),
        })

    # Fallback generic section
    return render(request, "dashboard/candidate/section.html", {
        "section":             section,
        "section_title":       title,
        "section_description": description,
        "section_detail":      detail,
        "profile":             profile,
        "unread_count":        _unread_count(profile),
    })


@login_required
def candidate_documents_legacy(request):
    return redirect("website:candidate_section", section="profile")


def _candidate_profile_edit(request, profile, title, description):
    is_post       = request.method == "POST"
    form          = CandidateProfileForm(request.POST if is_post else None, instance=profile)
    document_form = (
        CandidateDocumentForm(request.POST, request.FILES)
        if request.FILES
        else CandidateDocumentForm()
    )
    document_is_valid = not request.FILES or document_form.is_valid()

    # Map each form field → wizard step so errors can jump back to the right step
    FIELD_STEP_MAP = {
        "legal_name": 1, "email": 1, "phone": 1, "whatsapp_number": 1, "address": 1,
        "specializations": 2, "custom_specialization": 2,
        "primary_degree": 3, "certifications": 3, "software_competencies": 3,
        "equipment_competencies": 3,
        "professional_pitch": 4, "expected_salary": 4, "availability": 4,
        "file": 4,
    }

    error_step = None
    cv_required_error = None

    if is_post:
        form_is_valid = form.is_valid()
        # CV is required on first completion: must upload one OR already have one
        has_existing_cv = profile.cv_documents.exists()
        if not request.FILES and not has_existing_cv:
            cv_required_error = "Upload your CV (PDF or DOCX, max 5 MB) to complete your profile."
            document_is_valid = False

        if form_is_valid and document_is_valid:
            form.save()
            if request.FILES:
                document = document_form.save(commit=False)
                document.profile = profile
                document.save()
                profile.notify(
                    title="CV uploaded successfully",
                    message="Your latest CV has been saved and is ready for administrator review.",
                    kind=Notification.Kind.PROFILE,
                )
            profile.notify(
                title="Professional profile completed",
                message="Your professional profile has been completed and saved. You can now submit it for verification.",
                kind=Notification.Kind.PROFILE,
            )
            messages.success(request, "Professional profile has been completed.")
            return redirect(f"{request.path}?completed=1")

        # ── Validation failed: find first error step ──
        error_fields = list(form.errors.keys())
        if cv_required_error or document_form.errors:
            error_fields.append("file")
        for field in error_fields:
            step = FIELD_STEP_MAP.get(field)
            if step is not None and (error_step is None or step < error_step):
                error_step = step
        if error_step is None:
            error_step = 1
        messages.error(
            request,
            f"Some required fields are missing — please complete Step {error_step} to continue.",
        )

    return render(request, "dashboard/candidate/profile.html", {
        "profile":             profile,
        "form":                form,
        "document_form":       document_form,
        "documents":           profile.cv_documents.all(),
        "section_title":       title,
        "section_description": description,
        "unread_count":        _unread_count(profile),
        "error_step":          error_step,
        "cv_required_error":   cv_required_error,
        "profile_completed":   request.GET.get("completed") == "1" and not is_post,
    })


@login_required
def add_specialization(request):
    """AJAX-friendly POST: create a new Specialization (if unique) and attach it to the candidate profile."""
    if request.method != "POST":
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(["POST"])

    profile = _candidate_profile(request)
    raw     = request.POST.get("name", "").strip()

    if not raw:
        from django.http import JsonResponse
        return JsonResponse({"ok": False, "error": "Name cannot be empty."}, status=400)

    if len(raw) > 120:
        from django.http import JsonResponse
        return JsonResponse({"ok": False, "error": "Name is too long (max 120 characters)."}, status=400)

    # Build a slug from the name
    from django.utils.text import slugify
    slug = slugify(raw)
    if not slug:
        from django.http import JsonResponse
        return JsonResponse({"ok": False, "error": "Invalid name — please use letters and numbers."}, status=400)

    spec, _ = Specialization.objects.get_or_create(
        slug=slug,
        defaults={"name": raw.title()},
    )
    profile.specializations.add(spec)

    from django.http import JsonResponse
    return JsonResponse({"ok": True, "id": spec.pk, "name": spec.name, "slug": spec.slug})


@login_required
def submit_candidate_profile(request):
    profile = _candidate_profile(request)
    if profile.verification_status in {
        Profile.VerificationStatus.PENDING,
        Profile.VerificationStatus.VERIFYING,
        Profile.VerificationStatus.VERIFIED,
    }:
        messages.info(request, "Your profile has already been submitted for review.")
    else:
        profile.verification_status = Profile.VerificationStatus.PENDING
        profile.submitted_at        = timezone.now()
        profile.verification_notes  = ""
        profile.save(update_fields=["verification_status", "submitted_at", "verification_notes", "updated_at"])
        profile.notify(
            title="Profile submitted for review",
            message="Your professional profile has been submitted for vetting. We'll notify you once our team begins the review process.",
            kind=Notification.Kind.VERIFICATION,
        )
        messages.success(request, "Your profile is now pending review.")
    return redirect("website:candidate_dashboard")


# ─────────────────────────────────────────────────────────────
# Employer helpers
# ─────────────────────────────────────────────────────────────

def _employer_profile(request):
    return get_object_or_404(Profile, user=request.user, role=Profile.Role.EMPLOYER)


# ─────────────────────────────────────────────────────────────
# Employer views
# ─────────────────────────────────────────────────────────────

@login_required
def employer_dashboard(request):
    employer = _employer_profile(request)
    return render(request, "dashboard/employer/index.html", {
        "employer":      employer,
        "unread_count":  _unread_count(employer),
        "subscription":  employer.subscriptions.filter(is_active=True).first(),
        "requests":      employer.recruitment_requests.order_by("-created_at")[:5],
        "matches":       employer.candidate_matches.filter(is_active=True)[:5],
        "notifications": employer.notifications.all()[:5],
    })


@login_required
def employer_section(request, section):
    employer = _employer_profile(request)
    unread   = _unread_count(employer)

    # ── Profile ──────────────────────────────────────────────
    if section == "profile":
        # Capture completeness BEFORE the bound form is validated: ModelForm's
        # _post_clean() writes the submitted values onto this same instance, so
        # reading it after is_valid() would always report the NEW state.
        was_complete = employer.employer_profile_complete

        form = EmployerProfileForm(request.POST or None, instance=employer)
        if request.method == "POST" and form.is_valid():
            form.save()
            employer.refresh_from_db()
            now_complete = employer.employer_profile_complete

            if now_complete and not was_complete:
                messages.success(
                    request,
                    "Company profile completed. Let's post your first recruitment request.",
                )
                url = reverse("website:employer_section", kwargs={"section": "profile"})
                return redirect(f"{url}?completed=1")

            messages.success(request, "Company profile updated.")
            return redirect("website:employer_section", section="profile")

        return render(request, "dashboard/employer/profile.html", {
            "employer":      employer,
            "form":          form,
            "unread_count":  unread,
            "section_title": "Company Profile",
            # ?completed=1 → show the celebration modal, then move the user on
            # to the recruitment request page.
            "just_completed": request.GET.get("completed") == "1"
                              and employer.employer_profile_complete,
        })

    # ── Recruitment requests ──────────────────────────────────
    if section == "requests":
        form = RecruitmentRequestForm(request.POST or None)
        submitted = None

        if request.method == "POST" and form.is_valid():
            req          = form.save(commit=False)
            req.employer = employer
            req.save()
            employer.notify(
                title="Recruitment request submitted",
                message=f"Your request for {req.position} has been submitted and is under review by JobSPACE administrators.",
                kind=Notification.Kind.SYSTEM,
            )
            messages.success(request, "Recruitment request submitted.")
            # Redirect (POST/redirect/GET) and tag the URL so the page can open the
            # confirmation modal for exactly this request.
            url = reverse("website:employer_section", kwargs={"section": "requests"})
            return redirect(f"{url}?submitted={req.pk}")

        requests_qs = employer.recruitment_requests.order_by("-created_at")

        # ?submitted=<pk> → render the confirmation modal (validated against this
        # employer so a hand-edited URL can't expose another company's request).
        submitted_id = request.GET.get("submitted")
        if submitted_id and submitted_id.isdigit():
            submitted = employer.recruitment_requests.filter(pk=int(submitted_id)).first()

        return render(request, "dashboard/employer/requests.html", {
            "employer":         employer,
            "form":             form,
            "unread_count":     unread,
            "page_obj":         paginate(request, requests_qs),
            "section_title":    "Recruitment Requests",
            "other_choice":     RecruitmentRequestForm.OTHER,
            "submitted_request": submitted,
        })

    # ── Candidates received ───────────────────────────────────
    if section == "candidates":
        matches_qs = employer.candidate_matches.filter(is_active=True).select_related("profile")
        return render(request, "dashboard/employer/candidates.html", {
            "employer":      employer,
            "unread_count":  unread,
            "page_obj":      paginate(request, matches_qs),
            "section_title": "Candidates Received",
        })

    # ── Shortlist ─────────────────────────────────────────────
    if section == "shortlist":
        shortlists_qs = employer.shortlists.select_related("candidate")
        return render(request, "dashboard/employer/shortlist.html", {
            "employer":      employer,
            "unread_count":  unread,
            "page_obj":      paginate(request, shortlists_qs),
            "section_title": "Shortlisted Candidates",
        })

    # ── Subscription ──────────────────────────────────────────
    if section == "subscription":
        active = employer.subscriptions.filter(is_active=True).first()
        return render(request, "dashboard/employer/subscription.html", {
            "employer":      employer,
            "unread_count":  unread,
            "subscription":  active,
            "payments":      employer.payments.order_by("-paid_at"),
            "section_title": "Subscription",
        })

    # ── Payments ──────────────────────────────────────────────
    if section == "payments":
        payments_qs = employer.payments.order_by("-paid_at")
        return render(request, "dashboard/employer/payments.html", {
            "employer":      employer,
            "unread_count":  unread,
            "page_obj":      paginate(request, payments_qs),
            "section_title": "Payments",
        })

    # ── Notifications ─────────────────────────────────────────
    if section == "notifications":
        employer.notifications.filter(is_read=False).update(is_read=True)
        notifs_qs = employer.notifications.all()
        return render(request, "dashboard/employer/notifications.html", {
            "employer":      employer,
            "unread_count":  0,
            "page_obj":      paginate(request, notifs_qs, per_page=15),
            "section_title": "Notifications",
        })

    # ── Support / Settings fallback ───────────────────────────
    if section in {"support", "settings"}:
        return render(request, "dashboard/employer/section.html", {
            "employer":      employer,
            "unread_count":  unread,
            "section_title": section.title(),
            "section_detail": "Contact JobSPACE support for help with your account and recruitment workflow.",
        })

    raise Http404


@login_required
def accept_candidate(request, match_id):
    """POST — employer formally accepts a matched candidate.
    Sets is_accepted=True on the match, notifies admin and the candidate."""
    if request.method != "POST":
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(["POST"])

    employer = _employer_profile(request)
    match    = get_object_or_404(
        CandidateMatch.objects.select_related("profile__user", "request"),
        pk=match_id, employer=employer, is_active=True,
    )

    if match.is_accepted:
        return JsonResponse({"ok": True, "already": True})

    match.is_accepted = True
    match.accepted_at = timezone.now()
    match.save(update_fields=["is_accepted", "accepted_at"])

    candidate_name = (
        match.profile.legal_name
        or match.profile.user.get_full_name()
        or match.profile.user.username
    )
    position = match.request.position if match.request else "the position"

    # Notify the candidate
    match.profile.notify(
        title="An employer has accepted your profile",
        message=(
            f"{employer.company_name or 'An employer'} has accepted your profile "
            f"for {position}. JobSPACE will be in touch to coordinate next steps."
        ),
        kind=Notification.Kind.MATCH,
    )

    # Notify admin
    from .models import Notification as Notif
    Notif.objects.create(
        profile=employer,          # attach to employer so admin sees it in platform feed
        title="Employer accepted a candidate",
        message=(
            f"{employer.company_name or employer.user.username} accepted "
            f"{candidate_name} for {position}. Please coordinate the next steps."
        ),
        kind=Notif.Kind.MATCH,
    )

    AuditLog.objects.create(
        actor=request.user,
        action="Employer accepted candidate",
        subject=f"{employer.company_name} accepted {candidate_name} for {position}",
    )

    return JsonResponse({"ok": True, "accepted_at": match.accepted_at.strftime("%d %b %Y")})


@login_required
def employer_candidate_detail(request, match_id):
    """GET — returns a candidate's professional profile as JSON for the
    employer detail modal. Contact information (phone, whatsapp, email,
    address) is intentionally excluded so employers must go through
    JobSPACE to reach the candidate."""
    employer = _employer_profile(request)
    match    = get_object_or_404(
        CandidateMatch.objects.select_related("profile__user")
                              .prefetch_related("profile__specializations",
                                                "profile__qualifications",
                                                "profile__cv_documents"),
        pk=match_id, employer=employer, is_active=True,
    )
    p = match.profile

    name    = p.legal_name or p.user.get_full_name() or p.user.username
    specs   = [s.name for s in p.specializations.all()]
    quals   = [
        {"title": q.title, "institution": q.institution or "", "year": q.year or ""}
        for q in p.qualifications.order_by("-year")
    ]
    has_cv  = p.cv_documents.exists()

    return JsonResponse({
        "name":                 name,
        "avatar":               name[:2].upper(),
        "verification_status":  p.get_verification_status_display(),
        "is_verified":          p.verification_status == Profile.VerificationStatus.VERIFIED,
        # Professional fields
        "specializations":      specs,
        "primary_degree":       p.primary_degree or "",
        "certifications":       p.certifications or "",
        "software_competencies": p.software_competencies or "",
        "equipment_competencies": p.equipment_competencies or "",
        "professional_pitch":   p.professional_pitch or "",
        # Salary & availability — visible to employer
        "expected_salary":      f"₦{p.expected_salary:,}/mo" if p.expected_salary else "",
        "availability":         p.get_availability_display() if p.availability else "",
        # Education history
        "qualifications":       quals,
        # CV presence (not the file itself)
        "has_cv":               has_cv,
        # Match metadata
        "matched_on":           match.created_at.strftime("%d %b %Y"),
        "is_accepted":          match.is_accepted,
        "accepted_at":          match.accepted_at.strftime("%d %b %Y") if match.accepted_at else None,
    })


@login_required
def shortlist_candidate(request, match_id):
    employer = _employer_profile(request)
    match    = get_object_or_404(CandidateMatch, pk=match_id, employer=employer, is_active=True)
    created  = Shortlist.objects.get_or_create(
        employer=employer, candidate=match.profile, match=match,
    )[1]  # [1] = created boolean

    if created:
        # Notify the candidate that they have been shortlisted
        match.profile.notify(
            title="You've been shortlisted!",
            message=f"Great news — {employer.company_name or 'an employer'} has added your profile to their private shortlist. This is a strong indication of interest.",
            kind=Notification.Kind.SHORTLIST,
        )

    messages.success(request, "Candidate added to your private shortlist.")
    return redirect("website:employer_section", section="candidates")


# ─────────────────────────────────────────────────────────────
# Flutterwave payment views
# ─────────────────────────────────────────────────────────────

PLAN_AMOUNTS = {
    Subscription.Plan.BASIC:   50_000,
    Subscription.Plan.PREMIUM: 100_000,
}


@login_required
def initiate_subscription(request):
    """POST — creates a pending Subscription + Payment row and returns the
    Flutterwave inline-JS config as JSON so the frontend can open the checkout."""
    if request.method != "POST":
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(["POST"])

    employer = _employer_profile(request)
    plan = request.POST.get("plan", Subscription.Plan.BASIC)
    if plan not in PLAN_AMOUNTS:
        return JsonResponse({"ok": False, "error": "Invalid plan."}, status=400)

    from django.conf import settings as django_settings
    public_key = django_settings.FLUTTERWAVE_PUBLIC_KEY
    if not public_key:
        return JsonResponse({"ok": False, "error": "Payment gateway not configured."}, status=503)

    amount = PLAN_AMOUNTS[plan]
    now    = timezone.now()
    import uuid
    tx_ref = f"JOBSPACE-{employer.pk}-{uuid.uuid4().hex[:12].upper()}"

    # Deactivate any in-progress pending payment for this employer (idempotent retry)
    Payment.objects.filter(
        employer=employer, status=Payment.Status.PENDING
    ).update(status=Payment.Status.FAILED)

    # Create a placeholder subscription (inactive until payment confirmed)
    subscription = Subscription.objects.create(
        employer=employer,
        plan=plan,
        amount=amount,
        starts_at=now,
        expires_at=now + timezone.timedelta(days=30),
        is_active=False,
    )
    Payment.objects.create(
        employer=employer,
        subscription=subscription,
        reference=tx_ref,
        amount=amount,
        status=Payment.Status.PENDING,
    )

    # Build the absolute callback URL
    callback_url = request.build_absolute_uri(
        reverse("website:subscription_callback")
    )

    return JsonResponse({
        "ok": True,
        "public_key": public_key,
        "tx_ref":     tx_ref,
        "amount":     amount,
        "currency":   "NGN",
        "email":      request.user.email,
        "name":       employer.company_name or request.user.get_full_name() or request.user.username,
        "phone":      employer.phone or "",
        "redirect_url": callback_url,
        "plan_label": subscription.get_plan_display(),
    })


@login_required
def subscription_callback(request):
    """GET — Flutterwave redirects here after the user pays (or cancels).
    We verify the transaction server-side and activate the subscription."""
    from django.conf import settings as django_settings
    import urllib.request
    import json as _json

    status     = request.GET.get("status", "")
    tx_ref     = request.GET.get("tx_ref", "")
    tx_id      = request.GET.get("transaction_id", "")

    employer   = _employer_profile(request)

    if status != "successful" or not tx_ref or not tx_id:
        messages.error(request, "Payment was not completed. Please try again.")
        return redirect("website:employer_section", section="subscription")

    # Look up the pending payment for this employer + reference
    try:
        payment = Payment.objects.select_related("subscription").get(
            reference=tx_ref, employer=employer, status=Payment.Status.PENDING
        )
    except Payment.DoesNotExist:
        messages.error(request, "Payment reference not found or already processed.")
        return redirect("website:employer_section", section="subscription")

    # Verify the transaction with Flutterwave REST API
    secret_key = django_settings.FLUTTERWAVE_SECRET_KEY
    try:
        req = urllib.request.Request(
            f"https://api.flutterwave.com/v3/transactions/{tx_id}/verify",
            headers={"Authorization": f"Bearer {secret_key}"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = _json.loads(resp.read().decode())
    except Exception:
        messages.error(request, "Could not verify payment with Flutterwave. Please contact support.")
        return redirect("website:employer_section", section="subscription")

    if (
        data.get("status") != "success"
        or data.get("data", {}).get("status") != "successful"
        or data["data"].get("tx_ref") != tx_ref
        or data["data"].get("amount") < payment.amount
        or data["data"].get("currency") != "NGN"
    ):
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=["status"])
        messages.error(request, "Payment verification failed. Please contact support.")
        return redirect("website:employer_section", section="subscription")

    # All checks passed — activate subscription
    now = timezone.now()
    payment.status = Payment.Status.SUCCESS
    payment.paid_at = now
    payment.save(update_fields=["status", "paid_at"])

    sub = payment.subscription
    sub.is_active  = True
    sub.starts_at  = now
    sub.expires_at = now + timezone.timedelta(days=30)
    sub.save(update_fields=["is_active", "starts_at", "expires_at"])

    # Deactivate any older subscriptions for this employer
    employer.subscriptions.exclude(pk=sub.pk).filter(is_active=True).update(is_active=False)

    employer.notify(
        title="Subscription activated",
        message=(
            f"Your {sub.get_plan_display()} plan is now active and expires on "
            f"{sub.expires_at.strftime('%d %b %Y')}. "
            f"Payment reference: {payment.reference}."
        ),
        kind=Notification.Kind.PAYMENT,
    )
    messages.success(
        request,
        f"Payment successful! Your {sub.get_plan_display()} plan is now active."
    )
    return redirect("website:employer_section", section="subscription")


from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def subscription_webhook(request):
    """POST — Flutterwave server-side webhook for async payment confirmation.
    Verifies the secret hash header before processing."""
    from django.conf import settings as django_settings
    import json as _json

    if request.method != "POST":
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(["POST"])

    # Authenticate the webhook using the verif-hash header
    secret_hash = django_settings.FLUTTERWAVE_WEBHOOK_HASH
    received_hash = request.headers.get("verif-hash", "")
    if secret_hash and received_hash != secret_hash:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Invalid webhook signature.")

    try:
        payload = _json.loads(request.body)
    except ValueError:
        from django.http import HttpResponseBadRequest
        return HttpResponseBadRequest("Invalid JSON.")

    event = payload.get("event", "")
    data  = payload.get("data", {})

    if event == "charge.completed" and data.get("status") == "successful":
        tx_ref = data.get("tx_ref", "")
        try:
            payment = Payment.objects.select_related("subscription", "employer").get(
                reference=tx_ref, status=Payment.Status.PENDING
            )
        except Payment.DoesNotExist:
            # Already processed (by callback) or unknown ref — idempotent, just 200.
            from django.http import HttpResponse
            return HttpResponse(status=200)

        now = timezone.now()
        payment.status  = Payment.Status.SUCCESS
        payment.paid_at = now
        payment.save(update_fields=["status", "paid_at"])

        sub = payment.subscription
        if sub:
            sub.is_active  = True
            sub.starts_at  = now
            sub.expires_at = now + timezone.timedelta(days=30)
            sub.save(update_fields=["is_active", "starts_at", "expires_at"])
            payment.employer.subscriptions.exclude(pk=sub.pk).filter(is_active=True).update(is_active=False)

    from django.http import HttpResponse
    return HttpResponse(status=200)


# ─────────────────────────────────────────────────────────────
# Admin views
# ─────────────────────────────────────────────────────────────

@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def admin_dashboard(request):
    context = {
        "candidates":         Profile.objects.filter(role=Profile.Role.CANDIDATE),
        "employers":          Profile.objects.filter(role=Profile.Role.EMPLOYER),
        "pending_candidates": Profile.objects.filter(
            role=Profile.Role.CANDIDATE,
            verification_status__in=[
                Profile.VerificationStatus.PENDING,
                Profile.VerificationStatus.VERIFYING,
            ],
        ),
        "verified_candidates": Profile.objects.filter(
            role=Profile.Role.CANDIDATE,
            verification_status=Profile.VerificationStatus.VERIFIED,
        ),
        "active_subscriptions": Subscription.objects.filter(is_active=True),
        "requests":  RecruitmentRequest.objects.select_related("employer").order_by("-created_at"),
        "matches":   CandidateMatch.objects.filter(is_active=True),
        # Candidates an employer has formally accepted. Surfaced on the admin
        # dashboard so the team can act on them (arrange interviews, etc.)
        # instead of having to open the matching workspace to find them.
        "accepted_matches": (
            CandidateMatch.objects
            .filter(is_active=True, is_accepted=True)
            .select_related("profile__user", "employer__user", "request")
            .order_by("-accepted_at")
        ),
        "accepted_count": CandidateMatch.objects.filter(is_active=True, is_accepted=True).count(),
        "payments":  Payment.objects.select_related("employer", "subscription").order_by("-paid_at"),
        "recent_candidates": Profile.objects.filter(role=Profile.Role.CANDIDATE).order_by("-user__date_joined")[:5],
        "recent_employers":  Profile.objects.filter(role=Profile.Role.EMPLOYER).order_by("-user__date_joined")[:5],
        "logs":      AuditLog.objects.select_related("actor")[:10],
        # Admin staff don't have Profile rows, so unread_count = 0
        "unread_count": 0,
    }
    return render(request, "dashboard/admin/index.html", context)


@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def admin_section(request, section):

    # ── Candidates ────────────────────────────────────────────
    if section == "candidates":
        qs = (
            Profile.objects
            .filter(role=Profile.Role.CANDIDATE)
            .prefetch_related("specializations", "cv_documents")
            .order_by("-user__date_joined")
        )
        return render(request, "dashboard/admin/candidates.html", {
            "page_obj":     paginate(request, qs),
            "unread_count": 0,
        })

    # ── Employers ─────────────────────────────────────────────
    if section == "employers":
        qs = Profile.objects.filter(role=Profile.Role.EMPLOYER).order_by("-user__date_joined")
        return render(request, "dashboard/admin/employers.html", {
            "page_obj":     paginate(request, qs),
            "unread_count": 0,
        })

    # ── Recruitment requests ──────────────────────────────────
    if section == "requests":
        qs = RecruitmentRequest.objects.select_related("employer").order_by("-created_at")
        return render(request, "dashboard/admin/requests.html", {
            "page_obj":     paginate(request, qs),
            "unread_count": 0,
        })

    # ── Talent pool ───────────────────────────────────────────
    if section == "talent-pool":
        qs = (
            Profile.objects
            .filter(role=Profile.Role.CANDIDATE, verification_status=Profile.VerificationStatus.VERIFIED)
            .prefetch_related("specializations")
        )
        return render(request, "dashboard/admin/talent_pool.html", {
            "page_obj":     paginate(request, qs),
            "unread_count": 0,
        })

    # ── Matching ──────────────────────────────────────────────
    if section == "matching":
        # Requests that still need candidates. Annotated with how many are
        # already matched so the admin can see outstanding slots at a glance.
        requests_qs = (
            RecruitmentRequest.objects
            .exclude(status=RecruitmentRequest.Status.COMPLETED)
            .select_related("employer__user")
            .annotate(matched_total=Count("matches", filter=Q(matches__is_active=True)))
            .order_by("-created_at")
        )

        # Optional ?request=<pk> focuses the workspace on one request.
        selected_request = None
        request_id = request.GET.get("request")
        if request_id and request_id.isdigit():
            selected_request = next(
                (r for r in requests_qs if r.pk == int(request_id)), None
            )

        # Verified candidates only — nobody else may be pushed to an employer.
        candidates_qs = (
            Profile.objects
            .filter(role=Profile.Role.CANDIDATE,
                    verification_status=Profile.VerificationStatus.VERIFIED)
            .select_related("user")
            .prefetch_related("specializations", "qualifications", "cv_documents")
            .order_by("-user__date_joined")
        )

        # Rank candidates against the selected request so the best fit is first.
        ranked = []
        already_matched = set()
        if selected_request:
            already_matched = set(
                selected_request.matches
                .filter(is_active=True)
                .values_list("profile_id", flat=True)
            )
            for cand in candidates_qs:
                score, reasons = _match_score(cand, selected_request)
                ranked.append({
                    "profile": cand,
                    "score": score,
                    "reasons": reasons,
                    "matched": cand.pk in already_matched,
                })
            ranked.sort(key=lambda row: (row["matched"], -row["score"]))

        return render(request, "dashboard/admin/matching.html", {
            "requests":         requests_qs,
            "candidates":       candidates_qs,
            "ranked":           ranked,
            "selected_request": selected_request,
            "recent_matches":   (
                CandidateMatch.objects
                .filter(is_active=True, request__isnull=False)
                .select_related("profile__user", "employer__user", "request")
                .order_by("-created_at")[:15]
            ),
            "unread_count": 0,
        })

    # ── Subscriptions ─────────────────────────────────────────
    if section == "subscriptions":
        qs = Subscription.objects.select_related("employer").order_by("-starts_at")
        return render(request, "dashboard/admin/subscriptions.html", {
            "page_obj":     paginate(request, qs),
            "unread_count": 0,
        })

    # ── Payments ──────────────────────────────────────────────
    if section == "payments":
        qs = Payment.objects.select_related("employer", "subscription").order_by("-paid_at")
        return render(request, "dashboard/admin/payments.html", {
            "page_obj":     paginate(request, qs),
            "unread_count": 0,
        })

    # ── Replacements ──────────────────────────────────────────
    if section == "replacements":
        qs = ReplacementRequest.objects.select_related("employer", "candidate")
        return render(request, "dashboard/admin/replacements.html", {
            "page_obj":     paginate(request, qs),
            "unread_count": 0,
        })

    # ── Notifications (admin view of ALL notifications) ───────
    if section == "notifications":
        Notification.objects.filter(is_read=False).update(is_read=True)
        qs = Notification.objects.select_related("profile").all()
        return render(request, "dashboard/admin/notifications.html", {
            "page_obj":     paginate(request, qs, per_page=25),
            "unread_count": 0,
        })

    # ── Reports ───────────────────────────────────────────────
    if section == "reports":
        return render(request, "dashboard/admin/reports.html", {
            "candidates": Profile.objects.filter(role=Profile.Role.CANDIDATE),
            "verified":   Profile.objects.filter(verification_status=Profile.VerificationStatus.VERIFIED),
            "employers":  Profile.objects.filter(role=Profile.Role.EMPLOYER),
            "requests":   RecruitmentRequest.objects.all(),
            "matches":    CandidateMatch.objects.filter(is_active=True),
            "payments":   Payment.objects.filter(status=Payment.Status.SUCCESS),
            "unread_count": 0,
        })

    # ── Activity logs ─────────────────────────────────────────
    if section == "logs":
        qs = AuditLog.objects.select_related("actor").order_by("-created_at")
        return render(request, "dashboard/admin/logs.html", {
            "page_obj":     paginate(request, qs),
            "unread_count": 0,
        })

    # ── Settings ──────────────────────────────────────────────
    if section == "settings":
        return render(request, "dashboard/admin/settings.html", {"unread_count": 0})

    raise Http404


# ─────────────────────────────────────────────────────────────
# Admin — matching engine
# ─────────────────────────────────────────────────────────────

_STOP_WORDS = {
    "and", "or", "with", "for", "the", "of", "in", "to", "a", "an",
    "years", "year", "experience", "required", "must", "good", "knowledge",
}


def _tokens(value):
    """Split free text into comparable lowercase tokens."""
    if not value:
        return []
    cleaned = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in str(value))
    return [t for t in cleaned.lower().split() if t and t not in _STOP_WORDS and len(t) > 1]


def _match_score(candidate, req):
    """Rank *candidate* against recruitment request *req*.

    Returns (score, reasons) where score is a 0-100 relevance number and
    reasons is a short, human-readable explanation shown in the admin UI.
    """
    score = 0
    reasons = []

    # ── Specialization / position alignment (heaviest signal, 40 pts) ──
    spec_names = " ".join(s.name for s in candidate.specializations.all())
    pos_tokens = _tokens(req.position)
    spec_tokens = set(_tokens(spec_names))

    if pos_tokens and spec_tokens:
        overlap = spec_tokens.intersection(pos_tokens)
        if overlap:
            score += 40
            reasons.append("Specialization matches: " + ", ".join(sorted(overlap)))
        else:
            # Partial credit when a token of the position appears in the specs.
            if any(tok in " ".join(spec_tokens) for tok in pos_tokens):
                score += 20
                reasons.append("Specialization partially matches the position")

    # ── Required skills overlap (25 pts) ──
    req_skills = set(_tokens(req.required_skills))
    if req_skills:
        cand_skills = set(_tokens(
            " ".join([
                candidate.software_competencies or "",
                candidate.equipment_competencies or "",
                candidate.professional_pitch or "",
            ])
        ))
        shared = req_skills.intersection(cand_skills)
        if shared:
            score += min(25, 10 * len(shared))
            reasons.append("Shares required skill: " + ", ".join(sorted(shared)[:3]))

    # ── Profile completeness as a confidence signal (up to 15 pts) ──
    score += round(candidate.completion_percentage * 0.15)

    # ── Availability (10 pts) ──
    if candidate.availability == Profile.Availability.IMMEDIATE:
        score += 10
        reasons.append("Available immediately")
    elif candidate.availability:
        score += 5

    # ── Has a CV on file (10 pts) ──
    if candidate.cv_documents.exists():
        score += 10
        reasons.append("CV on file")

    # ── Expected salary within / near the employer's band (bonus) ──
    if candidate.expected_salary:
        if req.salary_min <= candidate.expected_salary <= req.salary_max:
            score += 10
            reasons.append("Salary expectation within the offered range")
        elif candidate.expected_salary <= req.salary_max:
            score += 5

    return min(score, 100), reasons


def _employer_context(employer):
    """Counts + active plan used by the admin employer-detail modal."""
    active_sub = employer.subscriptions.filter(is_active=True).first()
    open_requests = employer.recruitment_requests.exclude(
        status=RecruitmentRequest.Status.COMPLETED
    )
    active_matches = employer.candidate_matches.filter(is_active=True)
    return {
        "plan":         active_sub.get_plan_display() if active_sub else "No active plan",
        "plan_expires": active_sub.expires_at.strftime("%d %b %Y") if active_sub else "—",
        "requests_total": open_requests.count(),
        "matches_total":  active_matches.count(),
        "shortlists":     employer.shortlists.count(),
        "payments":       employer.payments.count(),
    }


@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def admin_employer_detail(request, profile_id):
    """JSON payload of every employer field, for the matching-page modal."""
    employer = get_object_or_404(
        Profile.objects.select_related("user"), pk=profile_id, role=Profile.Role.EMPLOYER
    )
    ctx = _employer_context(employer)

    return JsonResponse({
        "name":         employer.company_name or employer.user.username,
        "legal_name":   employer.legal_name or "—",
        "user_name":    employer.user.get_full_name() or employer.user.username,
        "email":        employer.user.email or "—",
        "phone":        employer.phone or "—",
        "whatsapp":     employer.whatsapp_number or "—",
        "industry":     employer.industry_sector or "—",
        "hr_contact":   employer.hr_contact_name or "—",
        "address":      employer.office_address or "—",
        "joined":       employer.user.date_joined.strftime("%d %b %Y"),
        "last_login":   employer.user.last_login.strftime("%d %b %Y") if employer.user.last_login else "Never",
        "status":       "Active" if employer.user.is_active else "Inactive",
        "plan":         ctx["plan"],
        "plan_expires": ctx["plan_expires"],
        "requests_total": ctx["requests_total"],
        "matches_total":  ctx["matches_total"],
        "shortlists":     ctx["shortlists"],
        "payments":       ctx["payments"],
    })


def _matching_redirect(request, req_obj, notice):
    """Back to the matching workspace, focused on the request just acted on."""
    messages.success(request, notice)
    url = reverse("website:admin_section", kwargs={"section": "matching"})
    return redirect(f"{url}?request={req_obj.pk}")


@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def create_match(request):
    """POST — match a verified candidate to an employer's recruitment request."""
    if request.method != "POST":
        return redirect("website:admin_section", section="matching")

    req_obj = get_object_or_404(
        RecruitmentRequest.objects.select_related("employer__user"), pk=request.POST.get("request")
    )
    candidate = get_object_or_404(
        Profile.objects.select_related("user"),
        pk=request.POST.get("candidate"),
        role=Profile.Role.CANDIDATE,
    )

    if req_obj.status == RecruitmentRequest.Status.COMPLETED:
        messages.error(request, "That request is already completed.")
        return _matching_redirect(request, req_obj, "")

    # Only vetted candidates may be introduced to an employer.
    if candidate.verification_status != Profile.VerificationStatus.VERIFIED:
        messages.error(
            request,
            f"{_candidate_label(candidate)} is not verified yet — verify the profile before matching.",
        )
        return _matching_redirect(request, req_obj, "")

    # Don't exceed the number of professionals the employer asked for.
    if req_obj.is_fully_matched:
        messages.error(
            request,
            f"All {req_obj.professionals_required} slot(s) for this request are already filled.",
        )
        return _matching_redirect(request, req_obj, "")

    employer_name = req_obj.employer.company_name or req_obj.employer.user.username
    match, created = CandidateMatch.objects.get_or_create(
        employer=req_obj.employer,
        profile=candidate,
        request=req_obj,
        defaults={"note": request.POST.get("note", "").strip()},
    )

    if not created:
        messages.warning(
            request,
            f"{_candidate_label(candidate)} is already matched to this request.",
        )
        return _matching_redirect(request, req_obj, "")

    req_obj.sync_status()

    AuditLog.objects.create(
        actor=request.user,
        action="Candidate matched to request",
        subject=f"{_candidate_label(candidate)} -> {employer_name} ({req_obj.position})",
    )
    req_obj.employer.notify(
        title="A new candidate is available for your request",
        message=(
            f"{_candidate_label(candidate)} has been matched to your "
            f"{req_obj.position} requirement. Log in to review the profile."
        ),
        kind=Notification.Kind.MATCH,
    )
    candidate.notify(
        title="A new opportunity was matched to you",
        message=(
            f"Your verified profile has been matched to a {req_obj.position} "
            f"opportunity at {employer_name}."
        ),
        kind=Notification.Kind.MATCH,
    )

    return _matching_redirect(
        request, req_obj,
        f"{_candidate_label(candidate)} matched to “{req_obj.position}” at {employer_name}.",
    )


@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def remove_match(request, match_id):
    """POST — withdraw a match and roll the request status back."""
    if request.method != "POST":
        return redirect("website:admin_section", section="matching")

    match = get_object_or_404(
        CandidateMatch.objects.select_related("profile__user", "employer__user", "request"),
        pk=match_id,
        is_active=True,
    )
    req_obj = match.request
    label   = _candidate_label(match.profile)
    employer_name = match.employer.company_name or match.employer.user.username

    match.is_active = False
    match.save(update_fields=["is_active"])

    if req_obj:
        req_obj.sync_status()

    AuditLog.objects.create(
        actor=request.user,
        action="Candidate match withdrawn",
        subject=f"{label} -> {employer_name}" + (f" ({req_obj.position})" if req_obj else ""),
    )
    match.employer.notify(
        title="A candidate match was withdrawn",
        message=f"{label} is no longer available for your request. Please review your candidate list again.",
        kind=Notification.Kind.MATCH,
    )
    match.profile.notify(
        title="An introduction was withdrawn",
        message=f"A previous match with {employer_name} has been withdrawn by the JobSPACE team.",
        kind=Notification.Kind.MATCH,
    )

    if req_obj:
        return _matching_redirect(request, req_obj, f"Match withdrawn for {label}.")
    messages.success(request, f"Match withdrawn for {label}.")
    return redirect("website:admin_section", section="matching")


@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def push_candidate(request, match_id):
    """Legacy endpoint: re-notify both sides about an existing match."""
    match = get_object_or_404(CandidateMatch, pk=match_id)
    AuditLog.objects.create(
        actor=request.user,
        action="Candidate profile pushed to employer",
        subject=f"{match.profile} -> {match.employer}",
    )
    # Notify employer
    match.employer.notify(
        title="A vetted candidate has been pushed to you",
        message="A professionally vetted candidate profile has been added to your Candidates Received list. Log in to review.",
        kind=Notification.Kind.MATCH,
    )
    # Notify candidate
    match.profile.notify(
        title="Your profile was shared with an employer",
        message=f"Your verified profile has been shared with {match.employer.company_name or 'an employer'}. You may be contacted soon through JobSPACE.",
        kind=Notification.Kind.MATCH,
    )
    return redirect("website:admin_section", section="matching")


# ─────────────────────────────────────────────────────────────
# Admin — candidate verification actions (verify / reject / revoke)
# ─────────────────────────────────────────────────────────────

def _admin_candidate_or_404(profile_id):
    return get_object_or_404(Profile, pk=profile_id, role=Profile.Role.CANDIDATE)


def _candidate_label(profile):
    return profile.legal_name or profile.user.get_full_name() or profile.user.username


@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def admin_verify_candidate(request, profile_id):
    """POST — mark a candidate as Vetted & Verified (adds them to the talent pool)."""
    if request.method != "POST":
        return redirect("website:admin_section", section="candidates")

    profile = _admin_candidate_or_404(profile_id)
    profile.verification_status = Profile.VerificationStatus.VERIFIED
    profile.verified_at         = timezone.now()
    profile.verification_notes  = ""
    profile.save(update_fields=["verification_status", "verified_at", "verification_notes", "updated_at"])

    profile.notify(
        title="Profile verified",
        message="Congratulations! Your professional profile has been vetted and verified by JobSPACE. You are now in the talent pool and can be matched with employers.",
        kind=Notification.Kind.VERIFICATION,
    )
    AuditLog.objects.create(
        actor=request.user,
        action="Candidate verified",
        subject=f"{_candidate_label(profile)} ({profile.user.email})",
    )
    messages.success(request, f"{_candidate_label(profile)} has been verified.")
    return redirect("website:admin_section", section="candidates")


@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def admin_reject_candidate(request, profile_id):
    """POST — reject a candidate. A reason is required and is shared with the candidate
    and with any employer holding a match for this candidate."""
    if request.method != "POST":
        return redirect("website:admin_section", section="candidates")

    profile = _admin_candidate_or_404(profile_id)
    reason  = request.POST.get("reason", "").strip()
    if not reason:
        messages.error(request, "Please type a reason before rejecting this candidate.")
        return redirect("website:admin_section", section="candidates")

    profile.verification_status = Profile.VerificationStatus.REJECTED
    profile.verification_notes  = reason
    profile.verified_at         = None
    profile.save(update_fields=["verification_status", "verification_notes", "verified_at", "updated_at"])

    profile.notify(
        title="Profile rejected",
        message=f"Your profile was rejected during verification. Reason: {reason} "
                "Please correct the highlighted issue and resubmit your profile for review.",
        kind=Notification.Kind.VERIFICATION,
    )
    # Let every employer who received this candidate know why they were rejected
    for match in profile.matches.select_related("employer").filter(is_active=True):
        match.employer.notify(
            title="A candidate in your list was rejected",
            message=f"{_candidate_label(profile)} was rejected during JobSPACE verification. "
                    f"Reason: {reason}",
            kind=Notification.Kind.VERIFICATION,
        )
    AuditLog.objects.create(
        actor=request.user,
        action="Candidate rejected",
        subject=f"{_candidate_label(profile)} ({profile.user.email}) — {reason}",
    )
    messages.success(request, f"{_candidate_label(profile)} has been rejected.")
    return redirect("website:admin_section", section="candidates")


@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def admin_revoke_verification(request, profile_id):
    """POST — revoke a previously granted verification. A reason is required; the
    candidate drops back to 'Requires Changes' with the reason attached."""
    if request.method != "POST":
        return redirect("website:admin_section", section="candidates")

    profile = _admin_candidate_or_404(profile_id)
    reason  = request.POST.get("reason", "").strip()
    if not reason:
        messages.error(request, "Please type a reason before revoking this verification.")
        return redirect("website:admin_section", section="candidates")

    profile.verification_status = Profile.VerificationStatus.CHANGES
    profile.verification_notes  = f"Verification revoked — {reason}"
    profile.verified_at         = None
    profile.save(update_fields=["verification_status", "verification_notes", "verified_at", "updated_at"])

    profile.notify(
        title="Verification revoked",
        message=f"Your verification has been revoked by JobSPACE. Reason: {reason} "
                "Please update your profile and resubmit it for review.",
        kind=Notification.Kind.VERIFICATION,
    )
    AuditLog.objects.create(
        actor=request.user,
        action="Candidate verification revoked",
        subject=f"{_candidate_label(profile)} ({profile.user.email}) — {reason}",
    )
    messages.success(request, f"Verification revoked for {_candidate_label(profile)}.")
    return redirect("website:admin_section", section="candidates")


# ─────────────────────────────────────────────────────────────
# Global dashboard search (powers the topbar search on all three dashboards)
# ─────────────────────────────────────────────────────────────

SEARCH_LIMIT = 8  # max records per result group


def _search_result(kind, title, subtitle, url, badge=""):
    # Coerce to plain strings so JsonResponse can never choke on a model instance.
    return {
        "kind":     str(kind),
        "title":    str(title or ""),
        "subtitle": str(subtitle or ""),
        "url":      str(url or ""),
        "badge":    str(badge or ""),
    }


def _candidate_search_results(profile, term):
    """Candidate portal: search their own profile, matches and notifications."""
    results = []

    # ── Employer matches ──
    matches = (
        profile.matches.filter(is_active=True)
        .select_related("employer")
        .filter(
            Q(employer__company_name__icontains=term)
            | Q(employer__industry_sector__icontains=term)
            | Q(employer__office_address__icontains=term)
            | Q(note__icontains=term)
        )[:SEARCH_LIMIT]
    )
    for match in matches:
        employer = match.employer
        results.append(_search_result(
            "match",
            employer.company_name or "Confidential Employer",
            employer.industry_sector or "Opportunity matched to you",
            "/dashboard/candidate/matches/",
        ))

    # ── Own profile details ──
    profile_fields = [
        ("Primary degree",      profile.primary_degree),
        ("Certifications",      profile.certifications),
        ("Software skills",     profile.software_competencies),
        ("Equipment skills",    profile.equipment_competencies),
        ("Professional pitch",  profile.professional_pitch),
    ]
    for label, value in profile_fields:
        if value and term.lower() in str(value).lower():
            results.append(_search_result(
                "profile", label, str(value)[:90],
                "/dashboard/candidate/profile/",
            ))

    for spec in profile.specializations.filter(name__icontains=term)[:SEARCH_LIMIT]:
        results.append(_search_result(
            "profile", f"Specialization — {spec.name}",
            "Update your professional profile",
            "/dashboard/candidate/profile/",
        ))

    # ── Notifications ──
    for note in profile.notifications.filter(
        Q(title__icontains=term) | Q(message__icontains=term)
    )[:SEARCH_LIMIT]:
        results.append(_search_result(
            "notification", note.title, note.message[:90],
            "/dashboard/candidate/notifications/",
        ))

    return results


def _employer_search_results(employer, term):
    """Employer portal: search received candidates, own requests, shortlist and notifications."""
    results = []

    # ── Candidates received ──
    matches = (
        employer.candidate_matches.filter(is_active=True)
        .select_related("profile__user")
        .prefetch_related("profile__specializations")
        .filter(
            Q(profile__legal_name__icontains=term)
            | Q(profile__user__email__icontains=term)
            | Q(profile__primary_degree__icontains=term)
            | Q(profile__software_competencies__icontains=term)
            | Q(profile__equipment_competencies__icontains=term)
        )[:SEARCH_LIMIT]
    )
    for match in matches:
        candidate = match.profile
        spec = candidate.specializations.first
        headline = (
            str(spec) if spec
            else (candidate.primary_degree or "Candidate profile")
        )
        results.append(_search_result(
            "candidate",
            _candidate_label(candidate),
            headline,
            "/dashboard/employer/candidates/",
            candidate.get_verification_status_display(),
        ))

    # ── Shortlisted candidates ──
    for entry in employer.shortlists.select_related("candidate").filter(
        Q(candidate__legal_name__icontains=term)
    )[:SEARCH_LIMIT]:
        results.append(_search_result(
            "shortlist", _candidate_label(entry.candidate),
            "On your shortlist", "/dashboard/employer/shortlist/", entry.status,
        ))

    # ── Own recruitment requests ──
    for req in employer.recruitment_requests.filter(
        Q(position__icontains=term)
        | Q(required_skills__icontains=term)
        | Q(minimum_qualification__icontains=term)
        | Q(certifications__icontains=term)
    )[:SEARCH_LIMIT]:
        results.append(_search_result(
            "request", req.position,
            f"{req.professionals_required} professional(s) · {req.get_status_display()}",
            "/dashboard/employer/requests/",
        ))

    # ── Notifications ──
    for note in employer.notifications.filter(
        Q(title__icontains=term) | Q(message__icontains=term)
    )[:SEARCH_LIMIT]:
        results.append(_search_result(
            "notification", note.title, note.message[:90],
            "/dashboard/employer/notifications/",
        ))

    return results


def _admin_search_results(term):
    """Admin portal: search candidates, employers, requests, matches, payments and logs."""
    results = []

    # ── Candidates ──
    candidates = (
        Profile.objects.filter(role=Profile.Role.CANDIDATE)
        .filter(
            Q(legal_name__icontains=term)
            | Q(user__email__icontains=term)
            | Q(user__username__icontains=term)
            | Q(phone__icontains=term)
            | Q(primary_degree__icontains=term)
            | Q(specializations__name__icontains=term)
        )
        .select_related("user")
        .distinct()[:SEARCH_LIMIT]
    )
    for candidate in candidates:
        results.append(_search_result(
            "candidate", _candidate_label(candidate),
            candidate.user.email,
            "/dashboard/admin/candidates/",
            candidate.get_verification_status_display(),
        ))

    # ── Employers ──
    employers = (
        Profile.objects.filter(role=Profile.Role.EMPLOYER)
        .filter(
            Q(company_name__icontains=term)
            | Q(user__email__icontains=term)
            | Q(industry_sector__icontains=term)
            | Q(hr_contact_name__icontains=term)
            | Q(office_address__icontains=term)
        )
        .select_related("user")
        .distinct()[:SEARCH_LIMIT]
    )
    for employer in employers:
        results.append(_search_result(
            "employer", employer.company_name or employer.user.username,
            employer.user.email,
            "/dashboard/admin/employers/",
        ))

    # ── Recruitment requests ──
    for req in (
        RecruitmentRequest.objects
        .filter(
            Q(position__icontains=term)
            | Q(employer__company_name__icontains=term)
            | Q(required_skills__icontains=term)
            | Q(minimum_qualification__icontains=term)
        )
        .select_related("employer")[:SEARCH_LIMIT]
    ):
        results.append(_search_result(
            "request", req.position,
            req.employer.company_name or req.employer.user.username,
            "/dashboard/admin/requests/",
            req.get_status_display(),
        ))

    # ── Matches ──
    for match in (
        CandidateMatch.objects
        .filter(
            Q(profile__legal_name__icontains=term)
            | Q(employer__company_name__icontains=term)
            | Q(note__icontains=term)
        )
        .select_related("profile", "employer")[:SEARCH_LIMIT]
    ):
        results.append(_search_result(
            "match",
            f"{_candidate_label(match.profile)} → "
            f"{match.employer.company_name or match.employer.user.username}",
            "Review or push this match",
            "/dashboard/admin/matching/",
        ))

    # ── Payments ──
    for payment in (
        Payment.objects
        .filter(
            Q(reference__icontains=term)
            | Q(employer__company_name__icontains=term)
        )
        .select_related("employer")[:SEARCH_LIMIT]
    ):
        results.append(_search_result(
            "payment", payment.reference,
            payment.employer.company_name or payment.employer.user.username,
            "/dashboard/admin/payments/",
            payment.get_status_display(),
        ))

    # ── Audit log ──
    for log in (
        AuditLog.objects
        .filter(Q(action__icontains=term) | Q(subject__icontains=term))
        .select_related("actor")[:SEARCH_LIMIT]
    ):
        results.append(_search_result(
            "log", log.action, log.subject or "—",
            "/dashboard/admin/logs/",
        ))

    return results


SEARCH_GROUP_LABELS = [
    ("candidate",    "Candidates"),
    ("employer",     "Employers"),
    ("match",        "Matches"),
    ("request",      "Recruitment Requests"),
    ("shortlist",    "Shortlist"),
    ("profile",      "Your Profile"),
    ("payment",      "Payments"),
    ("log",          "Activity Log"),
    ("notification", "Notifications"),
]


# ─────────────────────────────────────────────────────────────
# Notifications JSON API  (powers the bell dropdown on all dashboards)
# ─────────────────────────────────────────────────────────────

@login_required
def notifications_json(request):
    """GET — returns the latest 10 notifications for the bell dropdown.

    Admin sees the 10 most recent platform-wide unread notifications.
    Employer / candidate see their own profile notifications.
    Each item: id, title, message, kind, is_read, time_ago.
    """
    user = request.user

    KIND_ICONS = {
        "verification": "shield",
        "match":        "link",
        "shortlist":    "star",
        "payment":      "card",
        "profile":      "user",
        "system":       "bell",
    }

    def _fmt(notif):
        from django.utils.timesince import timesince
        return {
            "id":      notif.pk,
            "title":   notif.title,
            "message": notif.message[:120] + ("…" if len(notif.message) > 120 else ""),
            "kind":    notif.kind,
            "icon":    KIND_ICONS.get(notif.kind, "bell"),
            "is_read": notif.is_read,
            "time":    timesince(notif.created_at) + " ago",
        }

    try:
        if user.is_staff or user.is_superuser:
            qs = (
                Notification.objects
                .select_related("profile__user")
                .order_by("-created_at")[:10]
            )
        else:
            profile = getattr(user, "profile", None)
            if not profile:
                return JsonResponse({"notifications": [], "unread": 0})
            qs = profile.notifications.order_by("-created_at")[:10]

        items  = [_fmt(n) for n in qs]
        unread = sum(1 for n in items if not n["is_read"])
        return JsonResponse({"notifications": items, "unread": unread})
    except Exception:
        return JsonResponse({"notifications": [], "unread": 0})


@login_required
def notifications_mark_read(request):
    """POST — marks all (or specific) notifications as read.

    Body (optional): JSON {"ids": [1, 2, 3]}  → mark only those IDs.
    Without a body: mark ALL unread as read for this user.
    Returns: {"ok": true, "unread": 0}
    """
    if request.method != "POST":
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(["POST"])

    user = request.user
    try:
        import json as _json
        try:
            data = _json.loads(request.body or b"{}")
        except ValueError:
            data = {}
        ids = data.get("ids")  # list of int or None

        if user.is_staff or user.is_superuser:
            qs = Notification.objects.filter(is_read=False)
            if ids:
                qs = qs.filter(pk__in=ids)
            qs.update(is_read=True)
            unread = Notification.objects.filter(is_read=False).count()
        else:
            profile = getattr(user, "profile", None)
            if not profile:
                return JsonResponse({"ok": True, "unread": 0})
            qs = profile.notifications.filter(is_read=False)
            if ids:
                qs = qs.filter(pk__in=ids)
            qs.update(is_read=True)
            unread = profile.notifications.filter(is_read=False).count()

        return JsonResponse({"ok": True, "unread": unread})
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=500)


# ─────────────────────────────────────────────────────────────
# Matching — live candidate search API
# ─────────────────────────────────────────────────────────────

@login_required
@user_passes_test(lambda u: u.is_staff or u.is_superuser)
def matching_candidate_search(request):
    """GET ?q=<term>&request=<pk> — searches verified candidates and returns
    them ranked by match score against the given request (if supplied), or by
    text relevance alone.

    Returns JSON:
    {
      "results": [
        { "id", "name", "avatar", "specializations", "degree",
          "salary", "availability", "score", "reasons",
          "already_matched" },
        ...
      ]
    }
    """
    term       = (request.GET.get("q") or "").strip()
    request_pk = request.GET.get("request", "")

    if not term:
        return JsonResponse({"results": []})

    # ── Base queryset: verified candidates only ──
    qs = (
        Profile.objects
        .filter(
            role=Profile.Role.CANDIDATE,
            verification_status=Profile.VerificationStatus.VERIFIED,
        )
        .select_related("user")
        .prefetch_related("specializations", "cv_documents")
    )

    # ── Text filter across all relevant fields ──
    qs = qs.filter(
        Q(legal_name__icontains=term)
        | Q(user__first_name__icontains=term)
        | Q(user__last_name__icontains=term)
        | Q(primary_degree__icontains=term)
        | Q(certifications__icontains=term)
        | Q(software_competencies__icontains=term)
        | Q(equipment_competencies__icontains=term)
        | Q(professional_pitch__icontains=term)
        | Q(specializations__name__icontains=term)
    ).distinct()

    # ── Load the request for scoring (optional) ──
    req_obj      = None
    already_matched = set()
    if request_pk and request_pk.isdigit():
        try:
            req_obj = RecruitmentRequest.objects.prefetch_related("matches").get(pk=int(request_pk))
            already_matched = set(
                req_obj.matches.filter(is_active=True).values_list("profile_id", flat=True)
            )
        except RecruitmentRequest.DoesNotExist:
            pass

    # ── Score and sort ──
    rows = []
    for cand in qs[:60]:  # cap DB rows; scoring runs in Python
        if req_obj:
            score, reasons = _match_score(cand, req_obj)
        else:
            # No request selected — give a flat relevance score based on
            # how many search tokens appear in their profile.
            tokens = _tokens(term)
            profile_text = " ".join(filter(None, [
                cand.legal_name, cand.primary_degree,
                cand.software_competencies, cand.equipment_competencies,
                cand.professional_pitch,
                " ".join(s.name for s in cand.specializations.all()),
            ]))
            profile_tokens = set(_tokens(profile_text))
            matched_tokens = sum(1 for t in tokens if t in profile_tokens)
            score   = min(100, matched_tokens * 20 + round(cand.completion_percentage * 0.15))
            reasons = []

        specs  = [s.name for s in cand.specializations.all()]
        name   = cand.legal_name or cand.user.get_full_name() or cand.user.username
        avail  = cand.get_availability_display() if cand.availability else ""
        salary = f"₦{cand.expected_salary:,}" if cand.expected_salary else ""

        rows.append({
            "id":              cand.pk,
            "name":            name,
            "avatar":          name[:2].upper(),
            "specializations": specs,
            "degree":          cand.primary_degree or "",
            "salary":          salary,
            "availability":    avail,
            "score":           score,
            "score_class":     "is-high" if score >= 70 else ("is-mid" if score >= 40 else ""),
            "reasons":         reasons,
            "already_matched": cand.pk in already_matched,
            "has_cv":          cand.cv_documents.exists(),
        })

    rows.sort(key=lambda r: (r["already_matched"], -r["score"]))
    return JsonResponse({"results": rows[:40]})


@login_required
def dashboard_search(request):
    """GET ?q=… — JSON search results scoped to the signed-in user's dashboard role."""
    term = (request.GET.get("q") or "").strip()

    if len(term) < 2:
        return JsonResponse({"query": term, "results": [], "groups": []})

    user     = request.user
    is_admin = user.is_staff or user.is_superuser

    if is_admin:
        results    = _admin_search_results(term)
        placeholder = "Search candidates, employers, requests or logs…"
    else:
        profile = getattr(user, "profile", None)
        if profile is None:
            return JsonResponse({"query": term, "results": [], "groups": []})
        if profile.role == Profile.Role.EMPLOYER:
            results    = _employer_search_results(profile, term)
            placeholder = "Search candidates, requests or shortlist…"
        else:
            results    = _candidate_search_results(profile, term)
            placeholder = "Search employers, skills or notifications…"

    present_kinds = {r["kind"] for r in results}
    groups = [
        {"kind": kind, "label": label}
        for kind, label in SEARCH_GROUP_LABELS
        if kind in present_kinds
    ]

    return JsonResponse({
        "query":       term,
        "results":     results,
        "groups":      groups,
        "placeholder": placeholder,
        "count":       len(results),
    })
