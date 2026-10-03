from django.conf import settings
from django.db import models
from django.utils.functional import cached_property
from django.utils import timezone


class Profile(models.Model):
    class Role(models.TextChoices):
        CANDIDATE = "candidate", "Candidate"
        EMPLOYER = "employer", "Employer"

    class VerificationStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING = "pending", "Pending Review"
        VERIFYING = "verifying", "Under Verification"
        VERIFIED = "verified", "Vetted & Verified"
        CHANGES = "changes", "Requires Changes"
        REJECTED = "rejected", "Rejected"

    class Availability(models.TextChoices):
        IMMEDIATE = "immediate", "Immediate"
        ONE_MONTH = "one_month", "1 Month Notice"

    class ExperienceLevel(models.TextChoices):
        ENTRY   = "entry",     "Entry-Level (0–1 year)"
        JUNIOR  = "junior",    "Junior (1–3 years)"
        MID     = "mid",       "Mid-Level (3–5 years)"
        SENIOR  = "senior",    "Senior (5–8 years)"
        PRINCIPAL = "principal", "Principal / Executive (8+ years)"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=Role.choices)
    phone = models.CharField(max_length=30, blank=True)
    company_name = models.CharField(max_length=150, blank=True)
    company_legal_name = models.CharField(max_length=200, blank=True)  # legal entity for billing
    company_website = models.URLField(blank=True)
    company_size = models.CharField(max_length=40, blank=True)          # size tier slug
    hq_location = models.CharField(max_length=150, blank=True)         # city, country
    industry_sector = models.CharField(max_length=150, blank=True)
    hr_contact_name = models.CharField(max_length=150, blank=True)
    office_address = models.TextField(blank=True)
    legal_name = models.CharField(max_length=150, blank=True)
    address = models.TextField(blank=True)
    whatsapp_url = models.URLField(blank=True)  # legacy: stored wa.me link
    whatsapp_number = models.CharField(max_length=30, blank=True)
    primary_degree = models.CharField(max_length=200, blank=True)
    certifications = models.TextField(blank=True)
    software_competencies = models.TextField(blank=True)
    equipment_competencies = models.TextField(blank=True)
    professional_pitch = models.TextField(blank=True)
    expected_salary = models.PositiveIntegerField(null=True, blank=True)
    availability = models.CharField(max_length=20, choices=Availability.choices, blank=True)
    # ── New career fields ──────────────────────────────────────────────────
    professional_headline = models.CharField(max_length=120, blank=True)
    experience_level = models.CharField(max_length=20, choices=ExperienceLevel.choices, blank=True)
    job_role_targets = models.CharField(max_length=300, blank=True)   # comma-sep, up to 3
    employment_nature = models.CharField(max_length=150, blank=True)  # comma-sep checkboxes
    workplace_model   = models.CharField(max_length=100, blank=True)  # comma-sep checkboxes
    target_location   = models.CharField(max_length=150, blank=True)
    verification_status = models.CharField(max_length=20, choices=VerificationStatus.choices, default=VerificationStatus.DRAFT)
    verification_notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    specializations = models.ManyToManyField("Specialization", blank=True, related_name="profiles")

    def __str__(self):
        return f"{self.user.username} ({self.role})"

    @property
    def completion_percentage(self):
        fields = [self.legal_name, self.address, self.phone, self.primary_degree, self.certifications, self.software_competencies, self.professional_pitch, self.expected_salary, self.availability, self.cv_documents.exists()]
        return round(sum(bool(value) for value in fields) / len(fields) * 100)

    # Fields an employer must supply before the profile counts as complete.
    EMPLOYER_REQUIRED_FIELDS = (
        "company_name", "company_legal_name", "industry_sector",
        "hr_contact_name", "office_address", "hq_location", "phone",
    )

    @property
    def employer_profile_complete(self):
        """True once every company detail + contact detail has been provided."""
        if self.role != self.Role.EMPLOYER:
            return False
        if not all(getattr(self, name, "") for name in self.EMPLOYER_REQUIRED_FIELDS):
            return False
        return bool(getattr(self.user, "email", ""))

    def notify(self, title, message, kind="system"):
        """Convenience method — creates a Notification for this profile."""
        self.notifications.create(title=title, message=message, kind=kind)

    def current_subscription(self):
        """The employer's live plan, or None.

        A row only counts while it is both `is_active` and inside its
        expiry window, so an expired Basic never keeps its employer
        unlocked. Plans are ordered by expiry so the one that actually
        covers today wins if stale rows linger.
        """
        return (
            self.subscriptions.filter(is_active=True)
            .exclude(expires_at__lte=timezone.now())
            .order_by("-expires_at")
            .first()
        )

    def has_active_plan(self):
        return self.current_subscription() is not None

    def current_match_limit(self):
        """Candidates an admin may push per request; None = unlimited."""
        sub = self.current_subscription()
        return sub.match_limit if sub else 0


