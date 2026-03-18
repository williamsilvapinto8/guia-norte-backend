import requests
import os

N8N_DIAGNOSIS_WEBHOOK_URL = os.environ.get(
    'N8N_DIAGNOSIS_WEBHOOK_URL',
    'https://n8n.cocrias.com.br/webhook/diagnostico-ideacao'  # ajuste depois
)
N8N_API_KEY = os.environ.get('N8N_API_KEY', '')


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
    ExperimentSerializer, RegisterSerializer, StageStatusProgressUpdateSerializer, OnboardingSerializer, FormResponseCreateSerializer, BusinessContextSerializer, N8NDiagnosisCreateSerializer,
)

from .utils import advance_business_stage
from .permissions import HasN8NAPIKey

from django.conf import settings

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
    authentication_classes = []

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
    authentication_classes = []

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # O método create do serializer já lida com a criação de User, Business e StageStatus
        # Ele retorna um dicionário com user_id, business_id e message
        response_data = serializer.save() 
        
        try:
            requests.post(
                'https://n8n.cocrias.com.br/webhook/captura-inicial',
                json={
                    'nome': request.data.get('username'),
                    'email': request.data.get('email'),
                    'telefone_whatsapp': '',
                },
                timeout=5
            )
        except Exception as e:
            print(f'[AVISO] Falha ao notificar n8n boas-vindas: {e}')
        


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
        # Obtém o business_id da URL
        business_id = self.kwargs.get('business_id')
        try:
            business = Business.objects.get(id=business_id)
        except Business.DoesNotExist:
            raise Http404("Negócio não encontrado.")

        # Autor (se tiver JWT)
        author = self.request.user if self.request.user.is_authenticated else None

        if author and business.owner != author:
            raise permissions.PermissionDenied("Você não tem permissão para enviar respostas para este negócio.")

        # Salva o FormResponse
        form_response = serializer.save(business=business, author=author)

        # Lógica de avanço de estágio
        form_type = form_response.form_type
        if form_type == "plan":
            advance_business_stage(business, target_stage="plan", changed_by=author)
        elif form_type == "mvp":
            advance_business_stage(business, target_stage="mvp", changed_by=author)
        # ideation: mantém como está

        # >>> NOTIFICAÇÃO PARA N8N (apenas para ideation) <<<
        if form_type == "ideation" and N8N_DIAGNOSIS_WEBHOOK_URL:
            payload = {
                "business_id": business.id,
                "form_response_id": form_response.id,
                # se quiser já mandar um prompt-base ou qualquer outra info extra
            }
            headers = {
                "Content-Type": "application/json",
            }
            if N8N_API_KEY:
                headers["X-API-Key"] = N8N_API_KEY

            try:
                resp = requests.post(
                    N8N_DIAGNOSIS_WEBHOOK_URL,
                    json=payload,
                    headers=headers,
                    timeout=20,
                )
                print(
                    f"[DEBUG] Notificação n8n enviada. "
                    f"Status={resp.status_code}, Body={resp.text[:300]}"
                )
            except Exception as e:
                # Não quebra o fluxo do usuário; só loga o problema
                print(f"[ERRO] Falha ao notificar n8n para diagnóstico: {e}")
        # <<< FIM NOTIFICAÇÃO >>>

# --- NOVA VIEW: N8NBusinessContextView ---
class N8NBusinessContextView(generics.RetrieveAPIView):
    """
    Endpoint para o n8n buscar o contexto completo de um negócio para a IA.
    Inclui dados do Business, StageStatus e as últimas FormResponses por tipo.
    Autenticação via chave de API (HasN8NAPIKey).
    """
    permission_classes = [HasN8NAPIKey]
    serializer_class = BusinessContextSerializer
    queryset = Business.objects.all() # Define o queryset base
    lookup_field = 'id' # O campo que será usado para buscar o negócio na URL

    def get_object(self):
        # Sobrescreve get_object para buscar o Business pelo business_id da URL
        business_id = self.kwargs.get('business_id')
        try:
            # Prefetch related objects para evitar N+1 queries
            business = self.queryset.select_related('owner', 'stage_status').prefetch_related('form_responses').get(id=business_id)
        except Business.DoesNotExist:
            raise Http404("Negócio não encontrado para o ID fornecido.")
        return business

class N8NDiagnosisCreateView(generics.CreateAPIView):
    """
    Endpoint para o n8n registrar diagnósticos gerados pela IA.
    Autenticação via chave de API (HasN8NAPIKey).
    """
    permission_classes = [HasN8NAPIKey]
    serializer_class = N8NDiagnosisCreateSerializer

    def create(self, request, *args, **kwargs):
        # usamos o CreateAPIView padrão, só expondo o serializer
        return super().create(request, *args, **kwargs)

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

        # --- LÓGICA PARA NOTIFICAR O N8N ---
        if form_type == "ideation": # Só notifica para formulários de ideação
            n8n_webhook_url = settings.N8N_DIAGNOSIS_WEBHOOK_URL
            n8n_api_key = settings.N8N_API_KEY

            if n8n_webhook_url: # Garante que a URL está configurada
                payload = {
                    "business_id": business.id,
                    "form_response_id": form_response.id,
                    "form_type": form_response.form_type,
                    "form_version": form_response.form_version,
                }
                headers = {
                    "Content-Type": "application/json",
                    # Adiciona a API Key apenas se ela estiver configurada
                    **({"X-API-Key": n8n_api_key} if n8n_api_key else {})
                }

                try:
                    # Dispara a requisição POST para o webhook do n8n
                    response = requests.post(n8n_webhook_url, json=payload, headers=headers, timeout=5)
                    response.raise_for_status() # Levanta um erro para status codes 4xx/5xx
                    print(f"DEBUG: Notificação para n8n enviada com sucesso para {n8n_webhook_url}. Resposta: {response.status_code}")
                except requests.exceptions.RequestException as e:
                    print(f"ERRO: Falha ao notificar n8n sobre FormResponse {form_response.id}: {e}")
                except Exception as e:
                    print(f"ERRO INESPERADO ao notificar n8n: {e}")
