from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

from .models import Profile


class SignInForm(AuthenticationForm):
    username = forms.EmailField(label="Email address")


class SignUpForm(UserCreationForm):
    role = forms.ChoiceField(choices=Profile.Role.choices, widget=forms.HiddenInput())
    email = forms.EmailField(label="Email address")
    full_name = forms.CharField(label="Full name", required=False)
    phone = forms.CharField(label="Phone number", required=False)
    company_name = forms.CharField(label="Company name", required=False)

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
            )
        return user