class Specialization(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class CandidateDocument(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="cv_documents")
    file = models.FileField(upload_to="candidate_documents/%Y/%m/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.profile.user.username} - {self.file.name}"


class Qualification(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="qualifications")
    title = models.CharField(max_length=200)
    institution = models.CharField(max_length=200, blank=True)
    year = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return self.title


class Notification(models.Model):
    class Kind(models.TextChoices):
        VERIFICATION = "verification", "Verification"
        MATCH        = "match",        "Match / Opportunity"
        SHORTLIST    = "shortlist",    "Shortlisted"
        PAYMENT      = "payment",      "Payment"
        PROFILE      = "profile",      "Profile"
        SYSTEM       = "system",       "System"

    profile    = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="notifications")
    title      = models.CharField(max_length=180)
    message    = models.TextField()
    kind       = models.CharField(max_length=20, choices=Kind.choices, default=Kind.SYSTEM)
    is_read    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)


class CandidateMatch(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="matches")
    employer = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="candidate_matches")
    # The recruitment request this match fulfils. Nullable so pre-existing matches
    # (created before this field existed) stay valid.
    request = models.ForeignKey(
        "RecruitmentRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="matches",
    )
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    # Employer can formally accept a matched candidate
    is_accepted = models.BooleanField(default=False)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            # A candidate can only be pushed once per employer per request.
            models.UniqueConstraint(
                fields=("employer", "profile", "request"),
                name="unique_candidate_match_per_request",
            ),
        ]


class Subscription(models.Model):
    class Plan(models.TextChoices):
        BASIC = "basic", "Basic"
        PREMIUM = "premium", "Premium"

    # How long each plan runs for once payment is approved.
    DURATION_DAYS = {
        Plan.BASIC: 30,
        Plan.PREMIUM: 90,
    }

    # Candidates an admin may push per recruitment request.
    # Basic is capped; Premium is unlimited (None).
    MATCH_LIMIT = {
        Plan.BASIC: 5,
        Plan.PREMIUM: None,
    }

    employer = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="subscriptions")
    plan = models.CharField(max_length=20, choices=Plan.choices)
    amount = models.PositiveIntegerField()
    starts_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=False)
    # Set the first time the expiry sweep notifies the employer, so the
    # "plan expired" notice is sent exactly once per subscription row.
    expiry_notified_at = models.DateTimeField(null=True, blank=True)

    @property
    def plan_label(self):
        return self.get_plan_display()

    @property
    def duration_days(self):
        return self.DURATION_DAYS.get(self.plan, 30)

    @property
    def match_limit(self):
        """Max candidates an admin may match to ONE request on this plan."""
        return self.MATCH_LIMIT.get(self.plan)

    @property
    def is_expired(self):
        return bool(self.expires_at and self.expires_at <= timezone.now())

    @property
    def is_current(self):
        """Active AND not past its expiry date."""
        return bool(self.is_active) and not self.is_expired

    @property
    def days_remaining(self):
        """Whole days left before expiry; 0 once expired."""
        if not self.expires_at:
            return 0
        delta = self.expires_at - timezone.now()
        return max(delta.days, 0)

    def renewal_window_open(self):
        """True once a plan is close enough to expiry to warrant a renewal nudge.

        Premium asks 14 days out, Basic 7 days out.
        """
        if not self.expires_at:
            return False
        remaining = (self.expires_at - timezone.now()).days
        lead = 14 if self.plan == self.Plan.PREMIUM else 7
        return 0 <= remaining <= lead

    def expiry_from(self, start=None):
        """`expires_at` for a plan starting at `start` (default: now)."""
        start = start or timezone.now()
        return start + timezone.timedelta(days=self.duration_days)


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Under Review"
        SUCCESS = "success", "Approved"
        FAILED = "failed", "Declined"

    employer = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="payments")
    subscription = models.ForeignKey(Subscription, on_delete=models.SET_NULL, null=True, blank=True, related_name="payments")
    reference = models.CharField(max_length=120, unique=True)
    amount = models.PositiveIntegerField()
    verified_amount = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    bank_name = models.CharField(max_length=100, blank=True, default="")
    sender_name = models.CharField(max_length=150, blank=True, default="")
    proof = models.FileField(upload_to="payment_proofs/%Y/%m/", null=True, blank=True)
    admin_notes = models.TextField(blank=True, default="")
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "-id")

    @property
    def display_amount(self):
        """Amount actually verified on the receipt; falls back to claimed amount."""
        return self.verified_amount if self.verified_amount is not None else self.amount


