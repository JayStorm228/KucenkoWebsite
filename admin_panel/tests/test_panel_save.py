"""Пакетное сохранение изменений таблиц: admin_panel:save."""

import json
import re

import pytest
from django.utils import timezone

from shop.models import Category, Course

from .conftest import PANEL_URL, SAVE_URL


def save(client, payload) -> dict:
    """POST пакета изменений; возвращает разобранный ответ."""
    response = client.post(
        SAVE_URL,
        data=json.dumps(payload, ensure_ascii=False),
        content_type="application/json",
    )
    return response


def created(temp_id: int, **fields) -> dict:
    return {"temp_id": temp_id, **fields}


def updated(pk: int, **fields) -> dict:
    return {"id": pk, **fields}


def course_fields(category, **overrides) -> dict:
    fields = {
        "title": "Новый курс",
        "price": 990.0,
        "student_qty": 3,
        "reviews_qty": 0,
        "category": category.pk,
    }
    fields.update(overrides)
    return fields


@pytest.fixture
def csrf_token(csrf_client) -> str:
    """Токен из страницы панели: тот же клиент хранит и CSRF-cookie."""
    content = csrf_client.get(PANEL_URL).content.decode()
    match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', content)
    assert match is not None, "на странице нет CSRF-токена"
    return match.group(1)


class TestAccess:
    def test_anonymous_forbidden_and_nothing_saved(self, anonymous_client):
        response = save(
            anonymous_client, {"categories": {"created": [created(-1, title="X")]}}
        )
        assert response.status_code == 403
        assert response.json()["ok"] is False
        assert Category.objects.count() == 0

    def test_regular_user_forbidden(self, user_client):
        response = save(
            user_client, {"categories": {"created": [created(-1, title="X")]}}
        )
        assert response.status_code == 403

    def test_api_key_does_not_grant_access(self, anonymous_client, key_header):
        response = anonymous_client.post(
            SAVE_URL,
            data=json.dumps({"categories": {"created": [created(-1, title="X")]}}),
            content_type="application/json",
            headers=key_header,
        )
        assert response.status_code == 403
        assert Category.objects.count() == 0

    def test_csrf_token_required(self, csrf_client):
        response = save(csrf_client, {"categories": {}})
        assert response.status_code == 403

    def test_csrf_token_from_page_is_accepted(self, csrf_client, csrf_token):
        response = csrf_client.post(
            SAVE_URL,
            data=json.dumps(
                {"categories": {"created": [created(-1, title="Из браузера")]}}
            ),
            content_type="application/json",
            headers={"X-CSRFToken": csrf_token},
        )
        assert response.status_code == 200
        assert Category.objects.filter(title="Из браузера").exists()

    def test_get_is_not_allowed(self, staff_client):
        assert staff_client.get(SAVE_URL).status_code == 405

    def test_broken_json(self, staff_client):
        response = staff_client.post(
            SAVE_URL, data="{не json", content_type="application/json"
        )
        assert response.status_code == 400
        assert response.json()["ok"] is False

    def test_json_array_is_rejected(self, staff_client):
        response = staff_client.post(
            SAVE_URL, data="[]", content_type="application/json"
        )
        assert response.status_code == 400

    def test_empty_payload_is_accepted(self, staff_client):
        response = save(staff_client, {})
        assert response.status_code == 200
        assert response.json()["summary"] == {"created": 0, "updated": 0, "deleted": 0}


