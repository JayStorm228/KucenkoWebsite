"""Тесты API v1 для ресурса Course (/api/v1/courses/)."""

import pytest
from django.urls import reverse
from rest_framework import status

from shop.models import Course

pytestmark = pytest.mark.django_db


def course_list_url() -> str:
    return reverse("api:course-list")


def course_detail_url(course_id: int) -> str:
    return reverse("api:course-detail", args=[course_id])


def course_payload(category, title: str = "python basics") -> dict:
    return {
        "title": title,
        "price": 999.5,
        "student_qty": 3,
        "category": category.id,
    }


class TestPublicRead:
    """Чтение курсов доступно без ключа (требования 1 и списка ресурсов)."""

    def test_list_without_key(self, api_client, course):
        response = api_client.get(course_list_url())
        assert response.status_code == status.HTTP_200_OK
        assert [item["id"] for item in response.json()] == [course.id]

    def test_retrieve_without_key(self, api_client, course):
        response = api_client.get(course_detail_url(course.id))
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "id": course.id,
            "title": course.title,
            "price": course.price,
            "student_qty": course.student_qty,
            "category": course.category_id,
        }

    def test_reviews_qty_and_created_at_are_hidden(self, api_client, course):
        payload = api_client.get(course_detail_url(course.id)).json()
        assert "reviews_qty" not in payload
        assert "created_at" not in payload

    def test_list_items_hide_reviews_qty_and_created_at(self, api_client, course):
        payload = api_client.get(course_list_url()).json()[0]
        assert "reviews_qty" not in payload
        assert "created_at" not in payload

    def test_retrieve_unknown_id_returns_404(self, api_client):
        response = api_client.get(course_detail_url(999_999))
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestCreate:
    """POST /api/v1/courses/ — создание курса по API-ключу."""

    def test_without_key_returns_401(self, api_client, category):
        response = api_client.post(
            course_list_url(), course_payload(category), format="json"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.headers["WWW-Authenticate"].startswith("ApiKey")
        assert not Course.objects.exists()

    def test_with_invalid_key_returns_401(self, api_client, category):
        api_client.credentials(HTTP_X_API_KEY="kcn_deadbeef_wrong-secret")
        response = api_client.post(
            course_list_url(), course_payload(category), format="json"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_with_write_key_creates_course(self, auth_client, category):
        response = auth_client.post(
            course_list_url(), course_payload(category), format="json"
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["id"]
        assert data["price"] == 999.5
        assert data["student_qty"] == 3
        assert data["category"] == category.id

    def test_title_is_capitalized_on_create(self, auth_client, category):
        response = auth_client.post(
            course_list_url(),
            course_payload(category, "  django   rest framework "),
            format="json",
        )
        assert response.json()["title"] == "Django Rest Framework"

    def test_reviews_qty_defaults_to_zero(self, auth_client, category):
        data = auth_client.post(
            course_list_url(), course_payload(category), format="json"
        ).json()
        course = Course.objects.get(pk=data["id"])
        assert course.reviews_qty == 0
        assert course.created_at is not None

    def test_hidden_fields_from_client_are_ignored(self, auth_client, category):
        payload = course_payload(category) | {
            "reviews_qty": 100,
            "created_at": "2000-01-01",
        }
        response = auth_client.post(course_list_url(), payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert "reviews_qty" not in response.json()
        assert Course.objects.get(pk=response.json()["id"]).reviews_qty == 0

    def test_with_manage_key_creates_course(self, api_client, manage_key, category):
        api_client.credentials(HTTP_X_API_KEY=manage_key)
        response = api_client.post(
            course_list_url(), course_payload(category), format="json"
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_with_delete_key_returns_403(self, api_client, delete_key, category):
        api_client.credentials(HTTP_X_API_KEY=delete_key)
        response = api_client.post(
            course_list_url(), course_payload(category), format="json"
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert not Course.objects.exists()

    def test_key_can_be_passed_in_authorization_header(
        self, api_client, write_key, category
    ):
        api_client.credentials(HTTP_AUTHORIZATION=f"ApiKey {write_key}")
        response = api_client.post(
            course_list_url(), course_payload(category), format="json"
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_category_is_required(self, auth_client):
        payload = {"title": "курс без категории", "price": 1, "student_qty": 1}
        response = auth_client.post(course_list_url(), payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "category" in response.json()

    def test_unknown_category_returns_400(self, auth_client):
        payload = {
            "title": "курс",
            "price": 1,
            "student_qty": 1,
            "category": 999_999,
        }
        response = auth_client.post(course_list_url(), payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "category" in response.json()


class TestUpdate:
    """Изменение курса по id: PUT, PATCH и POST (требование задачи)."""

    def test_put_with_write_key(self, auth_client, course):
        payload = {
            "title": "advanced python",
            "price": 2000,
            "student_qty": 5,
            "category": course.category_id,
        }
        response = auth_client.put(course_detail_url(course.id), payload, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["title"] == "Advanced Python"
        course.refresh_from_db()
        assert course.price == 2000

    def test_patch_with_write_key(self, auth_client, course):
        response = auth_client.patch(
            course_detail_url(course.id), {"title": "django master"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["title"] == "Django Master"

    def test_post_on_detail_with_write_key(self, auth_client, course):
        """POST на детальный маршрут работает как частичное изменение."""
        response = auth_client.post(
            course_detail_url(course.id), {"title": "post update"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["title"] == "Post Update"
        course.refresh_from_db()
        assert course.title == "Post Update"
        # Не переданные поля не сбрасываются.
        assert course.price == 1500.0

    def test_post_on_detail_without_key_returns_401_not_405(self, api_client, course):
        response = api_client.post(
            course_detail_url(course.id), {"title": "x"}, format="json"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_update_with_delete_key_returns_403(self, api_client, delete_key, course):
        api_client.credentials(HTTP_X_API_KEY=delete_key)
        response = api_client.patch(
            course_detail_url(course.id), {"title": "нельзя"}, format="json"
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        course.refresh_from_db()
        assert course.title == "Python Basic"

    def test_reviews_qty_cannot_be_changed(self, auth_client, course):
        response = auth_client.patch(
            course_detail_url(course.id), {"reviews_qty": 42}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        course.refresh_from_db()
        assert course.reviews_qty == 7


class TestDelete:
    """DELETE /api/v1/courses/{id}/ — удаление по ключу со скоупом delete."""

    def test_with_delete_key_removes_course(self, api_client, delete_key, course):
        api_client.credentials(HTTP_X_API_KEY=delete_key)
        response = api_client.delete(course_detail_url(course.id))
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Course.objects.exists()

    def test_with_manage_key_removes_course(self, api_client, manage_key, course):
        api_client.credentials(HTTP_X_API_KEY=manage_key)
        assert (
            api_client.delete(course_detail_url(course.id)).status_code
            == status.HTTP_204_NO_CONTENT
        )

    def test_with_write_key_returns_403(self, auth_client, course):
        response = auth_client.delete(course_detail_url(course.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert Course.objects.exists()

    def test_without_key_returns_401(self, api_client, course):
        response = api_client.delete(course_detail_url(course.id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert Course.objects.exists()

    def test_unknown_id_returns_404(self, api_client, manage_key):
        api_client.credentials(HTTP_X_API_KEY=manage_key)
        assert (
            api_client.delete(course_detail_url(999_999)).status_code
            == status.HTTP_404_NOT_FOUND
        )


class TestSessionAccess:
    """Сотрудник, вошедший в админку, может работать с API через сессию."""

    def test_staff_session_can_create(self, api_client, staff_user, category):
        api_client.force_login(staff_user)
        response = api_client.post(
            course_list_url(), course_payload(category), format="json"
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_staff_session_can_delete(self, api_client, staff_user, course):
        api_client.force_login(staff_user)
        response = api_client.delete(course_detail_url(course.id))
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_regular_user_session_returns_403(self, api_client, regular_user, category):
        api_client.force_login(regular_user)
        response = api_client.post(
            course_list_url(), course_payload(category), format="json"
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestRoutesWithoutTrailingSlash:
    """Адреса из задания (api/v1/courses) работают и без завершающего слэша."""

    def test_list(self, api_client):
        assert api_client.get("/api/v1/courses").status_code == status.HTTP_200_OK

    def test_retrieve(self, api_client, course):
        response = api_client.get(f"/api/v1/courses/{course.id}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == course.id

    def test_create_with_write_key(self, auth_client, category):
        response = auth_client.post(
            "/api/v1/courses", course_payload(category), format="json"
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_without_key_returns_401(self, api_client, category):
        response = api_client.post(
            "/api/v1/courses", course_payload(category), format="json"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_post_on_detail_changes_course(self, auth_client, course):
        response = auth_client.post(
            f"/api/v1/courses/{course.id}", {"title": "без слэша"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["title"] == "Без Слэша"

    def test_delete_on_detail(self, api_client, delete_key, course):
        api_client.credentials(HTTP_X_API_KEY=delete_key)
        response = api_client.delete(f"/api/v1/courses/{course.id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_categories_without_slash(self, auth_client):
        response = auth_client.post(
            "/api/v1/categories", {"title": "без слэша"}, format="json"
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["title"] == "Без Слэша"
        assert auth_client.get("/api/v1/categories").status_code == status.HTTP_200_OK
