"""Роутер API v1."""

from rest_framework.routers import DefaultRouter, Route


class ApiV1Router(DefaultRouter):
    """DefaultRouter, у которого детальный маршрут принимает ещё и POST.

    По требованию задачи изменение ресурса по id выполняется в том числе
    методом POST, тогда как DRF для детального маршрута (/courses/{id}/)
    по умолчанию разрешает только GET, PUT, PATCH и DELETE и отвечает 405
    на POST. Добавляем соответствие post -> partial_update.

    Важная деталь: словари mapping у маршрутов SimpleRouter общие для всех
    экземпляров роутера, поэтому изменять их на месте нельзя — создаём копию
    маршрута через _replace().
    """

    #: Действие, на которое отображается POST детального маршрута.
    detail_post_action = "partial_update"

    def get_routes(self, viewset):
        routes = []
        for route in super().get_routes(viewset):
            if (
                isinstance(route, Route)
                and route.detail
                and "post" not in route.mapping
            ):
                mapping = {**route.mapping, "post": self.detail_post_action}
                route = route._replace(mapping=mapping)
            routes.append(route)
        return routes
