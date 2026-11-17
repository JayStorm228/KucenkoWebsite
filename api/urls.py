"""Маршруты API v1.

Подключаются в config/urls.py с префиксом api/v1/, поэтому полные адреса
ресурсов: /api/v1/courses/ и /api/v1/categories/.
"""

from django.urls import include, path

from .routers import ApiV1Router
from .views import CategoryViewSet, CourseViewSet

app_name = "api"

router = ApiV1Router()
router.register("courses", CourseViewSet, basename="course")
router.register("categories", CategoryViewSet, basename="category")

#: Соответствие методов действиям вьюсета для маршрутов без завершающего слэша.
#: POST на детальный маршрут работает как частичное изменение — это требование
#: задачи (см. ApiV1Router).
LIST_ACTIONS = {"get": "list", "post": "create"}
DETAIL_ACTIONS = {
    "get": "retrieve",
    "put": "update",
    "patch": "partial_update",
    "post": "partial_update",
    "delete": "destroy",
}


def slashless_patterns() -> list:
    """Те же ресурсы по адресам без завершающего слэша: /api/v1/courses.

    Роутер DRF формирует адреса со слэшем, а без него записывающий запрос не
    доходит до представления: в DEBUG Django отвечает ошибкой RuntimeError из
    APPEND_SLASH, в боевом режиме — редиректом 301, при котором тело POST
    теряется. Дублируем маршруты явно, чтобы работали оба варианта адреса.
    """
    patterns = []
    resources = (
        ("courses", CourseViewSet, "course"),
        ("categories", CategoryViewSet, "category"),
    )
    for prefix, viewset, basename in resources:
        patterns += [
            path(
                prefix,
                viewset.as_view(
                    LIST_ACTIONS, suffix="List", detail=False, basename=basename
                ),
            ),
            path(
                f"{prefix}/<int:pk>",
                viewset.as_view(
                    DETAIL_ACTIONS, suffix="Instance", detail=True, basename=basename
                ),
            ),
        ]
    return patterns


urlpatterns = [
    path("", include(router.urls)),
    *slashless_patterns(),
]
