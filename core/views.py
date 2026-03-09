from rest_framework import viewsets, permissions
from .models import (
    UserProfile, Business, BusinessStageHistory,
    StageStatus, FormResponse, Diagnosis, Experiment
)
from .serializers import (
    UserProfileSerializer, BusinessSerializer, BusinessStageHistorySerializer,
    StageStatusSerializer, FormResponseSerializer, DiagnosisSerializer,
    ExperimentSerializer
)


class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]


class BusinessViewSet(viewsets.ModelViewSet):
    serializer_class = BusinessSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Business.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class BusinessStageHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BusinessStageHistorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return BusinessStageHistory.objects.filter(
            business__owner=self.request.user
        )


class StageStatusViewSet(viewsets.ModelViewSet):
    serializer_class = StageStatusSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return StageStatus.objects.filter(
            business__owner=self.request.user
        )


class FormResponseViewSet(viewsets.ModelViewSet):
    serializer_class = FormResponseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return FormResponse.objects.filter(
            business__owner=self.request.user
        )

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class DiagnosisViewSet(viewsets.ModelViewSet):
    serializer_class = DiagnosisSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Diagnosis.objects.filter(
            business__owner=self.request.user
        )


class ExperimentViewSet(viewsets.ModelViewSet):
    serializer_class = ExperimentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Experiment.objects.filter(
            business__owner=self.request.user
        )
