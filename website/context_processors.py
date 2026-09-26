def _viewed(request, *paths):
    """True when the current request is one of the given dashboard pages.

    Badges are hidden on the page they count so a queue looks "seen" the
    moment the admin/candidate/employer opens it.
    """
    return request.path in paths


def dashboard_badges(request):
    ctx = {"unread_count": 0, "notif_url": None, "sidebar_badges": {}, "header_unread": 0, "header_notif_url": None}
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return ctx
    try:
        from .models import CandidateMatch, Notification, Profile, RecruitmentRequest, ReplacementRequest, Payment
        if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
            pending_candidates = Profile.objects.filter(role=Profile.Role.CANDIDATE, verification_status__in=[Profile.VerificationStatus.PENDING, Profile.VerificationStatus.VERIFYING]).count()
            open_requests = RecruitmentRequest.objects.exclude(status=RecruitmentRequest.Status.COMPLETED).count()
            pending_replacements = ReplacementRequest.objects.filter(status=ReplacementRequest.Status.REQUESTED).count()
            pending_payments = Payment.objects.filter(status=Payment.Status.PENDING).count()
            verified_pool = Profile.objects.filter(role=Profile.Role.CANDIDATE, verification_status=Profile.VerificationStatus.VERIFIED).count()
            global_unread = Notification.objects.filter(is_read=False).count()
            on_notif_page = _viewed(request, "/dashboard/admin/notifications/")
            ctx["unread_count"] = 0 if on_notif_page else global_unread
            ctx["notif_url"] = "/dashboard/admin/notifications/"
            ctx["header_unread"] = ctx["unread_count"]
            ctx["header_notif_url"] = ctx["notif_url"]
            ctx["sidebar_badges"] = {
                "admin_candidates": 0 if _viewed(request, "/dashboard/admin/candidates/") else pending_candidates,
                "admin_requests": 0 if _viewed(request, "/dashboard/admin/requests/") else open_requests,
                "admin_talent_pool": 0 if _viewed(request, "/dashboard/admin/talent-pool/") else verified_pool,
                "admin_matching": 0 if _viewed(request, "/dashboard/admin/matching/") else open_requests,
                "admin_replacements": 0 if _viewed(request, "/dashboard/admin/replacements/") else pending_replacements,
                "admin_payments": 0 if _viewed(request, "/dashboard/admin/payments/") else pending_payments,
                "admin_notifications": 0 if on_notif_page else global_unread,
            }
            return ctx
        profile = getattr(user, "profile", None)
        if profile is None:
            return ctx
        unread = profile.notifications.filter(is_read=False).count()
        if profile.role == Profile.Role.CANDIDATE:
            active_matches = profile.matches.filter(is_active=True).count()
            on_page = _viewed(request, "/dashboard/candidate/notifications/")
            ctx["unread_count"] = 0 if on_page else unread
            ctx["notif_url"] = "/dashboard/candidate/notifications/"
            ctx["header_unread"] = ctx["unread_count"]
            ctx["header_notif_url"] = ctx["notif_url"]
            ctx["sidebar_badges"] = {
                "candidate_matches": 0 if _viewed(request, "/dashboard/candidate/matches/") else active_matches,
                "candidate_notifications": 0 if on_page else unread,
            }
        elif profile.role == Profile.Role.EMPLOYER:
            received = profile.candidate_matches.filter(is_active=True).count()
            shortlisted = profile.shortlists.count()
            req_count = profile.recruitment_requests.count()
            on_page = _viewed(request, "/dashboard/employer/notifications/")
            ctx["unread_count"] = 0 if on_page else unread
            ctx["notif_url"] = "/dashboard/employer/notifications/"
            ctx["header_unread"] = ctx["unread_count"]
            ctx["header_notif_url"] = ctx["notif_url"]
            ctx["sidebar_badges"] = {
                "employer_candidates": 0 if _viewed(request, "/dashboard/employer/candidates/") else received,
                "employer_shortlist": 0 if _viewed(request, "/dashboard/employer/shortlist/") else shortlisted,
                "employer_requests": 0 if _viewed(request, "/dashboard/employer/requests/") else req_count,
                "employer_notifications": 0 if on_page else unread,
            }
            # Inject active subscription so every employer template can check it
            # without an extra DB query in each individual view.
            active_sub = profile.subscriptions.filter(is_active=True).first()
            ctx["employer_active_subscription"] = active_sub
            # Show the subscribe modal on employer pages that are NOT the
            # subscription page itself, and only when there is no active plan.
            ctx["show_subscribe_modal"] = (
                active_sub is None
                and not _viewed(request, "/dashboard/employer/subscription/")
            )
    except Exception:
        pass
    return ctx
