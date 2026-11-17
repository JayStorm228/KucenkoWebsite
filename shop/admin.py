"""Админка магазина.

Категории и курсы управляются с одной страницы: в форму категории встроен
инлайн со всеми её курсами, поэтому добавлять, править и удалять курсы можно
не покидая страницу категории. Отдельный список всех курсов оставлен для
поиска, фильтра по категориям и массовых действий.
"""

from django.contrib import admin
from django.db.models import Count

from . import models


class CourseInline(admin.TabularInline):
    """Курсы категории — таблица прямо в форме категории."""

    model = models.Course
    extra = 1
    fields = ("title", "price", "student_qty", "reviews_qty")
    verbose_name = "курс"
    verbose_name_plural = "Курсы категории"


@admin.register(models.Category)
class CategoryAdmin(admin.ModelAdmin):
    """Категория вместе с её курсами на одной странице."""

    inlines = (CourseInline,)
    list_display = ("id", "title", "courses_count", "created_at")
    search_fields = ("title", "course__title")
    ordering = ("title",)

    @admin.display(description="Курсов", ordering="courses_count")
    def courses_count(self, obj) -> int:
        return obj.courses_count

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(courses_count=Count("course"))


@admin.register(models.Course)
class CourseAdmin(admin.ModelAdmin):
    """Общий список курсов по всем категориям."""

    list_display = (
        "id",
        "title",
        "category",
        "price",
        "student_qty",
        "reviews_qty",
        "created_at",
    )
    list_filter = ("category",)
    search_fields = ("title", "category__title")
    autocomplete_fields = ("category",)
    list_select_related = ("category",)
    ordering = ("title",)
