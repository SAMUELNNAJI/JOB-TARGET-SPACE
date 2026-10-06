from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, UserCreationForm
from django.contrib.auth.models import User
from django.template.loader import render_to_string

from . import emails as mailer
from .models import CandidateDocument, Profile, Qualification, RecruitmentRequest, Specialization


class SignInForm(AuthenticationForm):
    username = forms.CharField(label="Email address or username")


class BrandedPasswordResetForm(PasswordResetForm):
    """Password reset that sends the red/white branded HTML email.

    Django's stock PasswordResetView only builds a plain-text email from
    `email_template_name`, which is why reset mails arrived looking like
    raw text. Overriding `send_mail()` reuses website.emails' `_send` /
    `_wrap_html` (logo-by-CID, red/white shell) so the reset mail matches
    every other branded mail the site sends. Drop-in: URL conf just sets
    `form_class=BrandedPasswordResetForm`.
    """

    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None,
    ):
        subject = render_to_string(subject_template_name, context)
        # Email subject must not contain newlines — exactly like Django does.
        subject = "".join(subject.splitlines())
        text_body = render_to_string(email_template_name, context)
        reset_url = "{protocol}://{domain}/password-reset/reset/{uid}/{token}/".format(
            protocol=context["protocol"],
            domain=context["domain"],
            uid=context["uid"],
            token=context["token"],
        )
        name = context["user"].first_name or context["user"].username
        content_html = f"""
    <h2 style="margin:0 0 14px;font-size:22px;font-weight:800;color:#111827">Reset your password 🔑</h2>
    <p style="margin:0 0 18px">Hi {name},</p>
    <p style="margin:0 0 18px">
      You requested a password reset for your Target JobSpace account.
      Tap the button below to choose a new password.</p>
    <p style="margin:0 0 6px;padding:16px 18px;background:#fff8f8;border-left:4px solid #d6001d;border-radius:0 8px 8px 0;font-size:14px">
      <strong>This link is valid for 24 hours.</strong> If you did not request
      a password reset, you can safely ignore this email.</p>"""
        html_body = mailer._wrap_html(
            "Reset your password",
            content_html,
            "Choose a new password",
            reset_url,
            preheader="Reset your Target JobSpace password — link valid for 24 hours.",
        )
        mailer._send(subject, text_body, html_body, to_email)


