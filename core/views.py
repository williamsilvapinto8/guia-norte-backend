from rest_framework import viewsets, permissions, generics, status
from .models import (
    UserProfile, Business, BusinessStageHistory,
    StageStatus, FormResponse, Diagnosis, Experiment
)
from .serializers import (
    UserProfileSerializer, BusinessSerializer, BusinessStageHistorySerializer,
    StageStatusSerializer, FormResponseSerializer, DiagnosisSerializer,
    ExperimentSerializer, RegisterSerializer
)

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response
#Adicionados em 11/03, essa lista abaixo e class N8NWebhookReceiver
from rest_framework.views import APIView
from rest_framework import status
from .permissions import HasN8NAPIKey
from drf_spectacular.utils import extend_schema  # adicione esse import no topo


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
'''
class N8NWebhookReceiver(APIView):
    # Aqui está o segredo: usamos a permissão da API Key em vez do JWT
    permission_classes = [HasN8NAPIKey] 

    def post(self, request):
        # Aqui entrará a lógica para criar o User/Business 
        # ou atualizar o Diagnosis
        dados = request.data

        return Response(
            {"mensagem": "Dados recebidos com sucesso pelo n8n!"}, 
            status=status.HTTP_200_OK
        )
'''
