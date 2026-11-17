"""Авторизация API v1.

Правила доступа:

* чтение (GET, HEAD, OPTIONS) — публичное, ключ не нужен;
* создание и изменение (POST, PUT, PATCH) — нужен ключ со скоупом write;
* удаление (DELETE) — нужен ключ со скоупом delete;
* скоуп manage покрывает write и delete;
* залогиненный сотрудник (is_staff) может выполнять запись через сессию
  админки — это удобно для проверки в Browsable API.

Если ключ не передан вовсе, DRF вернёт 401 (NotAuthenticated), а если ключ
действительный, но скоупа не хватает — 403 с поясняющим сообщением.
"""

from rest_framework import permissions

from .models import ApiKey

SCOPE_BY_METHOD = {
    "POST": ApiKey.Scope.WRITE,
    "PUT": ApiKey.Scope.WRITE,
    "PATCH": ApiKey.Scope.WRITE,
    "DELETE": ApiKey.Scope.DELETE,
}

MESSAGE_BY_SCOPE = {
    ApiKey.Scope.WRITE: (
        "Для создания и изменения данных нужен API-ключ со скоупом write или manage."
    ),
    ApiKey.Scope.DELETE: (
        "Для удаления данных нужен API-ключ со скоупом delete или manage."
    ),
}


class ApiKeyScopePermission(permissions.BasePermission):
    """Проверка скоупа API-ключа под запрошенный HTTP-метод."""

    def has_permission(self, request, view) -> bool:
        if request.method in permissions.SAFE_METHODS:
            return True

        api_key = request.auth if isinstance(request.auth, ApiKey) else None
        if api_key is not None:
            scope = SCOPE_BY_METHOD.get(request.method)
            if scope is None:
                return True
            if api_key.has_scope(scope):
                return True
            self.message = MESSAGE_BY_SCOPE[scope]
            return False

        user = request.user
        if user is not None and user.is_authenticated and user.is_staff:
            return True

        self.message = (
            "Для записи передайте API-ключ в заголовке X-API-Key "
            "или Authorization: ApiKey <ключ>."
        )
        return False
