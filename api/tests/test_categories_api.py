"""Тесты API v1 для ресурса Category (/api/v1/categories/)."""

import pytest
from django.urls import reverse
from rest_framework import status

from shop.models import Category

pytestmark = pytest.mark.django_db


def category_list_url() -> str:
    return reverse("api:category-list")


def category_detail_url(category_id: int) -> str:
    return reverse("api:category-detail", args=[category_id])


class TestPublicRead:
    """Чтение категорий доступно без ключа."""

    def test_list_without_key(self, api_client, category):
        response = api_client.get(category_list_url())
        assert response.status_code == status.HTTP_200_OK
        assert [item["id"] for item in response.json()] == [category.id]

    def test_retrieve_without_key(self, api_client, category):
        response = api_client.get(category_detail_url(category.id))
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"id": category.id, "title": category.title}

    def test_created_at_is_hidden(self, api_client, category):
        payload = api_client.get(category_detail_url(category.id)).json()
        assert "created_at" not in payload
        assert list(payload) == ["id", "title"]

    def test_retrieve_unknown_id_returns_404(self, api_client):
        response = api_client.get(category_detail_url(999_999))
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestCreate:
    """POST /api/v1/categories/ — создание категории по API-ключу."""

    def test_without_key_returns_401(self, api_client):
        response = api_client.post(
            category_list_url(), {"title": "аналитика"}, format="json"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert not Category.objects.filter(title="аналитика").exists()

    def test_with_write_key_creates_category(self, auth_client):
        response = auth_client.post(
            category_list_url(), {"title": "аналитика"}, format="json"
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["title"] == "Аналитика"

    def test_title_is_capitalized(self, auth_client):
        response = auth_client.post(
            category_list_url(), {"title": "  machine   learning "}, format="json"
        )
        assert response.json()["title"] == "Machine Learning"

    def test_with_delete_key_returns_403(self, api_client, delete_key):
        api_client.credentials(HTTP_X_API_KEY=delete_key)
        response = api_client.post(
            category_list_url(), {"title": "аналитика"}, format="json"
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_created_at_cannot_be_set_by_client(self, auth_client):
        payload = {"title": "аналитика", "created_at": "2000-01-01T00:00:00Z"}
        response = auth_client.post(category_list_url(), payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert "created_at" not in response.json()
        assert Category.objects.get(pk=response.json()["id"]).created_at.year != 2000


class TestUpdate:
    """Изменение категории по id: PUT, PATCH и POST."""

    def test_put_with_write_key(self, auth_client, category):
        response = auth_client.put(
            category_detail_url(category.id), {"title": "дизайн"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["title"] == "Дизайн"

    def test_patch_with_write_key(self, auth_client, category):
        response = auth_client.patch(
            category_detail_url(category.id), {"title": "маркетинг"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["title"] == "Маркетинг"

    def test_post_on_detail_with_write_key(self, auth_client, category):
        response = auth_client.post(
            category_detail_url(category.id), {"title": "тестирование"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        category.refresh_from_db()
        assert category.title == "Тестирование"

    def test_without_key_returns_401(self, api_client, category):
        response = api_client.patch(
            category_detail_url(category.id), {"title": "нельзя"}, format="json"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        category.refresh_from_db()
        assert category.title == "Программирование"


class TestDelete:
    """DELETE /api/v1/categories/{id}/ — удаление по ключу со скоупом delete."""

    def test_with_delete_key_removes_category(self, api_client, delete_key, category):
        api_client.credentials(HTTP_X_API_KEY=delete_key)
        response = api_client.delete(category_detail_url(category.id))
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Category.objects.exists()

    def test_with_write_key_returns_403(self, auth_client, category):
        response = auth_client.delete(category_detail_url(category.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert Category.objects.exists()

    def test_without_key_returns_401(self, api_client, category):
        response = api_client.delete(category_detail_url(category.id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert Category.objects.exists()


class TestApiRoot:
    def test_root_lists_resources(self, api_client):
        response = api_client.get(reverse("api:api-root"))
        assert response.status_code == status.HTTP_200_OK
        assert set(response.json()) == {"courses", "categories"}
