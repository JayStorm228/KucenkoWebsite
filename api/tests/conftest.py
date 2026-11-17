"""Общие фикстуры тестов API v1."""

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from api.models import ApiKey
from shop.models import Category, Course


@pytest.fixture
def category(db) -> Category:
    return Category.objects.create(title="Программирование")


@pytest.fixture
def course(category) -> Course:
    return Course.objects.create(
        title="Python Basic",
        price=1500.0,
        student_qty=12,
        reviews_qty=7,
        category=category,
    )


@pytest.fixture
def api_client() -> APIClient:
    """Клиент DRF без аутентификации."""
    return APIClient()


@pytest.fixture
def key_factory(db):
    """Фабрика ключей: key_factory("write") -> (ApiKey, значение ключа)."""

    def factory(scopes: str = "write", **kwargs) -> tuple[ApiKey, str]:
        return ApiKey.objects.create_key(
            name=f"Тестовый ключ ({scopes})", scopes=scopes, **kwargs
        )

    return factory


@pytest.fixture
def write_key(key_factory) -> str:
    _, raw_key = key_factory("write")
    return raw_key


@pytest.fixture
def delete_key(key_factory) -> str:
    _, raw_key = key_factory("delete")
    return raw_key


@pytest.fixture
def manage_key(key_factory) -> str:
    _, raw_key = key_factory("manage")
    return raw_key


@pytest.fixture
def auth_client(api_client, write_key) -> APIClient:
    """Клиент с ключом со скоупом write в заголовке X-API-Key."""
    api_client.credentials(HTTP_X_API_KEY=write_key)
    return api_client


@pytest.fixture
def staff_user(db) -> User:
    return User.objects.create_user(username="staff", password="secret", is_staff=True)


@pytest.fixture
def regular_user(db) -> User:
    return User.objects.create_user(username="buyer", password="secret")
