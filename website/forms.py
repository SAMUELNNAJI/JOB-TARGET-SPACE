from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

from .models import CandidateDocument, Profile, Qualification, RecruitmentRequest, Specialization


class SignInForm(AuthenticationForm):
    username = forms.CharField(label="Email address or username")


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
    # Optional: user types a new specialization name; handled in the view via AJAX,
    # but also accepted here as a fallback for no-JS browsers.
    custom_specialization = forms.CharField(
        max_length=120,
        required=False,
        label="Add your own specialization",
        widget=forms.TextInput(attrs={
            "placeholder": "e.g. Petroleum Engineer",
            "autocomplete": "off",
        }),
    )

    class Meta:
        model = Profile
        fields = (
            "legal_name", "address", "email", "phone", "whatsapp_number", "specializations",
            "primary_degree", "certifications", "software_competencies", "equipment_competencies",
            "professional_pitch", "expected_salary", "availability",
        )
        # custom_specialization is a non-model field defined above — excluded from Meta.fields intentionally
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
            "certifications": forms.Textarea(attrs={"rows": 3}),
            "software_competencies": forms.Textarea(attrs={"rows": 3}),
            "equipment_competencies": forms.Textarea(attrs={"rows": 3}),
            "professional_pitch": forms.Textarea(attrs={"rows": 5}),
            "expected_salary": forms.NumberInput(attrs={"min": 0}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user_id:
            self.fields["email"].initial = self.instance.user.email
        # ── All wizard fields are required (except whatsapp + custom spec + equipment) ──
        required_fields = (
            "legal_name", "email", "phone", "address",
            "primary_degree", "certifications", "software_competencies",
            "professional_pitch", "expected_salary", "availability",
        )
        for name in required_fields:
            self.fields[name].required = True
        self.fields["specializations"].required = False
        # Enforced in clean(): checkbox selection OR custom_specialization text

    def clean_whatsapp_number(self):
        import re
        raw = (self.cleaned_data.get("whatsapp_number") or "").strip()
        if not raw:
            return ""
        digits = re.sub(r"\D", "", raw)
        # Strip leading Nigeria trunk zero / 234 prefix variants, keep local part check
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
        # Allow "custom_specialization only" to satisfy specializations
        specs = cleaned.get("specializations")
        custom = (cleaned.get("custom_specialization") or "").strip()
        if (not specs or len(specs) == 0) and not custom:
            self.add_error("specializations", "Select at least one specialization or add your own.")
        return cleaned

    def save(self, commit=True):
        profile = super().save(commit=commit)
        if commit:
            profile.user.email = self.cleaned_data["email"]
            profile.user.username = self.cleaned_data["email"].lower()
            profile.user.first_name = self.cleaned_data["legal_name"]
            profile.user.save(update_fields=["email", "username", "first_name"])
            # No-JS fallback: create + attach a custom specialization if provided
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
    email = forms.EmailField()

    class Meta:
        model = Profile
        fields = ("company_name", "industry_sector", "office_address", "hr_contact_name", "email", "phone")
        widgets = {"office_address": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].initial = self.instance.user.email

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
