from django.urls import path  
from rest_framework.routers import DefaultRouter
from .views import (
    UserProfileViewSet, BusinessViewSet, BusinessStageHistoryViewSet,
    StageStatusViewSet, FormResponseViewSet, DiagnosisViewSet,
    ExperimentViewSet, N8NHealthCheckView, N8NStageStatusProgressUpdateView, FormResponseCreateAPIView, N8NBusinessContextView,
)

router = DefaultRouter()
router.register(r'profiles', UserProfileViewSet, basename='profile')
router.register(r'businesses', BusinessViewSet, basename='business')
router.register(r'stage-history', BusinessStageHistoryViewSet, basename='stage-history')
router.register(r'stage-status', StageStatusViewSet, basename='stage-status')
router.register(r'form-responses', FormResponseViewSet, basename='form-response')
router.register(r'diagnoses', DiagnosisViewSet, basename='diagnosis')
router.register(r'experiments', ExperimentViewSet, basename='experiment')

urlpatterns = [
    path('n8n/health/', N8NHealthCheckView.as_view(), name='n8n-health'),
    path('n8n/businesses/<int:business_id>/stage-progress/',N8NStageStatusProgressUpdateView.as_view(),name='n8n-stage-progress-update'),
    path('businesses/<int:business_id>/form-responses/',FormResponseCreateAPIView.as_view(),name='business-form-response-create'), # <-- ADICIONE ESTA LINHA
    path('n8n/businesses/<int:business_id>/context/',N8NBusinessContextView.as_view(),name='n8n-business-context', # --- NOVA URL: Endpoint para o n8n buscar contexto da IA ---
    ),
] + router.urls
