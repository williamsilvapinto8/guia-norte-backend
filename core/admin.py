from django.contrib import admin
from .models import (
    UserProfile,
    Business,
    BusinessStageHistory,
    StageStatus,
    FormResponse,
    Diagnosis,
    Experiment,
)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'created_at')
    list_filter = ('role',)
    search_fields = ('user__username', 'user__email')


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'segment', 'stage', 'city', 'state', 'has_cnpj')
    list_filter = ('stage', 'segment', 'has_cnpj', 'state')
    search_fields = ('name', 'owner__username', 'owner__email')


@admin.register(BusinessStageHistory)
class BusinessStageHistoryAdmin(admin.ModelAdmin):
    list_display = ('business', 'from_stage', 'to_stage', 'changed_at', 'changed_by')
    list_filter = ('from_stage', 'to_stage')
    search_fields = ('business__name',)


@admin.register(StageStatus)
class StageStatusAdmin(admin.ModelAdmin):
    list_display = (
        'business',
        'current_stage',
        'ideation_progress',
        'plan_progress',
        'mvp_progress',
    )
    list_filter = ('current_stage',)


@admin.register(FormResponse)
class FormResponseAdmin(admin.ModelAdmin):
    list_display = ('business', 'form_type', 'form_version', 'created_at', 'is_active')
    list_filter = ('form_type', 'form_version', 'is_active')
    search_fields = ('business__name',)
    readonly_fields = ('data',)


@admin.register(Diagnosis)
class DiagnosisAdmin(admin.ModelAdmin):
    list_display = (
        'business',
        'diagnosis_type',
        'diagnosis_version',
        'status',
        'is_free',
        'created_at',
    )
    list_filter = ('diagnosis_type', 'status', 'is_free')
    search_fields = ('business__name',)
    readonly_fields = ('content', 'raw_response', 'error_message')


@admin.register(Experiment)
class ExperimentAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'experiment_type', 'status', 'created_at')
    list_filter = ('status', 'experiment_type')
    search_fields = ('name', 'business__name')
