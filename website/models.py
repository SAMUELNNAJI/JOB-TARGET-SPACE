from django.conf import settings
from django.db import models


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

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=Role.choices)
    phone = models.CharField(max_length=30, blank=True)
    company_name = models.CharField(max_length=150, blank=True)
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

    def notify(self, title, message, kind="system"):
        """Convenience method — creates a Notification for this profile."""
        self.notifications.create(title=title, message=message, kind=kind)


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
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("-created_at",)


class Subscription(models.Model):
    class Plan(models.TextChoices):
        BASIC = "basic", "Basic"
        PREMIUM = "premium", "Premium"

    employer = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="subscriptions")
    plan = models.CharField(max_length=20, choices=Plan.choices)
    amount = models.PositiveIntegerField()
    starts_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=False)

    @property
    def plan_label(self):
        return self.get_plan_display()


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Successful"
        FAILED = "failed", "Failed"

    employer = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="payments")
    subscription = models.ForeignKey(Subscription, on_delete=models.SET_NULL, null=True, blank=True, related_name="payments")
    reference = models.CharField(max_length=120, unique=True)
    amount = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    paid_at = models.DateTimeField(null=True, blank=True)


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
