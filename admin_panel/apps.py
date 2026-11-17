from django.apps import AppConfig


class AdminPanelConfig(AppConfig):
    # BigAutoField задан явно, чтобы не зависеть от DEFAULT_AUTO_FIELD проекта.
    default_auto_field = "django.db.models.BigAutoField"
    name = "admin_panel"
    verbose_name = "Табличная панель"
