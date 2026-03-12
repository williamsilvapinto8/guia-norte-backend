# core/tests/test_n8n_stage_progress.py
import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from core.models import Business, StageStatus
from rest_framework import status
from unittest.mock import patch

User = get_user_model()

# Mock da permissão HasN8NAPIKey para testes
# Isso permite que o teste simule a validação da API Key sem precisar de uma chave real
@pytest.fixture(autouse=True)
def mock_n8n_api_key_permission():
    with patch('core.permissions.HasN8NAPIKey.has_permission', return_value=True) as mock_has_permission:
        yield mock_has_permission

@pytest.mark.django_db
def test_n8n_updates_stage_progress(api_client):
    # 1) Setup: Cria um usuário e um Business
    user = User.objects.create_user(username="n8nuser", email="n8n@example.com", password="SenhaForte123")
    business = Business.objects.create(owner=user, name="Negocio N8N", segment="Automação", stage="ideation")

    # Garante que o StageStatus existe para o Business
    stage_status = StageStatus.objects.create(
        business=business,
        current_stage="ideation",
        ideation_progress=10,
        plan_progress=0,
        mvp_progress=0
    )

    # 2) Endpoint e payload para atualização
    # O n8n não precisa logar, ele usa a API Key
    update_url = reverse("n8n-stage-progress-update", kwargs={"business_id": business.id})
    payload = {
        "ideation_progress": 50,
        "plan_progress": 25,
        "current_stage": "ideation" # Pode enviar o mesmo estágio ou um novo, se a lógica permitir
    }

    # 3) Chama o endpoint com o PATCH
    # A permissão HasN8NAPIKey é mockada para retornar True
    resp = api_client.patch(update_url, payload, format="json")

    # 4) Verifica a resposta
    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["business"] == business.id
    assert resp.data["ideation_progress"] == 50
    assert resp.data["plan_progress"] == 25
    assert resp.data["current_stage"] == "ideation"

    # 5) Verifica se o StageStatus foi atualizado no banco de dados
    stage_status.refresh_from_db()
    assert stage_status.ideation_progress == 50
    assert stage_status.plan_progress == 25
    assert stage_status.mvp_progress == 0 # Não foi alterado
    assert stage_status.current_stage == "ideation"

@pytest.mark.django_db
def test_n8n_updates_stage_progress_with_dates(api_client):
    # 1) Setup: Cria um usuário e um Business
    user = User.objects.create_user(username="n8nuser_dates", email="n8n_dates@example.com", password="SenhaForte123")
    business = Business.objects.create(owner=user, name="Negocio N8N Datas", segment="Automação", stage="plan")

    # Garante que o StageStatus existe para o Business
    stage_status = StageStatus.objects.create(
        business=business,
        current_stage="plan",
        ideation_progress=100,
        plan_progress=10,
        mvp_progress=0
    )

    # 2) Endpoint e payload para atualização, incluindo datas
    update_url = reverse("n8n-stage-progress-update", kwargs={"business_id": business.id})
    payload = {
        "plan_progress": 75,
        "plan_completed_at": "2026-03-12T10:00:00Z", # Exemplo de data
        "current_stage": "plan"
    }

    # 3) Chama o endpoint com o PATCH
    resp = api_client.patch(update_url, payload, format="json")

    # 4) Verifica a resposta
    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["business"] == business.id
    assert resp.data["plan_progress"] == 75
    assert resp.data["plan_completed_at"] == "2026-03-12T10:00:00Z"

    # 5) Verifica se o StageStatus foi atualizado no banco de dados
    stage_status.refresh_from_db()
    assert stage_status.plan_progress == 75
    assert stage_status.plan_completed_at.isoformat().startswith("2026-03-12T10:00:00") # Verifica a data

@pytest.mark.django_db
def test_n8n_progress_update_business_not_found(api_client):
    # ...
    resp = api_client.patch(update_url, payload, format="json")
assert resp.status_code == status.HTTP_404_NOT_FOUND
# Altere esta linha:
# assert "StageStatus não encontrado" in resp.data["detail"]
# Para uma destas opções:
assert resp.data["detail"] == "No StageStatus matches the given query." # Opção 1: Exata

@pytest.mark.django_db
def test_n8n_progress_update_invalid_data(api_client):
    # 1) Setup: Cria um usuário e um Business
    user = User.objects.create_user(username="n8nuser_invalid", email="n8n_invalid@example.com", password="SenhaForte123")
    business = Business.objects.create(owner=user, name="Negocio N8N Invalido", segment="Teste", stage="ideation")
    StageStatus.objects.create(business=business, current_stage="ideation")

    # 2) Endpoint e payload com dados inválidos (progresso > 100)
    update_url = reverse("n8n-stage-progress-update", kwargs={"business_id": business.id})
    payload = {"ideation_progress": 150} # Inválido

    resp = api_client.patch(update_url, payload, format="json")

    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "ideation_progress" in resp.data
    assert "Ensure this value is less than or equal to 100." in resp.data["ideation_progress"][0]
