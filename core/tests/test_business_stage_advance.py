# core/tests/test_business_stage_advance.py
import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from core.models import Business, FormResponse, BusinessStageHistory, StageStatus
from rest_framework import status

User = get_user_model()

@pytest.mark.django_db
def test_advance_stage_from_ideation_to_plan_on_form_response(api_client):
    # 1) Setup: Cria um usuário e um Business no estágio inicial (ideation)
    user = User.objects.create_user(username="testuser_stage", email="stage@example.com", password="SenhaForte123")
    business = Business.objects.create(owner=user, name="Negocio Teste Estagio", segment="Serviços", stage="ideation")

    # Garante que o StageStatus inicial existe e está em ideation
    StageStatus.objects.create(business=business, current_stage="ideation")

    # 2) Login do usuário
    login_url = reverse("token_obtain_pair")
    resp_login = api_client.post(
        login_url,
        {"username": "testuser_stage", "password": "SenhaForte123"},
        format="json",
    )
    assert resp_login.status_code == status.HTTP_200_OK
    access_token = resp_login.data["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

    # 3) Envia um FormResponse do tipo "plan"
    form_response_url = reverse("form-response-list")
    payload = {
        "business": business.id,
        "form_type": "plan",
        "form_version": "1.0",
        "data": {"question1": "answer1", "question2": "answer2"},
    }
    resp_form_response = api_client.post(form_response_url, payload, format="json")
    assert resp_form_response.status_code == status.HTTP_201_CREATED

    # 4) Verifica se o Business avançou para "plan"
    business.refresh_from_db() # Recarrega o objeto Business do banco
    assert business.stage == "plan"

    # 5) Verifica o BusinessStageHistory
    history = BusinessStageHistory.objects.filter(business=business).order_by('-changed_at').first()
    assert history is not None
    assert history.from_stage == "ideation"
    assert history.to_stage == "plan"
    assert history.changed_by == user

    # 6) Verifica o StageStatus
    stage_status = StageStatus.objects.get(business=business)
    assert stage_status.current_stage == "plan"
    assert stage_status.plan_started_at is not None
    assert stage_status.ideation_completed_at is not None
    assert stage_status.ideation_progress == 100
    assert stage_status.plan_progress == 0 # Ou o valor inicial que você definiu na util

@pytest.mark.django_db
def test_advance_stage_from_plan_to_mvp_on_form_response(api_client):
    # 1) Setup: Cria um usuário e um Business no estágio "plan"
    user = User.objects.create_user(username="testuser_mvp", email="mvp@example.com", password="SenhaForte123")
    business = Business.objects.create(owner=user, name="Negocio Teste MVP", segment="Tecnologia", stage="plan")

    # Garante que o StageStatus inicial existe e está em plan
    StageStatus.objects.create(
        business=business,
        current_stage="plan",
        ideation_started_at="2026-01-01T00:00:00Z",
        ideation_completed_at="2026-01-05T00:00:00Z",
        ideation_progress=100,
        plan_started_at="2026-01-06T00:00:00Z",
        plan_progress=50 # Exemplo de progresso
    )

    # 2) Login do usuário
    login_url = reverse("token_obtain_pair")
    resp_login = api_client.post(
        login_url,
        {"username": "testuser_mvp", "password": "SenhaForte123"},
        format="json",
    )
    assert resp_login.status_code == status.HTTP_200_OK
    access_token = resp_login.data["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

    # 3) Envia um FormResponse do tipo "mvp"
    form_response_url = reverse("form-response-list")
    payload = {
        "business": business.id,
        "form_type": "mvp",
        "form_version": "1.0",
        "data": {"mvp_question1": "answer1", "mvp_question2": "answer2"},
    }
    resp_form_response = api_client.post(form_response_url, payload, format="json")
    assert resp_form_response.status_code == status.HTTP_201_CREATED

    # 4) Verifica se o Business avançou para "mvp"
    business.refresh_from_db()
    assert business.stage == "mvp"

    # 5) Verifica o BusinessStageHistory
    history = BusinessStageHistory.objects.filter(business=business).order_by('-changed_at').first()
    assert history is not None
    assert history.from_stage == "plan"
    assert history.to_stage == "mvp"
    assert history.changed_by == user

    # 6) Verifica o StageStatus
    stage_status = StageStatus.objects.get(business=business)
    assert stage_status.current_stage == "mvp"
    assert stage_status.mvp_started_at is not None
    assert stage_status.plan_completed_at is not None
    assert stage_status.plan_progress == 100
    assert stage_status.mvp_progress == 0 # Ou o valor inicial que você definiu na util

@pytest.mark.django_db
def test_no_stage_advance_on_ideation_form_response(api_client):
    # 1) Setup: Cria um usuário e um Business no estágio inicial (ideation)
    user = User.objects.create_user(username="testuser_no_advance", email="noadvance@example.com", password="SenhaForte123")
    business = Business.objects.create(owner=user, name="Negocio Sem Avanco", segment="Comercio", stage="ideation")

    # Garante que o StageStatus inicial existe e está em ideation
    StageStatus.objects.create(business=business, current_stage="ideation")

    # 2) Login do usuário
    login_url = reverse("token_obtain_pair")
    resp_login = api_client.post(
        login_url,
        {"username": "testuser_no_advance", "password": "SenhaForte123"},
        format="json",
    )
    assert resp_login.status_code == status.HTTP_200_OK
    access_token = resp_login.data["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

    # 3) Envia um FormResponse do tipo "ideation"
    form_response_url = reverse("form-response-list")
    payload = {
        "business": business.id,
        "form_type": "ideation",
        "form_version": "1.0",
        "data": {"ideation_q1": "a1"},
    }
    resp_form_response = api_client.post(form_response_url, payload, format="json")
    assert resp_form_response.status_code == status.HTTP_201_CREATED

    # 4) Verifica que o Business NÃO avançou de estágio
    business.refresh_from_db()
    assert business.stage == "ideation" # Deve permanecer em ideation

    # 5) Verifica que nenhum BusinessStageHistory foi criado para avanço
    history_count = BusinessStageHistory.objects.filter(business=business, to_stage="plan").count()
    assert history_count == 0

    # 6) Verifica que o StageStatus não mudou para "plan"
    stage_status = StageStatus.objects.get(business=business)
    assert stage_status.current_stage == "ideation"
    assert stage_status.plan_started_at is None # Não deve ter iniciado o plano
