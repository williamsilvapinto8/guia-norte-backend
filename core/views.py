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
    ExperimentSerializer, RegisterSerializer, StageStatusProgressUpdateSerializer, OnboardingSerializer, FormResponseCreateSerializer,
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

class FormResponseCreateAPIView(generics.CreateAPIView):
    """
    Endpoint para receber respostas de formulários (Ideação, Plano, MVP).
    Pode ser usado pelo frontend (com JWT) ou pelo n8n (com API Key).
    """
    serializer_class = FormResponseCreateSerializer
    permission_classes = [permissions.IsAuthenticated | HasN8NAPIKey]

    def get_serializer_context(self):
        """
        Adiciona o business_id da URL ao contexto do serializer.
        """
        context = super().get_serializer_context()
        context['business_id'] = self.kwargs.get('business_id')
        return context

    def perform_create(self, serializer):
        # Obtém o business_id do contexto (que veio da URL)
        business_id = self.kwargs.get('business_id')
        try:
            business = Business.objects.get(id=business_id)
        except Business.DoesNotExist:
            raise Http404("Negócio não encontrado.")

        # O autor da resposta é o usuário logado (se houver)
        author = self.request.user if self.request.user.is_authenticated else None

        # Validação de permissão extra: garante que o usuário tem acesso ao negócio
        # (Isso já é feito no serializer, mas reforçar aqui não faz mal)
        if author and business.owner != author:
            raise permissions.PermissionDenied("Você não tem permissão para enviar respostas para este negócio.")

        # Salva o FormResponse, passando o business e o author
        form_response = serializer.save(business=business, author=author)

        # Lógica de avanço de estágio
        form_type = form_response.form_type
        if form_type == "plan":
            advance_business_stage(business, target_stage="plan", changed_by=author)
        elif form_type == "mvp":
            advance_business_stage(business, target_stage="mvp", changed_by=author)
        # se for ideation, mantemos como está (já nasce em ideation)

        # Opcional: Disparar um evento para o n8n aqui, informando que um formulário foi enviado.
        # Isso seria feito com uma requisição HTTP para um webhook do n8n.
        # Ex: requests.post("https://seu-n8n.com/webhook/form-submitted", json={"form_response_id": form_response.id})