class TestCreate:
    def test_create_category(self, staff_client):
        response = save(
            staff_client, {"categories": {"created": [created(-1, title="Аналитика")]}}
        )
        body = response.json()
        assert response.status_code == 200
        assert body["ok"] is True
        assert body["summary"]["created"] == 1
        assert Category.objects.filter(title="Аналитика").exists()

    def test_title_is_saved_as_typed(self, staff_client):
        """Панель не капитализирует заголовки — это делает только API v1."""
        save(
            staff_client,
            {"categories": {"created": [created(-1, title="аналитика ДАННЫХ")]}},
        )
        assert Category.objects.get().title == "аналитика ДАННЫХ"

    def test_create_course(self, staff_client, category):
        response = save(
            staff_client,
            {"courses": {"created": [created(-1, **course_fields(category))]}},
        )
        assert response.status_code == 200
        course = Course.objects.get()
        assert course.title == "Новый курс"
        assert course.price == 990.0
        assert course.student_qty == 3
        assert course.category == category

    def test_reviews_qty_is_saved(self, staff_client, category):
        """В отличие от API v1, reviews_qty здесь приходит от клиента."""
        save(
            staff_client,
            {
                "courses": {
                    "created": [created(-1, **course_fields(category, reviews_qty=5))]
                }
            },
        )
        assert Course.objects.get().reviews_qty == 5

    def test_created_at_is_set_by_database(self, staff_client, category):
        before = timezone.now()
        save(
            staff_client,
            {
                "courses": {
                    "created": [
                        created(
                            -1, created_at="2001-01-01T00:00", **course_fields(category)
                        )
                    ]
                }
            },
        )
        course = Course.objects.get()
        assert course.created_at >= before
        assert course.created_at.year != 2001

    def test_create_course_with_temp_category(self, staff_client):
        """Курс может ссылаться на категорию, созданную в том же пакете."""
        response = save(
            staff_client,
            {
                "categories": {"created": [created(-1, title="Новая категория")]},
                "courses": {
                    "created": [
                        created(
                            -2,
                            title="Курс",
                            price=10,
                            student_qty=0,
                            reviews_qty=0,
                            category=-1,
                        )
                    ]
                },
            },
        )
        assert response.status_code == 200, response.json()
        category = Category.objects.get(title="Новая категория")
        assert Course.objects.get(title="Курс").category == category

    def test_unknown_temp_category_is_rejected(self, staff_client):
        response = save(
            staff_client,
            {
                "courses": {
                    "created": [
                        created(
                            -1,
                            title="Курс",
                            price=10,
                            student_qty=0,
                            reviews_qty=0,
                            category=-99,
                        )
                    ]
                }
            },
        )
        assert response.status_code == 400
        assert "courses" in response.json()["errors"]
        assert Course.objects.count() == 0

    def test_response_returns_fresh_data(self, staff_client, category):
        body = save(
            staff_client,
            {"courses": {"created": [created(-1, **course_fields(category))]}},
        ).json()
        assert body["ok"] is True
        rows = body["data"]["courses"]
        assert len(rows) == 1
        assert rows[0]["id"] > 0
        assert rows[0]["category"] == category.pk
        assert rows[0]["created_at"]

    def test_several_rows_in_one_batch(self, staff_client, category):
        response = save(
            staff_client,
            {
                "courses": {
                    "created": [
                        created(-1, **course_fields(category, title="Первый")),
                        created(-2, **course_fields(category, title="Второй")),
                    ]
                }
            },
        )
        assert response.json()["summary"]["created"] == 2
        assert Course.objects.count() == 2

    def test_created_row_without_id_is_ignored(self, staff_client):
        response = save(
            staff_client, {"categories": {"created": [{"title": "Без ключа"}]}}
        )
        assert response.status_code == 200
        assert Category.objects.count() == 0


