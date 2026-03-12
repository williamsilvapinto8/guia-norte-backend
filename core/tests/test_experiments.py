from django.test import TestCase
# Create your tests here.

# Adicione os imports necessários para o teste de API
from rest_framework.test import APIClient
from rest_framework import status
from django.urls import reverse
from django.contrib.auth import get_user_model
from core.models import Business, Experiment # Assumindo que models.py está em core
from core.serializers import ExperimentSerializer # Assumindo que serializers.py está em core
import pytest

User = get_user_model()

@pytest.mark.django_db
def test_create_experiment_limit_one_per_business(api_client):
    # 1) Cria um usuário e um Business
    user = User.objects.create_user(username="testuser", email="user@example.com", password="SenhaForte123")
    business = Business.objects.create(owner=user, name="Meu Negocio Teste", segment="Serviços")

    # 2) Loga o usuário para obter o token JWT
    login_url = reverse("token_obtain_pair") # Verifique se esta é a URL correta do seu SimpleJWT
    resp_login = api_client.post(
        login_url,
        {"username": "user@example.com", "password": "SenhaForte123"},
        format="json",
    )
    assert resp_login.status_code == 200
    access_token = resp_login.data["access"]

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

    # 3) Cria o primeiro Experiment (deve funcionar)
    experiments_url = reverse("experiment-list") # Verifique se esta é a URL correta do seu ExperimentViewSet
    payload_1 = {
        "business": business.id,
        "name": "Experimento 1",
        "hypothesis": "Testar interesse no serviço X",
        "experiment_type": "entrevista",
        "target_audience": "Clientes da região",
        "channels": "WhatsApp",
        "success_metrics": "Número de interessados",
        "expected_duration_days": 7,
    }

    resp_1 = api_client.post(experiments_url, payload_1, format="json")
    assert resp_1.status_code == status.HTTP_201_CREATED
    assert Experiment.objects.filter(business=business).count() == 1

    # 4) Tenta criar o segundo Experiment (deve falhar)
    payload_2 = {
        "business": business.id,
        "name": "Experimento 2",
        "hypothesis": "Testar preço do serviço X",
        "experiment_type": "oferta_simples",
        "target_audience": "Clientes da região",
        "channels": "Instagram",
        "success_metrics": "Vendas realizadas",
        "expected_duration_days": 5,
    }

    resp_2 = api_client.post(experiments_url, payload_2, format="json")

    assert resp_2.status_code == status.HTTP_400_BAD_REQUEST
    # Verifica se veio a mensagem da nossa validação
    assert "Na versão gratuita, você só pode cadastrar 1 experimento por negócio." in str(
        resp_2.data
    )
