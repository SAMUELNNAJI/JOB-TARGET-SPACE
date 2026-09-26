def _viewed(request, *paths):
    """True when the current request is one of the given dashboard pages.

    Badges are hidden on the page they count so a queue looks "seen" the
    moment the admin/candidate/employer opens it.
    """
    return request.path in paths


# Session key holding the last count the user actually saw for each badge.
SEEN_BADGES_KEY = "seen_badges"


def _apply_seen(request, badges, visited_map):
    """Suppress badges the user has already opened.

    `badges` maps a badge key to its current count; `visited_map` maps the
    same keys to whether the user is on that page right now.

    Opening a page records the count it had at that moment. The badge then
    stays hidden on every later page until the underlying count *grows* —
    that is what makes a badge mean "there is something new here" rather
    than "this section is non-empty". Without this the old behaviour only
    hid the badge for the duration of the visit, so it reappeared as soon
    as the user navigated away.
    """
    try:
        seen = request.session.get(SEEN_BADGES_KEY) or {}
    except Exception:
        seen = {}

    out = {}
    dirty = False
    for key, count in badges.items():
        if visited_map.get(key):
            # Viewing the page marks whatever is queued right now as seen.
            if seen.get(key) != count:
                seen[key] = count
                dirty = True
            out[key] = 0
        else:
            # Show only what has appeared since the last visit.
            out[key] = count if count > seen.get(key, 0) else 0

    if dirty:
        try:
            request.session[SEEN_BADGES_KEY] = seen
            request.session.modified = True
        except Exception:
            pass
    return out


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
            ctx["sidebar_badges"]    = _apply_seen(
                request,
                {
                    "admin_candidates":    pending_candidates,
                    "admin_requests":      open_requests,
                    "admin_talent_pool":   verified_pool,
                    "admin_matching":      open_requests,
                    "admin_replacements":  pending_replacements,
                    "admin_payments":      pending_payments,
                    "admin_notifications": global_unread,
                },
                {
                    "admin_candidates":    on_cand_page,
                    "admin_requests":      on_requests_page,
                    "admin_talent_pool":   on_pool_page,
                    "admin_matching":      on_matching_page,
                    "admin_replacements":  on_replacements,
                    "admin_payments":      on_payments_page,
                    "admin_notifications": on_notif_page,
                },
            )
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
            ctx["sidebar_badges"]   = _apply_seen(
                request,
                {
                    "candidate_matches":       active_matches,
                    "candidate_notifications": unread,
                },
                {
                    "candidate_matches":       on_matches_page,
                    "candidate_notifications": on_page,
                },
            )

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
            ctx["sidebar_badges"]   = _apply_seen(
                request,
                {
                    "employer_candidates":    received,
                    "employer_shortlist":     shortlisted,
                    "employer_requests":      req_count,
                    "employer_notifications": unread,
                },
                {
                    "employer_candidates":    on_cand_page,
                    "employer_shortlist":     on_shortlist,
                    "employer_requests":      on_req_page,
                    "employer_notifications": on_page,
                },
            )
            active_sub = profile.subscriptions.filter(is_active=True).first()
            ctx["employer_active_subscription"] = active_sub
            ctx["show_subscribe_modal"] = (
                active_sub is None
                and not _viewed(request, "/dashboard/employer/subscription/")
            )

    except Exception:
        pass
    return ctx
