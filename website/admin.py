from django.contrib import admin, messages
from django.utils import timezone

from .models import (
    AuditLog, CandidateDocument, CandidateMatch, Notification,
    Payment, Profile, Qualification, RecruitmentRequest,
    ReplacementRequest, Shortlist, Specialization, Subscription,
)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display  = ("user", "role", "verification_status", "specialization_names", "company_name")
    list_filter   = ("role", "verification_status", "availability")
    search_fields = ("user__username", "user__email", "legal_name", "company_name")
    filter_horizontal = ("specializations",)
    actions = ("mark_under_verification", "mark_vetted_and_verified", "request_changes")

    @admin.display(description="Specializations")
    def specialization_names(self, obj):
        return ", ".join(obj.specializations.values_list("name", flat=True))

    @admin.action(description="Move selected candidates to Under Verification")
    def mark_under_verification(self, request, queryset):
        candidates = queryset.filter(role=Profile.Role.CANDIDATE)
        candidates.update(verification_status=Profile.VerificationStatus.VERIFYING)
        for profile in candidates:
            profile.notify(
                title="Profile received for review",
                message="Our team is now reviewing your CV and credentials. We'll update you as soon as the process is complete.",
                kind=Notification.Kind.VERIFICATION,
            )
        self.message_user(request, f"{candidates.count()} candidate profiles moved to verification.", messages.SUCCESS)

    @admin.action(description="Mark selected candidates Vetted & Verified")
    def mark_vetted_and_verified(self, request, queryset):
        candidates = queryset.filter(role=Profile.Role.CANDIDATE)
        candidates.update(verification_status=Profile.VerificationStatus.VERIFIED, verified_at=timezone.now())
        for profile in candidates:
            profile.notify(
                title="Profile verified — you're in the talent pool!",
                message="Congratulations! Your professional profile is now Vetted & Verified and has been added to the JobSPACE talent pool. You may now be matched with top employers.",
                kind=Notification.Kind.VERIFICATION,
            )
        self.message_user(request, f"{candidates.count()} candidate profiles verified.", messages.SUCCESS)

    @admin.action(description="Request changes from selected candidates")
    def request_changes(self, request, queryset):
        candidates = queryset.filter(role=Profile.Role.CANDIDATE)
        candidates.update(verification_status=Profile.VerificationStatus.CHANGES)
        for profile in candidates:
            profile.notify(
                title="Action required — profile needs updates",
                message="Our review team has flagged your profile for changes. Please log in and update the relevant sections before resubmitting.",
                kind=Notification.Kind.PROFILE,
            )
        self.message_user(request, f"{candidates.count()} candidates notified about required changes.", messages.WARNING)


admin.site.register(Specialization)
admin.site.register(Qualification)
admin.site.register(CandidateDocument)
admin.site.register(Notification)
admin.site.register(Payment)
admin.site.register(Subscription)
admin.site.register(ReplacementRequest)
admin.site.register(AuditLog)


@admin.register(Shortlist)
class ShortlistAdmin(admin.ModelAdmin):
    list_display  = ("employer", "candidate", "status", "created_at")
    list_filter   = ("status",)
    search_fields = ("employer__company_name", "candidate__legal_name", "candidate__user__email")


@admin.register(RecruitmentRequest)
class RecruitmentRequestAdmin(admin.ModelAdmin):
    list_display  = ("position", "employer", "professionals_required", "status", "created_at")
    list_filter   = ("status", "position", "salary_period")
    search_fields = ("position", "employer__company_name", "required_skills")
    list_editable = ("status",)


@admin.register(CandidateMatch)
class CandidateMatchAdmin(admin.ModelAdmin):
    list_display  = ("profile", "employer", "is_active", "created_at")
    list_filter   = ("is_active",)
    search_fields = ("profile__user__email", "employer__company_name")

    def save_model(self, request, obj, form, change):
        if obj.profile.role != Profile.Role.CANDIDATE or obj.employer.role != Profile.Role.EMPLOYER:
            raise ValueError("Matches must connect a candidate profile to an employer profile.")
        super().save_model(request, obj, form, change)
        # Notify the candidate that a match was created
        obj.profile.notify(
            title="You have a potential opportunity!",
            message=f"Your professional profile has been selected for a potential opportunity with {obj.employer.company_name or 'an employer'}. Log in to view details.",
            kind=Notification.Kind.MATCH,
        )
        # Notify the employer that a candidate was pushed to them
        obj.employer.notify(
            title="A candidate profile has been pushed to you",
            message="A vetted candidate matching one of your recruitment requests has been added to your Candidates Received list.",
            kind=Notification.Kind.MATCH,
        )
