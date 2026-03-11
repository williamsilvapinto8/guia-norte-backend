from rest_framework.permissions import BasePermission
from django.conf import settings


class HasN8NAPIKey(BasePermission):
    """
    Permite acesso apenas se a requisição contiver o cabeçalho
    'X-API-Key' com o valor configurado em settings.N8N_API_KEY.
    """
    def has_permission(self, request, view):
        api_key = request.headers.get('X-API-Key')

        # Rejeita se a chave estiver em branco ou não configurada
        if not api_key:
            return False

        return api_key == getattr(settings, 'N8N_API_KEY', None)
