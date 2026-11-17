"""Модели приложения api.

ApiKey — ключ доступа к записывающим операциям API v1. В базе хранится только
SHA-256 хэш ключа, поэтому посмотреть выпущенный ключ повторно нельзя: его
показывают один раз при создании (в админке или в команде create_api_key).
"""

from __future__ import annotations

import hashlib
import secrets

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

# Открытая часть ключа: по ней запись ищется в базе до сверки хэша.
KEY_PREFIX = "kcn"
PREFIX_BYTES = 4  # 4 байта -> 8 шестнадцатеричных символов префикса
SECRET_BYTES = 32  # длина секретной части ключа


def generate_key() -> tuple[str, str]:
    """Сгенерировать новый ключ.

    Возвращает пару (полное значение ключа, префикс). Полное значение состоит
    из префикса и секретной части: "kcn_1a2b3c4d_<секрет>".
    """
    prefix = secrets.token_hex(PREFIX_BYTES)
    secret = secrets.token_urlsafe(SECRET_BYTES)
    return f"{KEY_PREFIX}_{prefix}_{secret}", prefix


def parse_prefix(raw_key: str) -> str | None:
    """Достать префикс из значения ключа или вернуть None, если формат неверный.

    Секретная часть получена token_urlsafe() и может содержать символ «_»,
    поэтому ключ разбирается по первым двум разделителям, а не по всем.
    """
    key_prefix, _, rest = str(raw_key).partition("_")
    if key_prefix != KEY_PREFIX or not rest:
        return None
    prefix, _, secret = rest.partition("_")
    if not prefix or not secret:
        return None
    return prefix


def hash_key(raw_key: str) -> str:
    """Хэш, который реально сохраняется в поле hashed_key."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


class ApiKeyManager(models.Manager):
    """Выпуск и проверка API-ключей."""

    def create_key(
        self,
        *,
        name: str,
        scopes: str | None = None,
        is_active: bool = True,
        expires_at=None,
    ) -> tuple[ApiKey, str]:
        """Создать ключ и вернуть пару (объект ApiKey, ключ в открытом виде)."""
        raw_key, prefix = generate_key()
        api_key = self.create(
            name=name,
            prefix=prefix,
            hashed_key=hash_key(raw_key),
            scopes=scopes if scopes is not None else self.model.Scope.WRITE,
            is_active=is_active,
            expires_at=expires_at,
        )
        return api_key, raw_key

    def verify(self, raw_key: str) -> ApiKey | None:
        """Найти действующий ключ по его открытому значению или вернуть None.

        Ключ считается недействительным, если он не найден, отключён,
        просрочен или если хэш не совпал.
        """
        prefix = parse_prefix(raw_key)
        if prefix is None:
            return None
        try:
            api_key = self.get(prefix=prefix)
        except self.model.DoesNotExist:
            return None
        if not api_key.is_usable(raw_key):
            return None
        api_key.touch()
        return api_key


class ApiKey(models.Model):
    """Ключ доступа к API со своим набором разрешений (скоупов)."""

    class Scope(models.TextChoices):
        WRITE = "write", "write — создание и изменение"
        DELETE = "delete", "delete — удаление"
        MANAGE = "manage", "manage — полный доступ (write + delete)"

    name = models.CharField(
        verbose_name="название",
        max_length=100,
        help_text="Для чего выпущен ключ, например «Учебный скрипт».",
    )
    prefix = models.CharField(
        verbose_name="префикс",
        max_length=16,
        unique=True,
        editable=False,
        help_text="Открытая часть ключа, по которой он ищется в базе.",
    )
    hashed_key = models.CharField(
        verbose_name="хэш ключа",
        max_length=64,
        editable=False,
        help_text="SHA-256 от полного значения ключа. Сам ключ в базе не хранится.",
    )
    scopes = models.CharField(
        verbose_name="скоупы",
        max_length=64,
        default=Scope.WRITE,
        help_text="Через запятую: write, delete, manage.",
    )
    is_active = models.BooleanField(verbose_name="активен", default=True)
    expires_at = models.DateTimeField(
        verbose_name="действителен до",
        null=True,
        blank=True,
        help_text="Пустое значение — ключ бессрочный.",
    )
    created_at = models.DateTimeField(
        verbose_name="создан",
        default=timezone.now,
        editable=False,
    )
    last_used_at = models.DateTimeField(
        verbose_name="последнее использование",
        null=True,
        blank=True,
        editable=False,
    )

    objects = ApiKeyManager()

    class Meta:
        verbose_name = "API-ключ"
        verbose_name_plural = "API-ключи"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.name} ({self.prefix}…)"

    def clean(self) -> None:
        """Проверить скоупы при сохранении через админку или форму."""
        super().clean()
        scopes = self.scope_list()
        if not scopes:
            raise ValidationError(
                {"scopes": "Укажите хотя бы один скоуп: write, delete или manage."}
            )
        allowed = set(self.Scope.values)
        unknown = [scope for scope in scopes if scope not in allowed]
        if unknown:
            raise ValidationError(
                {
                    "scopes": (
                        f"Неизвестные скоупы: {', '.join(unknown)}. "
                        f"Допустимые значения: {', '.join(sorted(allowed))}."
                    )
                }
            )

    def save(self, *args, **kwargs) -> None:
        self.scopes = self.normalize_scopes(self.scopes)
        super().save(*args, **kwargs)

    @staticmethod
    def normalize_scopes(value: str | None) -> str:
        """Привести список скоупов к каноничному виду: «Write, write » -> «write»."""
        unique: dict[str, None] = {}
        for scope in str(value or "").split(","):
            scope = scope.strip().lower()
            if scope:
                unique.setdefault(scope, None)
        return ", ".join(unique)

    def scope_list(self) -> list[str]:
        """Скоупы ключа списком."""
        return [
            scope.strip().lower() for scope in self.scopes.split(",") if scope.strip()
        ]

    def has_scope(self, scope: str) -> bool:
        """Проверить разрешение. Скоуп manage покрывает write и delete."""
        scopes = self.scope_list()
        return self.Scope.MANAGE in scopes or scope in scopes

    @property
    def is_expired(self) -> bool:
        return self.expires_at is not None and self.expires_at <= timezone.now()

    def is_usable(self, raw_key: str) -> bool:
        """Ключ активен, не просрочен и совпал по хэшу."""
        return (
            self.is_active
            and not self.is_expired
            and secrets.compare_digest(self.hashed_key, hash_key(raw_key))
        )

    def touch(self) -> None:
        """Отметить время последнего использования одним UPDATE-запросом."""
        now = timezone.now()
        ApiKey.objects.filter(pk=self.pk).update(last_used_at=now)
        self.last_used_at = now
