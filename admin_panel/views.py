"""Представления табличной панели: страница и JSON-эндпоинты.

Все представления доступны только сотрудникам (is_staff). Страница наследует
оформление админки, эндпоинты возвращают JSON и на отказ отвечают JSON-ом же,
а не редиректом на страницу входа.
"""

import json
from functools import wraps

from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from .services import apply_panel_changes, build_panel_data


def api_staff_required(view_func):
    """Доступ к JSON-эндпоинтам только для сотрудников.

    В отличие от staff_member_required, не перенаправляет на страницу входа
    (клиенту таблицы редирект бесполезен), а сразу отвечает 403 с JSON.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if user.is_authenticated and user.is_active and user.is_staff:
            return view_func(request, *args, **kwargs)
        return JsonResponse(
            {
                "ok": False,
                "detail": "Требуется вход в админ-панель от имени сотрудника.",
            },
            status=403,
        )

    return wrapper


@staff_member_required
def panel(request):
    """Страница с таблицами категорий и курсов."""
    context = {
        **admin.site.each_context(request),
        "title": "Таблицы данных",
        "subtitle": "Категории и курсы как в базе: правка и добавление на месте",
    }
    return render(request, "admin_panel/panel.html", context)


@api_staff_required
@require_GET
def panel_data(request):
    """Данные обеих таблиц одним ответом."""
    return JsonResponse({"ok": True, "data": build_panel_data()})


@api_staff_required
@require_POST
def panel_save(request):
    """Пакетное сохранение изменений обеих таблиц."""
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "detail": "Ожидался JSON."}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse(
            {"ok": False, "detail": "Ожидался JSON-объект."}, status=400
        )

    result = apply_panel_changes(payload)
    if not result.ok:
        return JsonResponse(
            {
                "ok": False,
                "errors": result.errors,
                "detail": "Изменения не сохранены: исправьте подсвеченные ячейки.",
            },
            status=400,
        )
    return JsonResponse(
        {"ok": True, "summary": result.as_dict(), "data": build_panel_data()}
    )
