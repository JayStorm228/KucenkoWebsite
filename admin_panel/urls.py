"""Маршруты табличной панели.

Подключаются в config/urls.py с префиксом admin/panel/ — до admin.site.urls,
чтобы адрес не перехватывала штатная админка.
"""

from django.urls import path

from . import views

app_name = "admin_panel"

urlpatterns = [
    path("", views.panel, name="panel"),
    path("api/data/", views.panel_data, name="data"),
    path("api/save/", views.panel_save, name="save"),
]
