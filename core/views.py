from rest_framework import status, viewsets, permissions, generics

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import extend_schema  # adicione esse import no topo

from .models import (
    UserProfile, Business, BusinessStageHistory,
    StageStatus, FormResponse, Diagnosis, Experiment
)
from .serializers import (
    UserProfileSerializer, BusinessSerializer, BusinessStageHistorySerializer,
    StageStatusSerializer, FormResponseSerializer, DiagnosisSerializer,
    ExperimentSerializer, RegisterSerializer, StageStatusProgressUpdateSerializer,
)

from .utils import advance_business_stage
from .permissions import HasN8NAPIKey

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
        form_response = serializer.save(author=self.request.user)

        business = form_response.business
        form_type = form_response.form_type

        # Regras simples de avanço de estágio
        if form_type == "plan":
            # tenta avançar de ideation -> plan
            advance_business_stage(business, target_stage="plan", changed_by=self.request.user)
        elif form_type == "mvp":
            # tenta avançar de plan -> mvp
            advance_business_stage(business, target_stage="mvp", changed_by=self.request.user)
        # se for ideation, mantemos como está (já nasce em ideation)


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

class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Já devolve os tokens JWT junto com o registro
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
            },
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)

class N8NHealthCheckView(APIView):
    """
    Endpoint simples para o n8n testar a autenticação via API Key.
    Não exige JWT — usa apenas a chave de API estática.
    """
    authentication_classes = []   # ignora autenticação JWT
    permission_classes = [HasN8NAPIKey]

    def get(self, request):
        return Response({
            "status": "ok",
            "mensagem": "Conexão com Guia Norte autenticada com sucesso!"
        })

class N8NStageStatusProgressUpdateView(generics.UpdateAPIView): # <-- Use generics.UpdateAPIView
    """
    Endpoint para o n8n atualizar progresso e/ou estágio de StageStatus de um Business.
    Autenticação via chave de API (HasN8NAPIKey).
    """
    permission_classes = [HasN8NAPIKey]
    serializer_class = StageStatusProgressUpdateSerializer # <-- Defina o serializer aqui
    lookup_field = 'business_id' # <-- Define qual campo da URL será usado para buscar o objeto
    queryset = StageStatus.objects.all() # <-- Define o queryset base
# O método PATCH já é tratado por UpdateAPIView.
# Precisamos sobrescrever get_object para buscar pelo business_id
def get_object(self):
    queryset = self.filter_queryset(self.get_queryset())
    # Garante que o StageStatus pertence ao business_id passado na URL
    obj = queryset.get(business_id=self.kwargs[self.lookup_field])
    self.check_object_permissions(self.request, obj)
    return obj

# O método update já é chamado por UpdateAPIView, que usa o serializer.save()
# A resposta já será o StageStatusSerializer(stage_status).data
# Para garantir que a resposta seja o StageStatus completo, vamos sobrescrever o update
def get_serializer_context(self):
    return {'request': self.request}

def get_response_serializer(self, instance):
    # Importa o StageStatusSerializer aqui para evitar circular import se necessário
    from .serializers import StageStatusSerializer
    return StageStatusSerializer(instance, context=self.get_serializer_context())

def update(self, request, *args, **kwargs):
    partial = kwargs.pop('partial', False)
    instance = self.get_object()
    serializer = self.get_serializer(instance, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    self.perform_update(serializer)

    if getattr(instance, '_prefetched_objects_cache', None):
        # If 'prefetch_related' has been applied to a queryset, we need to
        # forcibly invalidate the prefetch cache on the instance.
        instance._prefetched_objects_cache = {}

    # Usa o StageStatusSerializer para a resposta completa
    response_serializer = self.get_response_serializer(instance)
    return Response(response_serializer.data)
