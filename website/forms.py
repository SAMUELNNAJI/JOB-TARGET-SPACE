from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

from .models import CandidateDocument, Profile, Qualification, RecruitmentRequest, Specialization


class SignInForm(AuthenticationForm):
    username = forms.EmailField(label="Email address")


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
            "legal_name", "address", "email", "phone", "whatsapp_url", "specializations",
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
    class Meta:
        model = RecruitmentRequest
        fields = ("position", "professionals_required", "minimum_qualification", "certifications", "years_experience", "required_skills", "salary_min", "salary_max", "salary_period")
        widgets = {"certifications": forms.Textarea(attrs={"rows": 3}), "required_skills": forms.Textarea(attrs={"rows": 3})}

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("salary_min") and cleaned.get("salary_max") and cleaned["salary_min"] > cleaned["salary_max"]:
            raise forms.ValidationError("Maximum salary must be greater than minimum salary.")
        return cleaned