class RecruitmentRequest(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        REVIEW = "review", "Under Review"
        MATCHING = "matching", "Matching Candidates"
        AVAILABLE = "available", "Candidates Available"
        COMPLETED = "completed", "Completed"

    # Suggested positions offered in the employer's dropdown. This is a plain list,
    # NOT model `choices` — employers may submit any other profession by typing it.
    POSITION_CHOICES = [(name, name) for name in ("Accountant", "Auditor", "Marketer", "Planner", "Architect", "Civil Engineer", "Mechanical Engineer", "Electrical Engineer", "Software Engineer", "Doctor", "Medical Technologist", "Equipment Operator", "Heavy Duty Technician", "Technical Supervisor", "Administrative Staff")]
    employer = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="recruitment_requests")
    position = models.CharField(max_length=120)
    professionals_required = models.PositiveIntegerField(default=1)
    minimum_qualification = models.CharField(max_length=200)
    certifications = models.TextField(blank=True)
    years_experience = models.PositiveIntegerField(default=0)
    required_skills = models.TextField()
    salary_min = models.PositiveIntegerField()
    salary_max = models.PositiveIntegerField()
    salary_period = models.CharField(max_length=20, choices=(("monthly", "Monthly"), ("annual", "Annual")), default="monthly")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUBMITTED)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def matched_count(self):
        """How many candidates are currently matched to this request."""
        return self.matches.filter(is_active=True).count()

    @property
    def remaining_slots(self):
        return max(self.professionals_required - self.matched_count, 0)

    @property
    def is_fully_matched(self):
        return self.remaining_slots == 0

    @property
    def is_open(self):
        return self.status != self.Status.COMPLETED

    def sync_status(self):
        """Keep the request status in step with how many candidates are matched.

        0 matches -> Under Review, partial -> Matching Candidates,
        all slots filled -> Candidates Available.
        """
        if self.status == self.Status.COMPLETED:
            return False

        if self.matched_count == 0:
            new_status = self.Status.REVIEW
        elif self.is_fully_matched:
            new_status = self.Status.AVAILABLE
        else:
            new_status = self.Status.MATCHING

        if new_status != self.status:
            self.status = new_status
            self.save(update_fields=["status"])
            return True
        return False


class Shortlist(models.Model):
    employer = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="shortlists")
    candidate = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="shortlisted_by")
    match = models.ForeignKey(CandidateMatch, on_delete=models.CASCADE, related_name="shortlists")
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=40, default="Shortlisted")

    class Meta:
        constraints = [models.UniqueConstraint(fields=("employer", "candidate"), name="unique_employer_candidate_shortlist")]


