from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    UserProfile, Business, BusinessStageHistory,
    StageStatus, FormResponse, Diagnosis, Experiment,
)

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
    class Meta:
        model = StageStatus
        fields = '__all__'


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
class StageStatusProgressUpdateSerializer(serializers.Serializer):
    ideation_progress = serializers.IntegerField(required=False, min_value=0, max_value=100)
    plan_progress = serializers.IntegerField(required=False, min_value=0, max_value=100)
    mvp_progress = serializers.IntegerField(required=False, min_value=0, max_value=100)
    current_stage = serializers.ChoiceField(
        required=False,
        choices=StageStatus._meta.get_field("current_stage").choices,
    )

    def update(self, instance, validated_data):
        # aplica apenas campos enviados
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance

    def create(self, validated_data):
        # não usaremos create neste endpoint
        raise NotImplementedError("Use apenas para update")
