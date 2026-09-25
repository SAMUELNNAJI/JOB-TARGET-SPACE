def dashboard_badges(request):
    ctx = {"unread_count": 0, "notif_url": None, "sidebar_badges": {}, "header_unread": 0, "header_notif_url": None}
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return ctx
    try:
        if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
            from .models import CandidateMatch, Notification, Profile, RecruitmentRequest, ReplacementRequest, Payment
            pending_candidates = Profile.objects.filter(role=Profile.Role.CANDIDATE, verification_status__in=[Profile.VerificationStatus.PENDING, Profile.VerificationStatus.VERIFYING]).count()
            open_requests = RecruitmentRequest.objects.exclude(status=RecruitmentRequest.Status.COMPLETED).count()
            pending_replacements = ReplacementRequest.objects.filter(status=ReplacementRequest.Status.REQUESTED).count()
            pending_payments = Payment.objects.filter(status=Payment.Status.PENDING).count()
            verified_pool = Profile.objects.filter(role=Profile.Role.CANDIDATE, verification_status=Profile.VerificationStatus.VERIFIED).count()
            global_unread = Notification.objects.filter(is_read=False).count()
            on_notif_page = request.path == "/dashboard/admin/notifications/"
            ctx["unread_count"] = 0 if on_notif_page else global_unread
            ctx["notif_url"] = "/dashboard/admin/notifications/"
            ctx["header_unread"] = ctx["unread_count"]
            ctx["header_notif_url"] = ctx["notif_url"]
            ctx["sidebar_badges"] = {"admin_candidates": pending_candidates, "admin_requests": open_requests, "admin_talent_pool": verified_pool, "admin_matching": open_requests, "admin_replacements": pending_replacements, "admin_payments": pending_payments, "admin_notifications": 0 if on_notif_page else global_unread}
            return ctx
        profile = getattr(user, "profile", None)
        if profile is None:
            return ctx
        unread = profile.notifications.filter(is_read=False).count()
        if profile.role == Profile.Role.CANDIDATE:
            active_matches = profile.matches.filter(is_active=True).count()
            on_page = request.path == "/dashboard/candidate/notifications/"
            ctx["unread_count"] = 0 if on_page else unread
            ctx["notif_url"] = "/dashboard/candidate/notifications/"
            ctx["header_unread"] = ctx["unread_count"]
            ctx["header_notif_url"] = ctx["notif_url"]
            ctx["sidebar_badges"] = {"candidate_matches": active_matches, "candidate_notifications": 0 if on_page else unread}
        elif profile.role == Profile.Role.EMPLOYER:
            received = profile.candidate_matches.filter(is_active=True).count()
            shortlisted = profile.shortlists.count()
            req_count = profile.recruitment_requests.count()
            on_page = request.path == "/dashboard/employer/notifications/"
            ctx["unread_count"] = 0 if on_page else unread
            ctx["notif_url"] = "/dashboard/employer/notifications/"
            ctx["header_unread"] = ctx["unread_count"]
            ctx["header_notif_url"] = ctx["notif_url"]
            ctx["sidebar_badges"] = {"employer_candidates": received, "employer_shortlist": shortlisted, "employer_requests": req_count, "employer_notifications": 0 if on_page else unread}
    except Exception:
        pass
    return ctx
