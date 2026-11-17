"""Представления API v1: ресурсы Category и Course."""

from rest_framework import viewsets
from rest_framework.authentication import SessionAuthentication

from shop.models import Category, Course

from .authentication import ApiKeyAuthentication
from .permissions import ApiKeyScopePermission
from .serializers import CategorySerializer, CourseSerializer


class CourseViewSet(viewsets.ModelViewSet):
    """Курсы.

    * GET  /api/v1/courses/          — список курсов, без ключа;
    * GET  /api/v1/courses/{id}/     — курс по id, без ключа;
    * POST /api/v1/courses/          — создание курса, ключ со скоупом write;
    * PUT|PATCH|POST /api/v1/courses/{id}/ — изменение, ключ со скоупом write;
    * DELETE /api/v1/courses/{id}/   — удаление, ключ со скоупом delete.

    Аутентификация и авторизация берутся из DEFAULT_* настроек DRF и продублированы
    здесь явно, чтобы правила ресурса были видны в самом представлении.
    """

    queryset = Course.objects.select_related("category").order_by("id")
    serializer_class = CourseSerializer
    authentication_classes = (ApiKeyAuthentication, SessionAuthentication)
    permission_classes = (ApiKeyScopePermission,)


class CategoryViewSet(viewsets.ModelViewSet):
    """Категории курсов.

    Набор маршрутов и правила доступа те же, что у CourseViewSet:
    чтение публичное, запись — по API-ключу с нужным скоупом.
    """

    queryset = Category.objects.order_by("id")
    serializer_class = CategorySerializer
    authentication_classes = (ApiKeyAuthentication, SessionAuthentication)
    permission_classes = (ApiKeyScopePermission,)
