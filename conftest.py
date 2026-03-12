import pytest
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

@pytest.fixture
def api_client():
    """
    Fixture para um cliente de API não autenticado.
    """
    return APIClient()

@pytest.fixture
def authenticated_api_client(api_client, user_data=None):
    """
    Fixture para um cliente de API autenticado.
    Cria um usuário e retorna um APIClient com token JWT.
    """
    User = get_user_model()
    if user_data is None:
        user_data = {
            "username": "testuser_auth",
            "email": "auth@example.com",
            "password": "SenhaForte123",
        }

    user = User.objects.create_user(**user_data)

    # Autentica o usuário e obtém o token
    login_url = pytest.reverse("token_obtain_pair") # Usando pytest.reverse
    resp_login = api_client.post(
        login_url,
        {"username": user_data["email"], "password": user_data["password"]},
        format="json",
    )
    assert resp_login.status_code == 200
    access_token = resp_login.data["access"]

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    return api_client

# Adicione esta linha para que o reverse funcione no conftest
# Isso é um hack, o ideal é passar o reverse como argumento ou usar o manage.py test
# Mas para o pytest puro, pode ser necessário.
# Ou você pode importar reverse diretamente no conftest se o Django estiver configurado.
try:
    from django.urls import reverse as django_reverse
    pytest.reverse = django_reverse
except ImportError:
    # Fallback se o Django não estiver configurado ainda
    pytest.reverse = lambda x: f"/{x}/" # Apenas para evitar erro, não funcional
