"""Чтение данных таблиц: admin_panel:data."""

import pytest

from shop.models import Category, Course

from .conftest import DATA_URL

COURSE_COLUMNS = {
    "id",
    "title",
    "price",
    "student_qty",
    "reviews_qty",
    "category",
    "created_at",
}
CATEGORY_COLUMNS = {"id", "title", "courses_count", "created_at"}


@pytest.fixture
def fetch_data(staff_client):
    """Запрос данных таблицы: вызывается уже после создания записей."""

    def fetch() -> dict:
        response = staff_client.get(DATA_URL)
        assert response.status_code == 200
        return response.json()["data"]

    return fetch


class TestAccess:
    def test_staff_gets_data(self, staff_client, category, course):
        response = staff_client.get(DATA_URL)
        assert response.status_code == 200
        assert response.json()["ok"] is True

    def test_regular_user_forbidden(self, user_client):
        response = user_client.get(DATA_URL)
        assert response.status_code == 403

    def test_api_key_does_not_grant_access(self, anonymous_client, key_header):
        """Ключ API v1 не даёт доступа к внутренней панели — только сессия."""
        response = anonymous_client.get(DATA_URL, headers=key_header)
        assert response.status_code == 403

    def test_only_get_allowed(self, staff_client):
        assert staff_client.post(DATA_URL).status_code == 405


class TestColumns:
    """Панель показывает все колонки базы, включая скрытые в публичном API."""

    def test_course_has_all_database_columns(self, fetch_data, course):
        row = next(row for row in fetch_data()["courses"] if row["id"] == course.pk)
        assert set(row) == COURSE_COLUMNS

    def test_category_has_all_database_columns(self, fetch_data, category):
        row = next(
            row for row in fetch_data()["categories"] if row["id"] == category.pk
        )
        assert set(row) == CATEGORY_COLUMNS

    def test_reviews_qty_is_visible(self, fetch_data, course):
        row = next(row for row in fetch_data()["courses"] if row["id"] == course.pk)
        assert row["reviews_qty"] == course.reviews_qty == 7

    def test_created_at_is_visible(self, fetch_data, course):
        row = next(row for row in fetch_data()["courses"] if row["id"] == course.pk)
        assert row["created_at"]
        assert row["created_at"].startswith(course.created_at.strftime("%Y-%m-%d"))

    def test_course_row_values(self, fetch_data, course):
        row = next(row for row in fetch_data()["courses"] if row["id"] == course.pk)
        assert row["title"] == "Python Basic"
        assert row["price"] == 1500.0
        assert row["student_qty"] == 12
        assert row["category"] == course.category_id

    def test_category_row_counts_courses(self, fetch_data, category, course):
        row = next(
            row for row in fetch_data()["categories"] if row["id"] == category.pk
        )
        assert row["courses_count"] == 1

    def test_category_without_courses(self, fetch_data, second_category):
        row = next(
            row for row in fetch_data()["categories"] if row["id"] == second_category.pk
        )
        assert row["courses_count"] == 0


class TestRawValues:
    """Значения отдаются как в базе — без капитализации, которую делает API v1."""

    def test_titles_are_not_capitalized(self, fetch_data):
        category = Category.objects.create(title="дизайн интерфейсов")
        Course.objects.create(
            title="figma с нуля",
            price=100.0,
            student_qty=1,
            reviews_qty=0,
            category=category,
        )
        data = fetch_data()
        assert data["categories"][0]["title"] == "дизайн интерфейсов"
        assert data["courses"][0]["title"] == "figma с нуля"

    def test_rows_are_ordered_by_id(self, fetch_data):
        first = Category.objects.create(title="А")
        second = Category.objects.create(title="Б")
        Course.objects.create(
            title="2", price=1, student_qty=0, reviews_qty=0, category=first
        )
        Course.objects.create(
            title="1", price=1, student_qty=0, reviews_qty=0, category=second
        )
        data = fetch_data()
        assert [row["id"] for row in data["categories"]] == [first.pk, second.pk]
        assert [row["title"] for row in data["courses"]] == ["2", "1"]

    def test_empty_database(self, fetch_data):
        assert fetch_data() == {"categories": [], "courses": []}