class SignUpForm(UserCreationForm):
    role = forms.ChoiceField(choices=Profile.Role.choices, widget=forms.HiddenInput())
    email = forms.EmailField(label="Email address")
    full_name = forms.CharField(label="Full name", max_length=150, required=False)
    phone = forms.CharField(label="Phone number", max_length=30, required=False)
    company_name = forms.CharField(label="Company name", max_length=150, required=False)

    class Meta:
        model = User
        fields = ("email", "full_name", "phone", "company_name", "password1", "password2", "role")

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(username=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get("role")
        if role == Profile.Role.CANDIDATE and not cleaned_data.get("full_name"):
            self.add_error("full_name", "Enter your full name.")
        if role == Profile.Role.EMPLOYER and not cleaned_data.get("company_name"):
            self.add_error("company_name", "Enter your company name.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"]
        user.email = self.cleaned_data["email"]
        full_name = self.cleaned_data.get("full_name", "").strip()
        user.first_name = full_name
        if commit:
            user.save()
            Profile.objects.create(
                user=user,
                role=self.cleaned_data["role"],
                phone=self.cleaned_data.get("phone", ""),
                company_name=self.cleaned_data.get("company_name", ""),
                legal_name=full_name,
            )
        return user


class CandidateProfileForm(forms.ModelForm):
    email = forms.EmailField()
    whatsapp_number = forms.CharField(
        label="WhatsApp number",
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={
            "placeholder": "e.g. 0803 123 4567",
            "inputmode": "tel",
            "autocomplete": "tel",
        }),
    )
    specializations = forms.ModelMultipleChoiceField(
        queryset=Specialization.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    custom_specialization = forms.CharField(
        max_length=120,
        required=False,
        label="Add your own specialization",
        widget=forms.TextInput(attrs={
            "placeholder": "e.g. Petroleum Engineer",
            "autocomplete": "off",
        }),
    )

    # ── New career preference fields ─────────────────────────────────────────
    EMPLOYMENT_NATURE_CHOICES = [
        ("Full-Time",          "Full-Time"),
        ("Part-Time",          "Part-Time"),
        ("Contract/Freelance", "Contract / Freelance"),
        ("Internship",         "Internship"),
    ]
    WORKPLACE_MODEL_CHOICES = [
        ("On-site", "On-site"),
        ("Hybrid",  "Hybrid"),
        ("Remote",  "Remote"),
    ]

    employment_nature_choices = forms.MultipleChoiceField(
        choices=EMPLOYMENT_NATURE_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Preferred employment type",
    )
    workplace_model_choices = forms.MultipleChoiceField(
        choices=WORKPLACE_MODEL_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Workplace model preference",
    )

    class Meta:
        model = Profile
        fields = (
            "legal_name", "address", "email", "phone", "whatsapp_number",
            "specializations",
            "primary_degree", "certifications", "software_competencies", "equipment_competencies",
            "professional_pitch", "expected_salary", "availability",
            # new fields
            "professional_headline", "experience_level",
            "job_role_targets", "target_location",
        )
        widgets = {
            "address":                forms.Textarea(attrs={"rows": 3}),
            "certifications":         forms.Textarea(attrs={"rows": 3}),
            "software_competencies":  forms.Textarea(attrs={"rows": 3}),
            "equipment_competencies": forms.Textarea(attrs={"rows": 3}),
            "professional_pitch":     forms.Textarea(attrs={"rows": 5}),
            "expected_salary":        forms.NumberInput(attrs={"min": 0}),
            "professional_headline":  forms.TextInput(attrs={
                "placeholder": "e.g. Senior Backend Engineer, Data Analyst, Creative UX Specialist"
            }),
            "job_role_targets": forms.TextInput(attrs={
                "placeholder": "e.g. Backend Developer, DevOps Engineer (up to 3 roles, comma-separated)"
            }),
            "target_location": forms.TextInput(attrs={
                "placeholder": "e.g. Lagos, Nigeria  or  Worldwide Remote"
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user_id:
            self.fields["email"].initial = self.instance.user.email
        # Restore multi-checkbox state from comma-sep model field
        if self.instance and self.instance.pk:
            if self.instance.employment_nature:
                self.fields["employment_nature_choices"].initial = [
                    v.strip() for v in self.instance.employment_nature.split(",") if v.strip()
                ]
            if self.instance.workplace_model:
                self.fields["workplace_model_choices"].initial = [
                    v.strip() for v in self.instance.workplace_model.split(",") if v.strip()
                ]
        # Required fields
        required_fields = (
            "legal_name", "email", "phone",
            "primary_degree", "software_competencies",
            "professional_pitch", "expected_salary", "availability",
            "professional_headline", "experience_level",
        )
        for name in required_fields:
            self.fields[name].required = True
        # Optional fields
        for name in ("whatsapp_number", "certifications", "equipment_competencies",
                     "address", "job_role_targets", "target_location",
                     "employment_nature_choices", "workplace_model_choices"):
            self.fields[name].required = False

    def clean_whatsapp_number(self):
        import re
        raw = (self.cleaned_data.get("whatsapp_number") or "").strip()
        if not raw:
            return ""
        digits = re.sub(r"\D", "", raw)
        if digits.startswith("234") and len(digits) > 10:
            local = digits[3:]
        elif digits.startswith("0"):
            local = digits[1:]
        else:
            local = digits
        if len(digits) < 7 or len(digits) > 15 or len(local) < 7:
            raise forms.ValidationError("Enter a valid WhatsApp number (7–15 digits).")
        return raw

    def clean_expected_salary(self):
        value = self.cleaned_data.get("expected_salary")
        if value in (None, ""):
            raise forms.ValidationError("Enter your expected net monthly salary.")
        if value <= 0:
            raise forms.ValidationError("Expected salary must be greater than zero.")
        return value

    def clean_professional_pitch(self):
        pitch = (self.cleaned_data.get("professional_pitch") or "").strip()
        if not pitch:
            raise forms.ValidationError("Write a short professional pitch.")
        if len(pitch) < 30:
            raise forms.ValidationError("Your pitch is too short — write at least 30 characters.")
        return pitch

    def clean(self):
        cleaned = super().clean()
        specs  = cleaned.get("specializations")
        custom = (cleaned.get("custom_specialization") or "").strip()
        if (not specs or len(specs) == 0) and not custom:
            self.add_error("specializations", "Select at least one specialization or add your own.")
        return cleaned

    def save(self, commit=True):
        profile = super().save(commit=False)
        # Persist multi-checkbox fields as comma-separated strings
        en = self.cleaned_data.get("employment_nature_choices") or []
        wm = self.cleaned_data.get("workplace_model_choices") or []
        profile.employment_nature = ",".join(en)
        profile.workplace_model   = ",".join(wm)
        if commit:
            profile.save()
            profile.user.email      = self.cleaned_data["email"]
            profile.user.username   = self.cleaned_data["email"].lower()
            profile.user.first_name = self.cleaned_data["legal_name"]
            profile.user.save(update_fields=["email", "username", "first_name"])
            custom = self.cleaned_data.get("custom_specialization", "").strip()
            if custom:
                from django.utils.text import slugify
                slug = slugify(custom)
                if slug:
                    spec, _ = Specialization.objects.get_or_create(
                        slug=slug, defaults={"name": custom.title()}
                    )
                    profile.specializations.add(spec)
        return profile


class CandidateDocumentForm(forms.ModelForm):
    class Meta:
        model = CandidateDocument
        fields = ("file",)

    def clean_file(self):
        uploaded_file = self.cleaned_data["file"]
        allowed_types = {"application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
        allowed_suffixes = {".pdf", ".docx"}
        suffix = "." + uploaded_file.name.rsplit(".", 1)[-1].lower() if "." in uploaded_file.name else ""
        if suffix not in allowed_suffixes or uploaded_file.content_type not in allowed_types:
            raise forms.ValidationError("Upload a PDF or DOCX file only.")
        if uploaded_file.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Your CV must be 5MB or smaller.")
        return uploaded_file


class QualificationForm(forms.ModelForm):
    class Meta:
        model = Qualification
        fields = ("title", "institution", "year")


class EmployerProfileForm(forms.ModelForm):
    email = forms.EmailField(label="Official email address")

    # ── Industry sector — comprehensive searchable dropdown ──────────────────
    INDUSTRY_CHOICES = [("", "Select an industry…")] + [(s, s) for s in [
        "Accounting & Finance",
        "Administrative & Secretarial",
        "Advertising & PR",
        "Agriculture, Forestry & Fishing",
        "Architecture & Design",
        "Automotive",
        "Aviation & Aerospace",
        "Banking & Financial Services",
        "Biotechnology & Life Sciences",
        "Broadcasting & Media",
        "Building & Construction",
        "Chemical & Petrochemical",
        "Consulting & Strategy",
        "Consumer Goods & FMCG",
        "Defence & Security",
        "E-Commerce & Retail Tech",
        "Education & Training",
        "Electrical & Electronics",
        "Energy & Utilities",
        "Engineering (Civil)",
        "Engineering (Mechanical)",
        "Engineering (Electrical)",
        "Engineering (Chemical)",
        "Environmental & Sustainability",
        "Fashion & Apparel",
        "Food & Beverage",
        "Government & Public Sector",
        "Healthcare & Medical",
        "Hospitality & Tourism",
        "Human Resources & Recruitment",
        "Import & Export / Trade",
        "Information Technology & Software",
        "Insurance",
        "Legal & Compliance",
        "Logistics, Supply Chain & Procurement",
        "Manufacturing & Production",
        "Marine & Shipping",
        "Marketing & Digital Marketing",
        "Mining & Metals",
        "NGO & Non-Profit",
        "Oil & Gas (Upstream)",
        "Oil & Gas (Midstream)",
        "Oil & Gas (Downstream)",
        "Pharmaceutical & Drug Manufacturing",
        "Power & Renewable Energy",
        "Printing & Publishing",
        "Property & Real Estate",
        "Retail & Wholesale",
        "Telecommunications",
        "Transportation",
        "Waste Management & Recycling",
        "Other",
    ]]

    # ── Company size tier ────────────────────────────────────────────────────
    SIZE_CHOICES = [
        ("", "Select company size…"),
        ("1-10",    "1–10 employees (Seed / Startup)"),
        ("11-50",   "11–50 employees (Growth)"),
        ("51-200",  "51–200 employees (Mid-Market)"),
        ("201-500", "201–500 employees (Corporate)"),
        ("501+",    "501+ employees (Enterprise)"),
    ]

    industry_sector = forms.ChoiceField(
        choices=INDUSTRY_CHOICES,
        label="Industry sector",
        widget=forms.Select(attrs={"class": "emp-select emp-select--searchable"}),
    )
    company_size = forms.ChoiceField(
        choices=SIZE_CHOICES,
        label="Company size",
        required=False,
        widget=forms.Select(attrs={"class": "emp-select"}),
    )

    class Meta:
        model = Profile
        fields = (
            "company_name",
            "company_legal_name",
            "company_website",
            "company_size",
            "industry_sector",
            "office_address",
            "hq_location",
            "hr_contact_name",
            "email",
            "phone",
        )
        widgets = {
            "office_address": forms.Textarea(attrs={"rows": 3}),
            "company_website": forms.URLInput(attrs={"placeholder": "https://www.yourcompany.com"}),
            "hq_location": forms.TextInput(attrs={"placeholder": "e.g. Lagos, Nigeria"}),
            "phone": forms.TextInput(attrs={"placeholder": "e.g. +234 801 234 5678"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].initial = self.instance.user.email
        # Required fields
        for f in ("company_name", "company_legal_name", "industry_sector",
                  "hr_contact_name", "office_address", "hq_location", "phone"):
            self.fields[f].required = True
        # Optional fields
        self.fields["company_website"].required = False
        self.fields["company_size"].required = False

    def clean_company_website(self):
        url = self.cleaned_data.get("company_website", "").strip()
        if not url:
            return ""
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        return url

    def clean_industry_sector(self):
        value = self.cleaned_data.get("industry_sector", "").strip()
        if not value:
            raise forms.ValidationError("Select an industry sector.")
        return value

    def save(self, commit=True):
        profile = super().save(commit=commit)
        if commit:
            profile.user.email = self.cleaned_data["email"]
            profile.user.username = self.cleaned_data["email"].lower()
            profile.user.save(update_fields=["email", "username"])
        return profile


class RecruitmentRequestForm(forms.ModelForm):
    OTHER = "__other__"

    # Dropdown of common professions. The employer can pick one, or choose
    # "Other" and type any profession we don't have listed.
    position = forms.ChoiceField(
        required=False,
        label="Professional position",
        choices=[("", "Select a position…")] + list(RecruitmentRequest.POSITION_CHOICES)
                + [(OTHER, "Other — type it below")],
    )
    # Non-model field, excluded from Meta.fields intentionally (same pattern as
    # custom_specialization on the candidate profile form).
    custom_position = forms.CharField(
        required=False,
        max_length=120,
        label="Enter the position you need",
        widget=forms.TextInput(attrs={"placeholder": "e.g.Quantity Surveyor, Data Analyst, welder…"}),
    )

    class Meta:
        model = RecruitmentRequest
        fields = ("position", "professionals_required", "minimum_qualification", "certifications", "years_experience", "required_skills", "salary_min", "salary_max", "salary_period")
        widgets = {"certifications": forms.Textarea(attrs={"rows": 3}), "required_skills": forms.Textarea(attrs={"rows": 3})}

    def clean_custom_position(self):
        # Whitespace-only input counts as "not provided".
        return self.cleaned_data.get("custom_position", "").strip()

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("salary_min") and cleaned.get("salary_max") and cleaned["salary_min"] > cleaned["salary_max"]:
            raise forms.ValidationError("Maximum salary must be greater than minimum salary.")

        selected  = (cleaned.get("position") or "").strip()
        custom    = (cleaned.get("custom_position") or "").strip()

        # Resolve the two inputs into a single stored position value.
        if selected == self.OTHER or not selected:
            cleaned["position"] = custom
            if not custom:
                message = ("Enter the position you need." if selected == self.OTHER
                           else "Select a position or type the one you need.")
                self.add_error("custom_position" if selected == self.OTHER else "position", message)
        else:
            cleaned["position"] = selected

        return cleaned
