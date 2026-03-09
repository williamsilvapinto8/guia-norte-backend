from django.conf import settings
from django.db import models

User = settings.AUTH_USER_MODEL  # permite trocar o modelo de usuário no futuro


class UserProfile(models.Model):
    """
    Perfil estendido do usuário, com papéis (empreendedor, mentor, admin).
    """
    ROLE_CHOICES = (
        ('entrepreneur', 'Empreendedor'),
        ('mentor', 'Mentor'),
        ('admin', 'Admin'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='entrepreneur',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user} ({self.get_role_display()})'


class Business(models.Model):
    """
    Representa um negócio do usuário (pode ter mais de um por usuário).
    Contém os dados mestres que alimentam os prompts.
    """
    STAGE_CHOICES = (
        ('ideation', 'Ideação'),
        ('plan', 'Plano'),
        ('mvp', 'MVP'),
        ('operation', 'Operação'),
    )

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='businesses')

    name = models.CharField(max_length=255)
    segment = models.CharField(max_length=255, blank=True, null=True)

    business_type = models.CharField(
        max_length=20,
        choices=(
            ('physical', 'Físico'),
            ('online', 'Online'),
            ('hybrid', 'Híbrido'),
        ),
        blank=True,
        null=True,
    )

    stage = models.CharField(
        max_length=20,
        choices=STAGE_CHOICES,
        default='ideation',
    )

    city = models.CharField(max_length=120, blank=True, null=True)
    state = models.CharField(max_length=2, blank=True, null=True)  # UF

    has_cnpj = models.BooleanField(default=False)
    revenue_range = models.CharField(max_length=50, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class BusinessStageHistory(models.Model):
    """
    Histórico de mudanças de estágio do negócio (para auditoria e análise).
    """
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='stage_history')

    from_stage = models.CharField(
        max_length=20,
        choices=Business.STAGE_CHOICES,
        blank=True,
        null=True,
    )
    to_stage = models.CharField(
        max_length=20,
        choices=Business.STAGE_CHOICES,
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stage_changes',
    )

    def __str__(self):
        return f'{self.business.name}: {self.from_stage} -> {self.to_stage} em {self.changed_at}'


class StageStatus(models.Model):
    """
    Status de progresso de cada etapa (Ideação, Plano, MVP) para um negócio.
    Guarda datas de início/conclusão e percentual de progresso.
    """
    CURRENT_STAGE_CHOICES = (
        ('ideation', 'Ideação'),
        ('plan', 'Plano'),
        ('mvp', 'MVP'),
        ('done', 'Concluído'),
    )

    business = models.OneToOneField(Business, on_delete=models.CASCADE, related_name='stage_status')

    ideation_started_at = models.DateTimeField(blank=True, null=True)
    ideation_completed_at = models.DateTimeField(blank=True, null=True)
    ideation_progress = models.PositiveIntegerField(default=0)  # 0 a 100

    plan_started_at = models.DateTimeField(blank=True, null=True)
    plan_completed_at = models.DateTimeField(blank=True, null=True)
    plan_progress = models.PositiveIntegerField(default=0)  # 0 a 100

    mvp_started_at = models.DateTimeField(blank=True, null=True)
    mvp_completed_at = models.DateTimeField(blank=True, null=True)
    mvp_progress = models.PositiveIntegerField(default=0)  # 0 a 100

    current_stage = models.CharField(
        max_length=20,
        choices=CURRENT_STAGE_CHOICES,
        default='ideation',
    )

    def __str__(self):
        return f'Status de etapas - {self.business.name}'


class FormResponse(models.Model):
    """
    Respostas dos formulários de cada etapa (Ideação, Plano, MVP).
    Genérico, com conteúdo em JSON, incluindo versão do formulário.
    """
    FORM_TYPE_CHOICES = (
        ('ideation', 'Ideação'),
        ('plan', 'Plano de Negócios'),
        ('mvp', 'MVP'),
    )

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='form_responses')
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    form_type = models.CharField(max_length=20, choices=FORM_TYPE_CHOICES)

    # versão do formulário (ex.: 1.0, 1.1), importante para quando perguntas mudarem
    form_version = models.CharField(max_length=10, default='1.0')

    # respostas do formulário (todas as perguntas num dict/json)
    data = models.JSONField()

    is_active = models.BooleanField(default=True)  # permite arquivar versões antigas

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.business.name} - {self.get_form_type_display()} ({self.form_version})'


class Diagnosis(models.Model):
    """
    Diagnósticos gerados pela IA para Ideação, Plano e MVP.
    """
    DIAGNOSIS_TYPE_CHOICES = (
        ('ideation', 'Ideação'),
        ('plan', 'Plano de Negócios'),
        ('mvp', 'MVP'),
    )

    STATUS_CHOICES = (
        ('pending', 'Pendente'),
        ('processing', 'Processando'),
        ('done', 'Concluído'),
        ('error', 'Erro'),
    )

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='diagnoses')
    form_response = models.ForeignKey(
        FormResponse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='diagnoses',
    )

    diagnosis_type = models.CharField(max_length=20, choices=DIAGNOSIS_TYPE_CHOICES)

    # versão do "modelo de diagnóstico" (prompt v1.0, v1.1, etc.)
    diagnosis_version = models.CharField(max_length=10, default='1.0')

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
    )
    error_message = models.TextField(blank=True, null=True)

    content = models.TextField(blank=True, null=True)  # texto gerado pela IA
    raw_response = models.JSONField(blank=True, null=True)  # resposta bruta da IA, se vier em JSON

    is_free = models.BooleanField(default=True)

    # metadados opcionais (úteis para custo/monitoramento da IA)
    tokens_used = models.IntegerField(blank=True, null=True)
    model_name = models.CharField(max_length=50, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.business.name} - {self.get_diagnosis_type_display()} ({self.diagnosis_version})'


class Experiment(models.Model):
    """
    Experimentos de MVP.
    Na versão free, você vai restringir para 1 experimento por negócio na regra de negócio.
    """
    EXPERIMENT_STATUS_CHOICES = (
        ('planned', 'Planejado'),
        ('running', 'Em andamento'),
        ('finished', 'Concluído'),
        ('cancelled', 'Cancelado'),
    )

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='experiments')

    name = models.CharField(max_length=255)
    hypothesis = models.TextField()
    experiment_type = models.CharField(max_length=50, blank=True, null=True)  # entrevista, landing, etc.

    target_audience = models.TextField(blank=True, null=True)
    channels = models.TextField(blank=True, null=True)  # ex.: "Instagram, WhatsApp"

    success_metrics = models.TextField(blank=True, null=True)
    expected_duration_days = models.IntegerField(blank=True, null=True)

    status = models.CharField(
        max_length=20,
        choices=EXPERIMENT_STATUS_CHOICES,
        default='planned',
    )

    results = models.TextField(blank=True, null=True)  # resumo dos resultados

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Experimento {self.name} - {self.business.name}'
