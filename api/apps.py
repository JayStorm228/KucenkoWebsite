from django.apps import AppConfig


class ApiConfig(AppConfig):
    # BigAutoField задан явно, чтобы миграции приложения не зависели от
    # значения DEFAULT_AUTO_FIELD в настройках проекта.
    default_auto_field = "django.db.models.BigAutoField"
    name = "api"
    verbose_name = "API"
