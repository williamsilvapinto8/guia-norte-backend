# core/utils.py
from django.utils import timezone
from .models import Business, BusinessStageHistory, StageStatus

# ordem oficial da jornada
STAGE_FLOW = ["ideation", "plan", "mvp", "operation"]


def can_advance_stage(current_stage: str, target_stage: str) -> bool:
    """
    Garante avanço apenas na ordem correta (sem pular nem retroceder).
    """
    try:
        current_index = STAGE_FLOW.index(current_stage)
        target_index = STAGE_FLOW.index(target_stage)
    except ValueError:
        return False

    # só permite avançar exatamente 1 passo (ideation -> plan, plan -> mvp, mvp -> operation)
    return target_index == current_index + 1


def advance_business_stage(business: Business, target_stage: str, changed_by=None):
    """
    Avança o estágio do Business e mantém BusinessStageHistory + StageStatus coerentes.
    Não permite pular estágio nem retroceder.
    Retorna o objeto StageStatus atualizado.
    """
    current_stage = business.stage

    if not can_advance_stage(current_stage, target_stage):
        # nada faz se a transição não for válida
        return None

    now = timezone.now()

    # 1) Atualiza o Business
    business.stage = target_stage
    business.save(update_fields=["stage", "updated_at"])

    # 2) Registra histórico
    BusinessStageHistory.objects.create(
        business=business,
        from_stage=current_stage,
        to_stage=target_stage,
        changed_by=changed_by,
    )

    # 3) Atualiza/Cria StageStatus
    stage_status, _created = StageStatus.objects.get_or_create(business=business)

    # Marca datas + progressos básicos
    if target_stage == "plan":
        if not stage_status.plan_started_at:
            stage_status.plan_started_at = now
        stage_status.ideation_completed_at = now
        stage_status.ideation_progress = 100
																				  
        stage_status.plan_progress = 0 # Inicia o progresso do plano

    elif target_stage == "mvp":
        if not stage_status.mvp_started_at:
            stage_status.mvp_started_at = now
        stage_status.plan_completed_at = now
        stage_status.plan_progress = 100
        stage_status.mvp_progress = 0 # Inicia o progresso do mvp

    elif target_stage == "operation":
														 
        if not stage_status.mvp_completed_at: # Pode ser que o MVP não tenha sido "completado" formalmente
            stage_status.mvp_completed_at = now
        stage_status.mvp_progress = 100
        stage_status.current_stage = "done" # Marca como concluído

									  
												   
    stage_status.current_stage = target_stage
									 
    stage_status.save()

					   
    return stage_status