class TestUpdate:
    def test_update_category_title(self, staff_client, category):
        response = save(
            staff_client,
            {"categories": {"updated": [updated(category.pk, title="ИТ")]}},
        )
        assert response.json()["summary"]["updated"] == 1
        category.refresh_from_db()
        assert category.title == "ИТ"

    def test_update_keeps_case(self, staff_client, category):
        save(
            staff_client,
            {"categories": {"updated": [updated(category.pk, title="ит курсы")]}},
        )
        category.refresh_from_db()
        assert category.title == "ит курсы"

    def test_update_course_fields(self, staff_client, course):
        response = save(
            staff_client,
            {
                "courses": {
                    "updated": [
                        updated(
                            course.pk,
                            title="Python Advanced",
                            price=2500.5,
                            student_qty=30,
                            reviews_qty=11,
                            category=course.category_id,
                        )
                    ]
                }
            },
        )
        assert response.json()["summary"]["updated"] == 1
        course.refresh_from_db()
        assert (course.title, course.price, course.student_qty, course.reviews_qty) == (
            "Python Advanced",
            2500.5,
            30,
            11,
        )

    def test_update_accepts_string_numbers(self, staff_client, course):
        """Редакторы таблиц присылают числа строками — форма их приводит."""
        save(
            staff_client,
            {
                "courses": {
                    "updated": [
                        updated(
                            course.pk,
                            title=course.title,
                            price="1234.56",
                            student_qty="42",
                            reviews_qty="7",
                            category=str(course.category_id),
                        )
                    ]
                }
            },
        )
        course.refresh_from_db()
        assert course.price == 1234.56
        assert course.student_qty == 42

    def test_move_course_to_another_category(
        self, staff_client, course, second_category
    ):
        save(
            staff_client,
            {
                "courses": {
                    "updated": [
                        updated(
                            course.pk,
                            title=course.title,
                            price=course.price,
                            student_qty=course.student_qty,
                            reviews_qty=course.reviews_qty,
                            category=second_category.pk,
                        )
                    ]
                }
            },
        )
        course.refresh_from_db()
        assert course.category == second_category

    def test_id_and_created_at_are_read_only(self, staff_client, course):
        """Колонки только для чтения игнорируются даже если прислать их."""
        save(
            staff_client,
            {
                "courses": {
                    "updated": [
                        updated(
                            course.pk,
                            id=999,
                            created_at="2001-01-01T00:00",
                            title=course.title,
                            price=course.price,
                            student_qty=course.student_qty,
                            reviews_qty=course.reviews_qty,
                            category=course.category_id,
                        )
                    ]
                }
            },
        )
        course.refresh_from_db()
        assert course.pk != 999
        assert course.created_at.year != 2001

    def test_update_of_missing_row_is_ignored(self, staff_client):
        response = save(
            staff_client, {"categories": {"updated": [updated(12345, title="Нет")]}}
        )
        assert response.status_code == 200
        assert response.json()["summary"]["updated"] == 0

    def test_missing_required_field_is_an_error(self, staff_client, course):
        """Пакет содержит строку целиком: без категории сохранение не пройдёт."""
        response = save(
            staff_client,
            {"courses": {"updated": [updated(course.pk, title="Без цены")]}},
        )
        assert response.status_code == 400
        assert "price" in response.json()["errors"]["courses"][str(course.pk)]


class TestDelete:
    def test_delete_course(self, staff_client, course):
        response = save(staff_client, {"courses": {"deleted": [course.pk]}})
        assert response.json()["summary"]["deleted"] == 1
        assert not Course.objects.filter(pk=course.pk).exists()

    def test_delete_category_cascades_courses(self, staff_client, category, course):
        response = save(staff_client, {"categories": {"deleted": [category.pk]}})
        assert response.status_code == 200
        assert not Category.objects.filter(pk=category.pk).exists()
        assert not Course.objects.filter(pk=course.pk).exists()

    def test_delete_category_and_its_course_together(
        self, staff_client, category, course
    ):
        response = save(
            staff_client,
            {
                "categories": {"deleted": [category.pk]},
                "courses": {"deleted": [course.pk]},
            },
        )
        assert response.status_code == 200
        assert Category.objects.count() == 0
        assert Course.objects.count() == 0

    def test_delete_of_missing_row_is_ignored(self, staff_client):
        response = save(staff_client, {"courses": {"deleted": [424242]}})
        assert response.status_code == 200
        assert response.json()["summary"]["deleted"] == 0


class TestMixedBatch:
    def test_create_update_delete_at_once(
        self, staff_client, category, course, second_category
    ):
        response = save(
            staff_client,
            {
                "categories": {
                    "created": [created(-1, title="Маркетинг")],
                    "updated": [updated(second_category.pk, title="UX/UI")],
                    "deleted": [],
                },
                "courses": {
                    "created": [created(-2, **course_fields(category, title="SEO"))],
                    "updated": [
                        updated(
                            course.pk,
                            title="Python Pro",
                            price=3000,
                            student_qty=20,
                            reviews_qty=9,
                            category=category.pk,
                        )
                    ],
                    "deleted": [],
                },
            },
        )
        body = response.json()
        assert response.status_code == 200
        assert body["summary"] == {"created": 2, "updated": 2, "deleted": 0}
        assert Category.objects.filter(title="Маркетинг").exists()
        assert Category.objects.get(pk=second_category.pk).title == "UX/UI"
        assert Course.objects.filter(title="SEO").exists()
        assert Course.objects.get(pk=course.pk).title == "Python Pro"


