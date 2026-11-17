"""Команда выпуска API-ключа из командной строки.

Примеры:

    python manage.py create_api_key --name "Учебный скрипт" --scopes write,delete
    python manage.py create_api_key --name "Интеграция" --scopes manage

Ключ с ограниченным сроком действия: добавьте --expires-in-days 30.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from api.models import ApiKey


class Command(BaseCommand):
    help = "Создать API-ключ для записывающих операций API v1 и показать его значение."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--name",
            required=True,
            help="Назначение ключа, например «Учебный скрипт».",
        )
        parser.add_argument(
            "--scopes",
            default=ApiKey.Scope.WRITE,
            help="Скоупы через запятую: write, delete, manage. По умолчанию write.",
        )
        parser.add_argument(
            "--expires-in-days",
            type=int,
            default=None,
            help="Срок действия ключа в днях. По умолчанию ключ бессрочный.",
        )
        parser.add_argument(
            "--inactive",
            action="store_true",
            help="Создать ключ неактивным (например, чтобы включить позже).",
        )

    def handle(self, *args, **options) -> None:
        scopes = self.normalize_scopes(options["scopes"])
        expires_at = self.expires_at(options["expires_in_days"])

        api_key, raw_key = ApiKey.objects.create_key(
            name=options["name"],
            scopes=scopes,
            is_active=not options["inactive"],
            expires_at=expires_at,
        )

        self.stdout.write(
            self.style.SUCCESS(f"API-ключ «{api_key.name}» создан (id={api_key.pk}).")
        )
        self.stdout.write(f"Скоупы: {api_key.scopes}")
        if api_key.expires_at:
            expires = timezone.localtime(api_key.expires_at).strftime("%Y-%m-%d %H:%M")
            self.stdout.write(f"Действителен до: {expires}")
        self.stdout.write(
            "Значение ключа (показывается один раз, в базе хранится хэш):"
        )
        self.stdout.write(self.style.WARNING(raw_key))
        self.stdout.write("Пример запроса:")
        self.stdout.write(
            f'  curl -H "X-API-Key: {raw_key}" http://127.0.0.1:8000/api/v1/courses/'
        )

    @staticmethod
    def normalize_scopes(value: str) -> str:
        scopes = ApiKey.normalize_scopes(value)
        allowed = set(ApiKey.Scope.values)
        unknown = [scope for scope in scopes.split(", ") if scope not in allowed]
        if unknown:
            raise CommandError(
                f"Неизвестные скоупы: {', '.join(unknown)}. "
                f"Допустимые значения: {', '.join(sorted(allowed))}."
            )
        if not scopes:
            raise CommandError("Укажите хотя бы один скоуп: write, delete или manage.")
        return scopes

    @staticmethod
    def expires_at(days: int | None):
        if days is None:
            return None
        if days <= 0:
            raise CommandError("--expires-in-days должно быть положительным числом.")
        return timezone.now() + timedelta(days=days)
