from django.contrib import admin
from django.urls import include, path

from .views import index

urlpatterns = [
    # Табличная панель — до admin.site.urls, иначе адрес перехватит штатная админка.
    path("admin/panel/", include("admin_panel.urls")),
    path("admin/", admin.site.urls, name="admin"),
    path("api/v1/", include("api.urls")),
    path("shop/", include("shop.urls")),
    path("", index, name="home"),
]

handler404 = "shop.views.page_not_found"
