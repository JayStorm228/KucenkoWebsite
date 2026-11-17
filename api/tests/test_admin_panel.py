"""Тесты переделанной админ-панели.

Проверяется, что категории и курсы управляются с одной страницы (инлайн),
что панель оформлена в стиле веб-приложения и что API-ключ показывается
в админке ровно один раз.

Используется фикстура admin_client из pytest-django — клиент, вошедший
под суперпользователем.
"""

import re

import pytest
from django.urls import reverse

from api.models import ApiKey
from shop.models import Course

pytestmark = pytest.mark.django_db

KEY_PATTERN = re.compile(r"kcn_[0-9a-f]{8}_[A-Za-z0-9_-]+")


class TestAdminStyling:
    def test_index_page_loads_bootstrap_and_site_css(self, admin_client):
        html = admin_client.get(reverse("admin:index")).content.decode()
        assert "css/bootstrap.min.css" in html
        assert "css/admin_site.css" in html

    def test_index_page_has_site_navbar(self, admin_client):
        html = admin_client.get(reverse("admin:index")).content.decode()
        assert (
            'class="navbar navbar-expand-lg navbar-dark bg-dark admin-navbar"' in html
        )
        assert "Магазин Куценко В." in html
        assert reverse("home") in html
        assert reverse("shop:index") in html

    def test_changelist_page_keeps_site_styles(self, admin_client):
        html = admin_client.get(
            reverse("admin:shop_course_changelist")
        ).content.decode()
        assert "css/bootstrap.min.css" in html
        assert "css/admin_site.css" in html

    def test_change_page_keeps_site_styles(self, admin_client, category):
        url = reverse("admin:shop_category_change", args=[category.id])
        html = admin_client.get(url).content.decode()
        assert "css/bootstrap.min.css" in html
        assert "css/admin_site.css" in html

    def test_login_page_keeps_site_styles(self, client):
        html = client.get(reverse("admin:login")).content.decode()
        assert "css/bootstrap.min.css" in html
        assert "css/admin_site.css" in html


class TestOnePageManagement:
    """Категория и её курсы — на одной странице.

    Префикс инлайна — course_set: так Django называет набор форм по имени
    обратного доступа от Course к Category.
    """

    def category_form_data(self, category) -> dict:
        return {
            "title": category.title,
            "created_at_0": "2026-01-01",
            "created_at_1": "12:00:00",
            "_save": "Сохранить",
        }

    def inline_form_data(self, index: int, course) -> dict:
        return {
            f"course_set-{index}-id": str(course.id),
            f"course_set-{index}-category": str(course.category_id),
            f"course_set-{index}-title": course.title,
            f"course_set-{index}-price": str(course.price),
            f"course_set-{index}-student_qty": str(course.student_qty),
            f"course_set-{index}-reviews_qty": str(course.reviews_qty),
        }

    def test_category_page_contains_courses_inline(
        self, admin_client, category, course
    ):
        url = reverse("admin:shop_category_change", args=[category.id])
        html = admin_client.get(url).content.decode()
        assert "Курсы категории" in html
        assert 'name="course_set-0-title"' in html
        assert course.title in html

    def test_category_changelist_shows_courses_count(
        self, admin_client, category, course
    ):
        html = admin_client.get(
            reverse("admin:shop_category_changelist")
        ).content.decode()
        assert "Курсов" in html

    def test_course_can_be_added_on_category_page(self, admin_client, category, course):
        url = reverse("admin:shop_category_change", args=[category.id])
        data = (
            self.category_form_data(category)
            | self.inline_form_data(0, course)
            | {
                "course_set-TOTAL_FORMS": "2",
                "course_set-INITIAL_FORMS": "1",
                "course_set-MIN_NUM_FORMS": "0",
                "course_set-MAX_NUM_FORMS": "1000",
                "course_set-1-title": "курс добавлен со страницы категории",
                "course_set-1-price": "500",
                "course_set-1-student_qty": "1",
                "course_set-1-reviews_qty": "0",
            }
        )
        response = admin_client.post(url, data, follow=True)
        assert response.status_code == 200
        assert Course.objects.filter(
            category=category, title="курс добавлен со страницы категории"
        ).exists()

    def test_course_can_be_edited_on_category_page(
        self, admin_client, category, course
    ):
        url = reverse("admin:shop_category_change", args=[category.id])
        data = (
            self.category_form_data(category)
            | self.inline_form_data(0, course)
            | {
                "course_set-TOTAL_FORMS": "1",
                "course_set-INITIAL_FORMS": "1",
                "course_set-MIN_NUM_FORMS": "0",
                "course_set-MAX_NUM_FORMS": "1000",
                "course_set-0-title": "курс переименован на странице категории",
            }
        )
        response = admin_client.post(url, data, follow=True)
        assert response.status_code == 200
        course.refresh_from_db()
        assert course.title == "курс переименован на странице категории"

    def test_course_can_be_deleted_on_category_page(
        self, admin_client, category, course
    ):
        url = reverse("admin:shop_category_change", args=[category.id])
        data = (
            self.category_form_data(category)
            | self.inline_form_data(0, course)
            | {
                "course_set-TOTAL_FORMS": "1",
                "course_set-INITIAL_FORMS": "1",
                "course_set-MIN_NUM_FORMS": "0",
                "course_set-MAX_NUM_FORMS": "1000",
                "course_set-0-DELETE": "on",
            }
        )
        response = admin_client.post(url, data, follow=True)
        assert response.status_code == 200
        assert not Course.objects.exists()


class TestApiKeyAdmin:
    def test_changelist_renders(self, admin_client, key_factory):
        key_factory("write")
        html = admin_client.get(reverse("admin:api_apikey_changelist")).content.decode()
        assert "API-ключи" in html
        assert "Тестовый ключ (write)" in html

    def test_key_value_is_shown_once_and_not_stored(self, admin_client):
        url = reverse("admin:api_apikey_add")
        response = admin_client.post(
            url,
            {"name": "Ключ из админки", "scopes": "write,delete", "is_active": "on"},
            follow=True,
        )
        assert response.status_code == 200
        html = response.content.decode()

        match = KEY_PATTERN.search(html)
        assert match, "значение нового ключа должно показываться после создания"
        raw_key = match.group()

        api_key = ApiKey.objects.get(name="Ключ из админки")
        # Ключ работоспособен, но в базе лежит только его хэш.
        assert ApiKey.objects.verify(raw_key) == api_key
        assert api_key.hashed_key != raw_key
        assert api_key.scopes == "write, delete"

    def test_key_value_is_not_shown_on_edit(self, admin_client, key_factory):
        api_key, _ = key_factory("write")
        url = reverse("admin:api_apikey_change", args=[api_key.id])
        html = admin_client.get(url).content.decode()
        assert api_key.hashed_key not in html
        assert not KEY_PATTERN.search(html)

    def test_unknown_scope_is_rejected(self, admin_client):
        url = reverse("admin:api_apikey_add")
        response = admin_client.post(
            url, {"name": "Ключ", "scopes": "read"}, follow=True
        )
        assert response.status_code == 200
        assert not ApiKey.objects.filter(name="Ключ").exists()
        assert "Неизвестные скоупы" in response.content.decode()
