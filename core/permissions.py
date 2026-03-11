from rest_framework.permissions import BasePermission
from django.conf import settings

class HasN8NAPIKey(BasePermission):
    """
    Permite acesso apenas se a requisição contiver o cabeçalho 'X-API-Key' 
    com o valor exato configurado no settings.
    """
    def has_permission(self, request, view):
        # O Django converte cabeçalhos HTTP customizados. 
        # 'X-API-Key' no request vira 'HTTP_X_API_KEY' no META, 
        # mas o objeto request.headers facilita a busca.
        api_key = request.headers.get('X-API-Key')

        # Verifica se a chave enviada bate com a chave do sistema
        return api_key == getattr(settings, 'N8N_API_KEY', None)
