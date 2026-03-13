from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    UserProfile, Business, BusinessStageHistory,
    StageStatus, FormResponse, Diagnosis, Experiment, User,
)
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import transaction # <-- Adicione este import para garantir atomicidade
from django.utils import timezone # <-- ADICIONE ESTE IMPORT
from rest_framework.exceptions import ValidationError # <-- ADICIONE ESTE IMPORT

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


class N8NDiagnosisCreateSerializer(serializers.ModelSerializer):
    """
    Serializer para o n8n criar diagnósticos gerados pela IA.
    """
    business_id = serializers.IntegerField(write_only=True)
    form_response_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Diagnosis
        fields = [
            'id',
            'business_id',
            'form_response_id',
            'diagnosis_type',
            'diagnosis_version',
            'status',
            'error_message',
            'content',
            'raw_response',
            'is_free',
            'tokens_used',
            'model_name',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def validate(self, attrs):
        business_id = attrs.get('business_id')
        form_response_id = attrs.get('form_response_id')

        # valida negócio
        try:
            business = Business.objects.get(id=business_id)
        except Business.DoesNotExist:
            raise serializers.ValidationError({"business_id": "Negócio não encontrado."})

        attrs['business'] = business

        # valida (opcionalmente) o form_response
        if form_response_id is not None:
            try:
                form_response = FormResponse.objects.get(id=form_response_id, business=business)
            except FormResponse.DoesNotExist:
                raise serializers.ValidationError(
                    {"form_response_id": "FormResponse não encontrado para este negócio."}
                )
            attrs['form_response'] = form_response

        return attrs

    def create(self, validated_data):
        # remover campos auxiliares
        validated_data.pop('business_id', None)
        validated_data.pop('form_response_id', None)
        return Diagnosis.objects.create(**validated_data)

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

# --- NOVO SERIALIZER: FormResponseCreateSerializer ---
class FormResponseCreateSerializer(serializers.ModelSerializer):
    # O campo 'business' será fornecido pela view, não pelo payload.
    # Definimos como required=False para que o serializer não o exija no data.
    business = serializers.PrimaryKeyRelatedField(queryset=Business.objects.all(), required=False) # <-- ALTERAÇÃO AQUI

    data = serializers.JSONField(required=True)

    class Meta:
        model = FormResponse
        fields = ['business', 'form_type', 'form_version', 'data']
        read_only_fields = ['author']

    def validate(self, attrs):
        # A validação de business agora será feita na view,
        # pois o business_id vem da URL e é injetado.
        # Podemos remover a validação de 'business' daqui ou ajustá-la.
        # Por enquanto, vamos manter a validação de form_type.

        form_type = attrs.get('form_type')
        if form_type not in [choice[0] for choice in FormResponse.FORM_TYPE_CHOICES]:
            raise ValidationError({"form_type": "Tipo de formulário inválido."})

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        # O business e o author são passados explicitamente pela view.
        # Removemos eles de validated_data para evitar duplicidade se por acaso
        # viessem no payload (o que não deveriam, mas é uma boa prática).
        business = validated_data.pop('business', None)
        author = validated_data.pop('author', None) # author também é passado pela view

        if not business:
            raise ValidationError({"business": "O negócio deve ser fornecido."})

        form_response = FormResponse.objects.create(business=business, author=author, **validated_data)
        return form_response

# --- NOVO SERIALIZER: BusinessContextSerializer ---
class BusinessContextSerializer(serializers.ModelSerializer):
    # Serializer aninhado para o StageStatus
    stage_status = StageStatusSerializer(read_only=True)

    # Serializer aninhado para as FormResponses (pode ser uma lista)
    # Usaremos o FormResponseSerializer existente, mas podemos customizá-lo se necessário
    # Este campo será substituído por 'latest_form_responses' no to_representation
    form_responses = FormResponseSerializer(many=True, read_only=True)

    # Opcional: Adicionar o email do owner diretamente para facilitar o prompt
    owner_email = serializers.EmailField(source='owner.email', read_only=True)
    owner_username = serializers.CharField(source='owner.username', read_only=True)

    class Meta:
        model = Business
        fields = [
            'id', 'name', 'segment', 'business_type', 'stage', 'city', 'state',
            'has_cnpj', 'revenue_range', 'owner_email', 'owner_username',
            'stage_status', 'form_responses', # Campos aninhados
            'created_at', 'updated_at'
        ]
        read_only_fields = fields # Este serializer é apenas para leitura

    def to_representation(self, instance):
        """
        Sobrescreve to_representation para filtrar form_responses por form_type
        e garantir que apenas as mais recentes sejam incluídas, se desejado.
        """
        representation = super().to_representation(instance)

        # Filtra as respostas do formulário para incluir apenas as mais recentes de cada tipo
        # e organizá-las por tipo para facilitar o consumo pelo n8n/IA.
        filtered_form_responses = {}
        for form_type_choice, _ in FormResponse.FORM_TYPE_CHOICES:
            # Pega a resposta mais recente para cada tipo de formulário
            latest_response = instance.form_responses.filter(
                form_type=form_type_choice,
                is_active=True # Considera apenas respostas ativas
            ).order_by('-created_at').first()

            if latest_response:
                # Usa o FormResponseSerializer para serializar a resposta individual
                filtered_form_responses[f'{form_type_choice}_form_response'] = FormResponseSerializer(latest_response).data
            else:
                filtered_form_responses[f'{form_type_choice}_form_response'] = None # Ou um dicionário vazio

        representation['latest_form_responses'] = filtered_form_responses
        # Remove o campo 'form_responses' original que continha todas as respostas
        representation.pop('form_responses', None)

        return representation
