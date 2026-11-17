"""Сериализаторы API v1 для ресурсов Category и Course."""

from rest_framework import serializers

from shop.models import Category, Course

from .utils import capitalize_title

# Поле reviews_qty полностью исключено из API, но в модели Course оно
# обязательное (NOT NULL без default), поэтому при создании курса через API
# значение подставляется здесь.
DEFAULT_REVIEWS_QTY = 0


class CapitalizedTitleMixin:
    """Автоматическая капитализация заголовка при добавлении и изменении через API.

    Хук validate_<field> вызывается для любого записывающего запроса
    (POST, PUT, PATCH), поэтому заголовок приводится к Title Case и при
    создании, и при обновлении ресурса.
    """

    def validate_title(self, value: str) -> str:
        return capitalize_title(value)


class CategorySerializer(CapitalizedTitleMixin, serializers.ModelSerializer):
    """Категория курса.

    Поле created_at намеренно не входит в ответ API.
    """

    class Meta:
        model = Category
        fields = ("id", "title")


class CourseSerializer(CapitalizedTitleMixin, serializers.ModelSerializer):
    """Курс.

    Поля reviews_qty и created_at полностью исключены из API: клиент не может
    их ни прочитать, ни передать. При создании курса reviews_qty получает
    значение по умолчанию, created_at — текущее время (default модели).
    """

    class Meta:
        model = Course
        fields = ("id", "title", "price", "student_qty", "category")

    def create(self, validated_data):
        validated_data.setdefault("reviews_qty", DEFAULT_REVIEWS_QTY)
        return super().create(validated_data)
