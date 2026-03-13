from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    UserProfile, Business, BusinessStageHistory,
    StageStatus, FormResponse, Diagnosis, Experiment, User,
)
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import transaction # <-- Adicione este import para garantir atomicidade
from django.utils import timezone # <-- ADICIONE ESTE IMPORT

User = get_user_model()

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = '__all__'


class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = '__all__'
        read_only_fields = ['owner', 'created_at', 'updated_at']


class BusinessStageHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessStageHistory
        fields = '__all__'
        read_only_fields = ['changed_at']


class StageStatusSerializer(serializers.ModelSerializer):
    # Adicione este campo para garantir que o business_id seja incluído na saída
    # 'business' é o nome do campo ForeignKey no modelo StageStatus
    business = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = StageStatus
        fields = '__all__'
        # Ou, se preferir listar explicitamente:
        # fields = [
        #     'id', 'business', 'ideation_started_at', 'ideation_completed_at',
        #     'ideation_progress', 'plan_started_at', 'plan_completed_at',
        #     'plan_progress', 'mvp_started_at', 'mvp_completed_at',
        #     'mvp_progress', 'current_stage'
        # ]
        # read_only_fields = ['id'] # 'business' agora é read_only via PrimaryKeyRelatedField

class FormResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormResponse
        fields = '__all__'
        read_only_fields = ['author', 'created_at', 'updated_at']


class DiagnosisSerializer(serializers.ModelSerializer):
    class Meta:
        model = Diagnosis
        fields = '__all__'
        read_only_fields = ['created_at']


class ExperimentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Experiment
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, attrs):
        request = self.context.get('request')
        business = attrs.get('business')

        # Segurança extra: garante que o negócio pertence ao usuário
        if business and business.owner != request.user:
            raise serializers.ValidationError(
                {"business": "Você não tem permissão para criar experimentos para este negócio."}
            )

        # Regra da versão free: apenas 1 experimento por negócio
        existing_count = Experiment.objects.filter(business=business).count()
        if existing_count >= 1:
            raise serializers.ValidationError(
                {"non_field_errors": ["Na versão gratuita, você só pode cadastrar 1 experimento por negócio."]}
            )

        return attrs


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'password_confirm']
        read_only_fields = ['id']

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'As senhas não coincidem.'})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
        )
        # Cria o UserProfile automaticamente com role padrão
        UserProfile.objects.create(user=user, role='entrepreneur')
        return user
class StageStatusProgressUpdateSerializer(serializers.ModelSerializer):
    # Adicione os validadores explicitamente para os campos de progresso
    ideation_progress = serializers.IntegerField(
        required=False,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    plan_progress = serializers.IntegerField(
        required=False,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    mvp_progress = serializers.IntegerField(
        required=False,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    class Meta: # <-- ESTA CLASSE META É CRUCIAL E DEVE ESTAR AQUI!
        model = StageStatus
        fields = [ # Liste explicitamente todos os campos que podem ser atualizados
            'ideation_progress', 'plan_progress', 'mvp_progress', 'current_stage',
            'ideation_started_at', 'ideation_completed_at',
            'plan_started_at', 'plan_completed_at',
            'mvp_started_at', 'mvp_completed_at',
        ]
        # 'id' e 'business' não devem ser atualizados por este serializer,
        # mas serão incluídos na resposta final pelo StageStatusSerializer
        read_only_fields = ['id', 'business']
# --- NOVO SERIALIZER: OnboardingSerializer ---
class OnboardingSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, min_length=8, required=True)
    username = serializers.CharField(max_length=150, required=True)
    business_name = serializers.CharField(max_length=255, required=True)
    business_segment = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    initial_stage = serializers.ChoiceField(
        choices=Business.STAGE_CHOICES,
        default='ideation',
        required=False
    )

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Este e-mail já está em uso.")
        return value

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Este nome de usuário já está em uso.")
        return value

    @transaction.atomic # Garante que todas as operações de DB aconteçam ou nenhuma aconteça
    def create(self, validated_data):
        email = validated_data['email']
        password = validated_data['password']
        username = validated_data['username']
        business_name = validated_data['business_name']
        business_segment = validated_data.get('business_segment')
        initial_stage = validated_data.get('initial_stage', 'ideation')

        # 1. Cria o Usuário
        user = User.objects.create_user(
            email=email,
            username=username,
            password=password
        )
        UserProfile.objects.create(user=user, role='entrepreneur')

        # 2. Cria o Negócio
        business = Business.objects.create(
            owner=user,
            name=business_name,
            segment=business_segment,
            stage=initial_stage # Define o estágio inicial do negócio
        )

        # 3. Cria o StageStatus para o Negócio
        StageStatus.objects.create(
            business=business,
            current_stage=initial_stage,
            ideation_started_at=timezone.now() if initial_stage == 'ideation' else None,
            plan_started_at=timezone.now() if initial_stage == 'plan' else None,
            mvp_started_at=timezone.now() if initial_stage == 'mvp' else None,
            # Outros campos de progresso ficam com default 0
        )

        return {
            "user_id": user.id,
            "business_id": business.id,
            "message": "Cadastro e negócio criados com sucesso."
        }

    def update(self, instance, validated_data):
        # Este serializer é apenas para criação, não para atualização
        raise NotImplementedError("Este serializer não suporta operações de atualização.")
