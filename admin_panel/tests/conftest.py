"""Общие фикстуры тестов табличной панели (/admin/panel/)."""

import pytest
from django.contrib.auth.models import User
from django.test import Client

from api.models import ApiKey
from shop.models import Category, Course

PANEL_URL = "/admin/panel/"
DATA_URL = "/admin/panel/api/data/"
SAVE_URL = "/admin/panel/api/save/"


@pytest.fixture
def category(db) -> Category:
    return Category.objects.create(title="Программирование")


@pytest.fixture
def second_category(db) -> Category:
    return Category.objects.create(title="Дизайн")


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
def staff_user(db) -> User:
    return User.objects.create_user(username="staff", password="secret", is_staff=True)


@pytest.fixture
def regular_user(db) -> User:
    return User.objects.create_user(username="buyer", password="secret")


@pytest.fixture
def staff_client(staff_user) -> Client:
    """Клиент, вошедший как сотрудник."""
    client = Client()
    client.force_login(staff_user)
    return client


@pytest.fixture
def anonymous_client(db) -> Client:
    return Client()


@pytest.fixture
def user_client(regular_user) -> Client:
    """Клиент обычного пользователя (не сотрудник)."""
    client = Client()
    client.force_login(regular_user)
    return client


@pytest.fixture
def csrf_client(staff_user) -> Client:
    """Клиент сотрудника с проверкой CSRF-токена."""
    client = Client(enforce_csrf_checks=True)
    client.force_login(staff_user)
    return client


@pytest.fixture
def key_header(db) -> dict:
    """Заголовок с API-ключом v1: панель работает по сессии, а не по ключу."""
    _, raw_key = ApiKey.objects.create_key(name="Тестовый ключ", scopes="manage")
    return {"X-API-Key": raw_key}
