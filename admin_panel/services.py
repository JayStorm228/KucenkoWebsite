"""Данные табличной панели и пакетное сохранение изменений.

Панель работает с базой напрямую: отдаёт все колонки моделей (включая
reviews_qty и created_at, которые скрыты в публичном API v1) и не применяет
капитализацию заголовков — администратор видит и правит данные как есть.

Контракт сохранения (POST на admin_panel:save):

    {
      "categories": {"created": [{"temp_id": -1, "title": "..."}],
                     "updated": [{"id": 3, "title": "..."}],
                     "deleted": [5]},
      "courses":    {"created": [{"temp_id": -2, "title": "...", "price": 100,
                                  "student_qty": 1, "reviews_qty": 0,
                                  "category": -1}],
                     "updated": [{"id": 7, ...}],
                     "deleted": [9]}
    }

Строки created и updated передаются целиком (все редактируемые поля), потому
что на сервере они проходят через ModelForm. Если в пакете есть новая категория,
курсы могут ссылаться на неё по временному отрицательному id — сервер подменит
его на настоящий. Изменения применяются пакетом: при любой ошибке валидации
не сохраняется ничего.
"""

from dataclasses import dataclass, field

from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from shop.models import Category, Course

from .forms import CategoryForm, CourseForm

#: Разделы панели: модель, форма строки и редактируемые поля.
SECTIONS = {
    "categories": {
        "model": Category,
        "form": CategoryForm,
        "fields": ("title",),
    },
    "courses": {
        "model": Course,
        "form": CourseForm,
        "fields": ("title", "price", "student_qty", "reviews_qty", "category"),
    },
}

#: Порядок применения: сначала категории, затем ссылающиеся на них курсы.
SECTION_ORDER = ("categories", "courses")


@dataclass
class Changeset:
    """Изменения одной таблицы."""

    created: list = field(default_factory=list)  # [(row_id, data)]
    updated: list = field(default_factory=list)  # [(row_id, data)]
    deleted: list = field(default_factory=list)  # [pk]


@dataclass
class SaveResult:
    """Итог сохранения: ошибки по строкам и счётчики применённых изменений."""

    errors: dict = field(default_factory=dict)
    created: int = 0
    updated: int = 0
    deleted: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors

    def add_errors(self, section: str, row_id, form_errors) -> None:
        """Записать ошибки формы под идентификатором строки."""
        rows = self.errors.setdefault(section, {})
        rows[str(row_id)] = {
            name: list(messages) for name, messages in form_errors.items()
        }

    def as_dict(self) -> dict:
        return {
            "created": self.created,
            "updated": self.updated,
            "deleted": self.deleted,
        }


def as_list(value) -> list:
    """Список из JSON-значения (пустой, если тип не тот)."""
    return value if isinstance(value, list) else []


def as_int(value):
    """Целое из JSON-значения; None, если это не целое."""
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    if isinstance(value, int):
        return value
    value = value.strip()
    return int(value) if value.lstrip("-").isdigit() else None


def row_key(row: dict, is_new: bool):
    """Идентификатор строки: temp_id для новых, id для существующих."""
    if is_new:
        key = as_int(row.get("temp_id"))
        return key if key is not None else as_int(row.get("id"))
    return as_int(row.get("id"))


def parse_changeset(raw, fields: tuple[str, ...]) -> Changeset:
    """Разобрать часть полезной нагрузки, отбрасывая лишнее и некорректное."""
    raw = raw if isinstance(raw, dict) else {}
    changeset = Changeset()

    for name, bucket, is_new in (
        ("created", changeset.created, True),
        ("updated", changeset.updated, False),
    ):
        for row in as_list(raw.get(name)):
            if not isinstance(row, dict):
                continue
            key = row_key(row, is_new)
            data = {
                field_name: row[field_name]
                for field_name in fields
                if field_name in row
            }
            if key is None or not data:
                continue
            bucket.append((key, data))

    changeset.deleted = [
        pk
        for pk in (as_int(value) for value in as_list(raw.get("deleted")))
        if pk is not None
    ]
    return changeset


def format_datetime(value) -> str | None:
    """ISO-строка в местном времени: сортируется лексикографически, читается в JS."""
    if value is None:
        return None
    return timezone.localtime(value).isoformat(timespec="minutes")


def build_panel_data() -> dict:
    """Все данные для обеих таблиц одним ответом."""
    categories = Category.objects.annotate(courses_count=Count("course")).order_by("id")
    courses = Course.objects.select_related("category").order_by("id")
    return {
        "categories": [
            {
                "id": category.id,
                "title": category.title,
                "courses_count": category.courses_count,
                "created_at": format_datetime(category.created_at),
            }
            for category in categories
        ],
        "courses": [
            {
                "id": course.id,
                "title": course.title,
                "price": course.price,
                "student_qty": course.student_qty,
                "reviews_qty": course.reviews_qty,
                "category": course.category_id,
                "created_at": format_datetime(course.created_at),
            }
            for course in courses
        ],
    }


def map_temp_category(data: dict, temp_to_real: dict[int, int]) -> dict:
    """Подставить настоящий id категории вместо временного (из того же пакета)."""
    category = as_int(data.get("category"))
    if category is not None and category in temp_to_real:
        return {**data, "category": temp_to_real[category]}
    return data


def save_rows(
    section: str, changeset: Changeset, temp_to_real: dict, result: SaveResult
) -> None:
    """Создать и обновить строки одного раздела, собирая ошибки валидации."""
    config = SECTIONS[section]
    for row_id, data in changeset.created:
        if section == "courses":
            data = map_temp_category(data, temp_to_real)
        form = config["form"](data=data)
        if form.is_valid():
            obj = form.save()
            result.created += 1
            if section == "categories":
                temp_to_real[row_id] = obj.pk
        else:
            result.add_errors(section, row_id, form.errors)

    for row_id, data in changeset.updated:
        obj = config["model"].objects.filter(pk=row_id).first()
        if obj is None:
            # Запись удалена раньше — изменение неактуально, ошибкой не считаем.
            continue
        if section == "courses":
            data = map_temp_category(data, temp_to_real)
        form = config["form"](data=data, instance=obj)
        if form.is_valid():
            form.save()
            result.updated += 1
        else:
            result.add_errors(section, row_id, form.errors)


def delete_rows(section: str, ids: list) -> int:
    """Удалить записи раздела и вернуть число удалённых строк.

    Удаление категории каскадно удаляет её курсы (on_delete=CASCADE у
    Course.category) — это штатное поведение модели, интерфейс предупреждает
    о нём до сохранения.
    """
    if not ids:
        return 0
    objects = SECTIONS[section]["model"].objects.filter(pk__in=ids)
    count = objects.count()
    objects.delete()
    return count


def apply_panel_changes(payload: dict) -> SaveResult:
    """Проверить и применить изменения обеих таблиц одной транзакцией."""
    result = SaveResult()
    changesets = {
        section: parse_changeset(payload.get(section), SECTIONS[section]["fields"])
        for section in SECTION_ORDER
    }
    temp_to_real: dict[int, int] = {}

    with transaction.atomic():
        # 1. Создание и обновление: сначала категории, потом курсы.
        for section in SECTION_ORDER:
            save_rows(section, changesets[section], temp_to_real, result)

        # 2. Удаления — только если всё остальное прошло валидацию:
        #    сначала курсы, затем категории (из-за каскада).
        if result.ok:
            for section in reversed(SECTION_ORDER):
                result.deleted += delete_rows(section, changesets[section].deleted)

        if not result.ok:
            transaction.set_rollback(True)

    return result
