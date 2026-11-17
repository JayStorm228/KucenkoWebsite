"""Админка приложения api: выпуск и отзыв API-ключей + оформление панели.

Здесь же задаются заголовки админ-сайта, чтобы панель выглядела как часть
веб-приложения «Магазин Куценко В.», а не как стандартная админка Django.
Сама разметка и стили — в templates/admin/base_site.html и static/css/admin_site.css.
"""

from django.contrib import admin, messages

from .models import ApiKey, generate_key, hash_key

admin.site.site_header = "Магазин Куценко В. — администрирование"
admin.site.site_title = "Администрирование магазина"
admin.site.index_title = "Управление магазином"


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    """Управление API-ключами.

    Значение ключа показывается один раз — сообщением сразу после создания.
    В базе хранится только SHA-256 хэш, поэтому восстановить значение нельзя:
    потерянный ключ заменяют новым. Отзыв доступа — снятие флажка «активен».
    """

    #: Атрибут request, в котором значение ключа доживает от save_model()
    #: до response_add(). Хранить его в self нельзя: экземпляр ModelAdmin
    #: общий для всех запросов.
    raw_key_request_attr = "_api_raw_key"

    list_display = (
        "name",
        "prefix",
        "scopes",
        "is_active",
        "expires_at",
        "last_used_at",
        "created_at",
    )
    list_filter = ("is_active",)
    search_fields = ("name", "prefix")
    # Хэш ключа в форме не показывается: он не нужен администратору и не должен
    # мелькать в интерфейсе. Отзыв доступа — снятие флажка «активен».
    readonly_fields = ("prefix", "created_at", "last_used_at")
    fields = (
        "name",
        "scopes",
        "is_active",
        "expires_at",
        "prefix",
        "created_at",
        "last_used_at",
    )

    def save_model(self, request, obj, form, change) -> None:
        """Выпустить ключ при создании записи и запомнить его значение в request."""
        if not change and not obj.hashed_key:
            raw_key, prefix = generate_key()
            obj.prefix = prefix
            obj.hashed_key = hash_key(raw_key)
            setattr(request, self.raw_key_request_attr, raw_key)
        super().save_model(request, obj, form, change)

    def response_add(self, request, obj, post_url_continue=None):
        """Показать выпущенный ключ единственному, кто может его увидеть."""
        raw_key = getattr(request, self.raw_key_request_attr, None)
        if raw_key:
            messages.success(
                request,
                f"API-ключ «{obj.name}» создан: {raw_key} "
                "— сохраните его, повторно посмотреть значение нельзя.",
            )
        return super().response_add(request, obj, post_url_continue)