class TestValidation:
    def test_empty_title_is_rejected(self, staff_client):
        response = save(
            staff_client, {"categories": {"created": [created(-1, title="   ")]}}
        )
        assert response.status_code == 400
        body = response.json()
        assert body["ok"] is False
        assert body["errors"]["categories"]["-1"]["title"]
        assert Category.objects.count() == 0

    def test_error_points_at_row_and_field(self, staff_client, course):
        response = save(
            staff_client,
            {
                "courses": {
                    "updated": [
                        updated(
                            course.pk,
                            title="",
                            price=course.price,
                            student_qty=course.student_qty,
                            reviews_qty=course.reviews_qty,
                            category=course.category_id,
                        )
                    ]
                }
            },
        )
        errors = response.json()["errors"]["courses"][str(course.pk)]
        assert errors["title"]
        course.refresh_from_db()
        assert course.title == "Python Basic"

    def test_negative_price_is_rejected(self, staff_client, category):
        response = save(
            staff_client,
            {
                "courses": {
                    "created": [created(-1, **course_fields(category, price=-100))]
                }
            },
        )
        assert response.status_code == 400
        assert "price" in response.json()["errors"]["courses"]["-1"]
        assert Course.objects.count() == 0

    def test_negative_counter_is_rejected(self, staff_client, category):
        response = save(
            staff_client,
            {
                "courses": {
                    "created": [created(-1, **course_fields(category, student_qty=-1))]
                }
            },
        )
        assert response.status_code == 400
        assert "student_qty" in response.json()["errors"]["courses"]["-1"]

    def test_not_a_number_is_rejected(self, staff_client, category):
        response = save(
            staff_client,
            {
                "courses": {
                    "created": [created(-1, **course_fields(category, price="много"))]
                }
            },
        )
        assert response.status_code == 400
        assert "price" in response.json()["errors"]["courses"]["-1"]

    def test_too_long_title_is_rejected(self, staff_client):
        response = save(
            staff_client, {"categories": {"created": [created(-1, title="д" * 256)]}}
        )
        assert response.status_code == 400
        assert "title" in response.json()["errors"]["categories"]["-1"]

    def test_error_messages_are_in_russian(self, staff_client, category):
        """Язык интерфейса русский, хотя LANGUAGE_CODE проекта — en-us."""
        response = save(
            staff_client,
            {
                "courses": {
                    "created": [
                        created(-1, **course_fields(category, title="", price=-5))
                    ]
                }
            },
        )
        errors = response.json()["errors"]["courses"]["-1"]
        assert errors["title"] == ["Укажите название."]
        assert errors["price"] == ["Не меньше 0."]

    def test_unknown_category_message(self, staff_client):
        response = save(
            staff_client,
            {
                "courses": {
                    "created": [
                        created(
                            -1,
                            title="Курс",
                            price=100,
                            student_qty=1,
                            reviews_qty=0,
                            category=424242,
                        )
                    ]
                }
            },
        )
        errors = response.json()["errors"]["courses"]["-1"]
        assert errors["category"] == ["Такой категории нет — обновите таблицу."]

    def test_all_or_nothing(self, staff_client, category):
        """Ошибка в одной таблице отменяет изменения во всех."""
        response = save(
            staff_client,
            {
                "categories": {"created": [created(-1, title="Хорошая категория")]},
                "courses": {
                    "created": [created(-2, **course_fields(category, price=-1))]
                },
            },
        )
        assert response.status_code == 400
        assert not Category.objects.filter(title="Хорошая категория").exists()
        assert Course.objects.count() == 0

    def test_several_bad_rows_are_all_reported(self, staff_client, category):
        response = save(
            staff_client,
            {
                "courses": {
                    "created": [
                        created(-1, **course_fields(category, title="")),
                        created(-2, **course_fields(category, price=-5)),
                    ]
                }
            },
        )
        errors = response.json()["errors"]["courses"]
        assert set(errors) == {"-1", "-2"}
