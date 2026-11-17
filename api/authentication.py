"""Аутентификация API v1 по ключу.

Ключ передаётся в заголовке X-API-Key либо в заголовке Authorization
со схемой ApiKey:

    X-API-Key: kcn_1a2b3c4d_xxx
    Authorization: ApiKey kcn_1a2b3c4d_xxx

У ключа нет связанного пользователя Django, поэтому authenticate() возвращает
(None, api_key): объект ключа доступен в представлении как request.auth.
"""

from rest_framework import authentication, exceptions

from .models import ApiKey

API_KEY_HEADER = "HTTP_X_API_KEY"
AUTHORIZATION_HEADER = "HTTP_AUTHORIZATION"
AUTHORIZATION_SCHEME = "ApiKey"


class ApiKeyAuthentication(authentication.BaseAuthentication):
    """Проверка API-ключа из заголовка запроса."""

    def authenticate(self, request):
        raw_key = self.get_raw_key(request)
        if not raw_key:
            # Заголовка нет — возможно, запрос аутентифицирует другой класс
            # (например, SessionAuthentication для сессии админки).
            return None

        api_key = ApiKey.objects.verify(raw_key)
        if api_key is None:
            raise exceptions.AuthenticationFailed(
                "Недействительный, отключённый или просроченный API-ключ.",
                code="invalid_api_key",
            )
        return (None, api_key)

    def authenticate_header(self, request) -> str:
        """Заголовок WWW-Authenticate для ответа 401."""
        return f'{AUTHORIZATION_SCHEME} realm="api"'

    @staticmethod
    def get_raw_key(request) -> str:
        """Достать значение ключа из X-API-Key или из Authorization: ApiKey <ключ>."""
        raw_key = request.META.get(API_KEY_HEADER, "").strip()
        if raw_key:
            return raw_key

        authorization = request.META.get(AUTHORIZATION_HEADER, "").strip()
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == AUTHORIZATION_SCHEME.lower():
            return value.strip()
        return ""
