from django.http import Http404
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


class N8NStageStatusProgressUpdateView(generics.UpdateAPIView):
    """
    Endpoint para o n8n atualizar progresso e/ou estágio de StageStatus de um Business.
    Autenticação via chave de API (HasN8NAPIKey).
    """
    permission_classes = [HasN8NAPIKey]
    serializer_class = StageStatusProgressUpdateSerializer
    lookup_field = 'business_id'
    queryset = StageStatus.objects.all()
    def get_object(self):
            queryset = self.filter_queryset(self.get_queryset())
            try:
                obj = queryset.get(business_id=self.kwargs[self.lookup_field])
            except StageStatus.DoesNotExist: # <-- Capture a exceção específica
                raise Http404("StageStatus não encontrado para este business.") # <-- Levante Http404
            self.check_object_permissions(self.request, obj)
            return obj

    def get_serializer_context(self):
        return {'request': self.request}

    def get_response_serializer(self, instance):
        from .serializers import StageStatusSerializer
        return StageStatusSerializer(instance, context=self.get_serializer_context())

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}

        response_serializer = self.get_response_serializer(instance)

        # --- ADICIONE ESTAS DUAS LINHAS PARA DEPURAR ---
        print(f"\n--- DEBUG: Response data from N8NStageStatusProgressUpdateView ---")
        print(response_serializer.data)
        print(f"--- END DEBUG ---\n")
        # ------------------------------------------------

        return Response(response_serializer.data)

class OnboardingView(generics.CreateAPIView):
    """
    Endpoint para o formulário de captura/pré-cadastro.
    Cria um novo usuário, um negócio e o status inicial de estágio.
    """
    serializer_class = OnboardingSerializer
    permission_classes = [permissions.AllowAny] # Este endpoint é público para novos cadastros

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # O método create do serializer já lida com a criação de User, Business e StageStatus
        # Ele retorna um dicionário com user_id, business_id e message
        response_data = serializer.save() 

        # Opcional: Se você quiser retornar tokens JWT automaticamente após o onboarding,
        # você pode replicar a lógica da RegisterView aqui.
        # Por enquanto, vamos retornar apenas o que o serializer.save() já nos dá.

        return Response(response_data, status=status.HTTP_201_CREATED)
