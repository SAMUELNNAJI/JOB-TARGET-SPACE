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
            # ── Mark items as seen when admin visits a section ──────────────
            on_cand_page     = _viewed(request, "/dashboard/admin/candidates/")
            on_requests_page = _viewed(request, "/dashboard/admin/requests/")
            on_replacements  = _viewed(request, "/dashboard/admin/replacements/")
            on_payments_page = _viewed(request, "/dashboard/admin/payments/")
            on_notif_page    = _viewed(request, "/dashboard/admin/notifications/")
            on_matching_page = _viewed(request, "/dashboard/admin/matching/")
            on_pool_page     = _viewed(request, "/dashboard/admin/talent-pool/")

            # Visiting candidates page → mark pending candidates as "verifying"
            # so they leave the pending queue (they were seen by admin)
            if on_cand_page:
                Profile.objects.filter(
                    role=Profile.Role.CANDIDATE,
                    verification_status=Profile.VerificationStatus.PENDING,
                ).update(verification_status=Profile.VerificationStatus.VERIFYING)

            # Visiting notifications → mark all unread as read
            if on_notif_page:
                Notification.objects.filter(is_read=False).update(is_read=True)

            # Visiting payments → mark pending payments as "under review" (seen)
            # We DON'T auto-change payment status — just suppress badge on the page
            # but use session to remember it was visited so badge stays clear.

            # Re-count AFTER potential updates above
            pending_candidates = Profile.objects.filter(
                role=Profile.Role.CANDIDATE,
                verification_status__in=[
                    Profile.VerificationStatus.PENDING,
                    Profile.VerificationStatus.VERIFYING,
                ],
            ).count()
            open_requests     = RecruitmentRequest.objects.exclude(status=RecruitmentRequest.Status.COMPLETED).count()
            pending_replacements = ReplacementRequest.objects.filter(status=ReplacementRequest.Status.REQUESTED).count()
            pending_payments  = Payment.objects.filter(status=Payment.Status.PENDING).count()
            verified_pool     = Profile.objects.filter(role=Profile.Role.CANDIDATE, verification_status=Profile.VerificationStatus.VERIFIED).count()
            global_unread     = Notification.objects.filter(is_read=False).count()

            ctx["unread_count"]      = 0 if on_notif_page else global_unread
            ctx["notif_url"]         = "/dashboard/admin/notifications/"
            ctx["header_unread"]     = ctx["unread_count"]
            ctx["header_notif_url"]  = ctx["notif_url"]
            ctx["sidebar_badges"]    = {
                "admin_candidates":   0 if on_cand_page     else pending_candidates,
                "admin_requests":     0 if on_requests_page else open_requests,
                "admin_talent_pool":  0 if on_pool_page     else verified_pool,
                "admin_matching":     0 if on_matching_page else open_requests,
                "admin_replacements": 0 if on_replacements  else pending_replacements,
                "admin_payments":     0 if on_payments_page else pending_payments,
                "admin_notifications": 0 if on_notif_page   else global_unread,
            }
            return ctx

        profile = getattr(user, "profile", None)
        if profile is None:
            return ctx

        # ── Candidate ────────────────────────────────────────────────────────
        if profile.role == Profile.Role.CANDIDATE:
            on_matches_page = _viewed(request, "/dashboard/candidate/matches/")
            on_page         = _viewed(request, "/dashboard/candidate/notifications/")

            # Visiting notifications → mark all as read
            if on_page:
                profile.notifications.filter(is_read=False).update(is_read=True)

            active_matches = profile.matches.filter(is_active=True).count()
            unread         = profile.notifications.filter(is_read=False).count()

            ctx["unread_count"]     = 0 if on_page else unread
            ctx["notif_url"]        = "/dashboard/candidate/notifications/"
            ctx["header_unread"]    = ctx["unread_count"]
            ctx["header_notif_url"] = ctx["notif_url"]
            ctx["sidebar_badges"]   = {
                "candidate_matches":       0 if on_matches_page else active_matches,
                "candidate_notifications": 0 if on_page         else unread,
            }

        # ── Employer ─────────────────────────────────────────────────────────
        elif profile.role == Profile.Role.EMPLOYER:
            on_cand_page  = _viewed(request, "/dashboard/employer/candidates/")
            on_shortlist  = _viewed(request, "/dashboard/employer/shortlist/")
            on_req_page   = _viewed(request, "/dashboard/employer/requests/")
            on_page       = _viewed(request, "/dashboard/employer/notifications/")

            # Visiting notifications → mark all as read
            if on_page:
                profile.notifications.filter(is_read=False).update(is_read=True)

            received    = profile.candidate_matches.filter(is_active=True).count()
            shortlisted = profile.shortlists.count()
            req_count   = profile.recruitment_requests.count()
            unread      = profile.notifications.filter(is_read=False).count()

            ctx["unread_count"]     = 0 if on_page else unread
            ctx["notif_url"]        = "/dashboard/employer/notifications/"
            ctx["header_unread"]    = ctx["unread_count"]
            ctx["header_notif_url"] = ctx["notif_url"]
            ctx["sidebar_badges"]   = {
                "employer_candidates":    0 if on_cand_page else received,
                "employer_shortlist":     0 if on_shortlist else shortlisted,
                "employer_requests":      0 if on_req_page  else req_count,
                "employer_notifications": 0 if on_page      else unread,
            }
            active_sub = profile.subscriptions.filter(is_active=True).first()
            ctx["employer_active_subscription"] = active_sub
            ctx["show_subscribe_modal"] = (
                active_sub is None
                and not _viewed(request, "/dashboard/employer/subscription/")
            )

    except Exception:
        pass
    return ctx
