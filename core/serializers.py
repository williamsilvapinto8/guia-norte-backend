from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    UserProfile, Business, BusinessStageHistory,
    StageStatus, FormResponse, Diagnosis, Experiment, User,
)
from django.core.validators import MinValueValidator, MaxValueValidator

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
class Meta:
    model = StageStatus
    fields = [
        'ideation_progress', 'plan_progress', 'mvp_progress', 'current_stage',
        'ideation_started_at', 'ideation_completed_at',
        'plan_started_at', 'plan_completed_at',
        'mvp_started_at', 'mvp_completed_at',
    ]
    read_only_fields = ['id', 'business']