class ReplacementRequest(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        ELIGIBLE = "eligible", "Eligible"
        REPLACED = "replaced", "Replaced"
        DECLINED = "declined", "Declined"

    employer = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="replacement_requests")
    candidate = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="replacement_requests_for")
    replacement_candidate = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, blank=True, related_name="replacement_assignments")
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED)
    created_at = models.DateTimeField(auto_now_add=True)


class AuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="audit_events")
    action = models.CharField(max_length=180)
    subject = models.CharField(max_length=180, blank=True)
    result = models.CharField(max_length=80, default="Success")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)


class SupportThread(models.Model):
    """One conversation between a Profile (candidate or employer) and Target JobSpace.

    There is exactly one thread per profile — a user always resumes the same
    conversation rather than starting a new one each time they open Support.
    `last_message_at` drives the admin inbox ordering so the thread with the
    most recent activity floats to the top.
    """

    profile = models.OneToOneField(
        Profile, on_delete=models.CASCADE, related_name="support_thread"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ("-last_message_at", "-created_at")

    def __str__(self):
        return f"Support thread — {self.profile}"

    @property
    def last_message(self):
        return self.messages.order_by("-created_at").first()

    def touch(self):
        """Stamp the thread after a new message so the inbox reorders."""
        now = timezone.now()
        self.last_message_at = now
        self.save(update_fields=["last_message_at", "updated_at"])

    def unread_for_admin(self):
        """Messages the user sent that staff have not opened yet."""
        return self.messages.filter(sender_role=SupportMessage.Role.USER, is_read=False)

    def unread_for_user(self):
        """Staff replies the user has not opened yet."""
        return self.messages.filter(sender_role=SupportMessage.Role.STAFF, is_read=False)


class SupportMessage(models.Model):
    class Role(models.TextChoices):
        USER  = "user",  "User"
        STAFF = "staff", "Target JobSpace"

    thread = models.ForeignKey(
        SupportThread, on_delete=models.CASCADE, related_name="messages"
    )
    # NULL sender = staff. Staff accounts have no Profile, and making this
    # nullable keeps the thread usable even if a staff user is later deleted.
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="support_messages",
    )
    sender_role = models.CharField(max_length=10, choices=Role.choices)
    body = models.TextField(blank=True)
    # Voice note. Optional — a message is either text, audio, or both.
    audio = models.FileField(upload_to="chat_audio/%Y/%m/", blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        # Oldest first so a chat transcript reads top-to-bottom, and the id
        # tiebreaker keeps ordering stable when two rows share a timestamp.
        ordering = ("created_at", "id")
        indexes = [models.Index(fields=("thread", "id"))]

    @cached_property
    def audio_available(self) -> bool:
        """Whether the clip this row points at can actually be served here.

        `audio` is a FileField, so Postgres holds only a relative path - the
        bytes live in MEDIA_ROOT, which is per-machine storage (the laptop's
        `media/` folder in dev, the Render disk in prod) while the database is
        shared. A note recorded on one of them is therefore a valid row with no
        file on the other, and a player built for it can only ever fail.
        Templates ask this first and show a quiet notice instead.
        """
        if not self.audio:
            return False
        try:
            return self.audio.storage.exists(self.audio.name)
        except Exception:          # storage backend hiccup = treat as absent
            return False



class SiteSettings(models.Model):
    """Single-row table that stores site-wide contact details.

    Only one row should ever exist (pk=1).  The admin settings page
    creates it on first save and updates it on subsequent saves.
    Use SiteSettings.load() anywhere you need the current values.
    """
    email   = models.EmailField(default="info@targetjobspace.com")
    phone   = models.CharField(max_length=30, default="+234 913 618 5082")
    address = models.CharField(max_length=200, default="Bayo Dejonwo Street, Maryland, Lagos.")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Site settings"

    def __str__(self):
        return "Site settings"

    @classmethod
    def load(cls):
        """Return the single settings row, creating it with defaults if absent."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
