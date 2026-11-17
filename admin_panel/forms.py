"""Формы строк табличной панели.

Формы нужны только для валидации данных, приходящих из таблиц, — HTML они не
рисуют. Состав полей совпадает с редактируемыми колонками: id и created_at
намеренно исключены, поэтому панель не может их изменить.

Ограничения «не меньше нуля» заданы здесь, а не в модели shop: менять модели
нельзя (это потребовало бы миграцию), а отрицательная цена или число студентов
в таблице всё равно невозможны — интерфейс их не пропустит.

Сообщения об ошибках переведены на русский: LANGUAGE_CODE проекта — en-us, а
панель полностью русская, и эти тексты показываются в подсказках к ячейкам.
"""

from django import forms

from shop.models import Category, Course

TITLE_ERRORS = {
    "required": "Укажите название.",
    "max_length": "Не длиннее %(limit_value)s символов.",
}

NUMBER_ERRORS = {
    "required": "Укажите значение.",
    "invalid": "Нужно число.",
    "min_value": "Не меньше %(limit_value)s.",
}

COUNTER_ERRORS = {
    "required": "Укажите значение.",
    "invalid": "Нужно целое число.",
    "min_value": "Не меньше %(limit_value)s.",
}


class CategoryForm(forms.ModelForm):
    """Строка таблицы «Категории»."""

    title = forms.CharField(
        max_length=255, label="Название", error_messages=TITLE_ERRORS
    )

    class Meta:
        model = Category
        fields = ("title",)


class CourseForm(forms.ModelForm):
    """Строка таблицы «Курсы».

    В отличие от публичного API v1, здесь reviews_qty виден и редактируем:
    панель — внутренний инструмент работы с базой, а не внешний контракт.
    """

    title = forms.CharField(
        max_length=255, label="Название", error_messages=TITLE_ERRORS
    )
    price = forms.FloatField(
        min_value=0,
        label="Цена",
        error_messages={**NUMBER_ERRORS, "required": "Укажите цену."},
    )
    student_qty = forms.IntegerField(
        min_value=0,
        label="Количество студентов",
        error_messages={**COUNTER_ERRORS, "required": "Укажите количество студентов."},
    )
    reviews_qty = forms.IntegerField(
        min_value=0,
        label="Количество отзывов",
        error_messages={**COUNTER_ERRORS, "required": "Укажите количество отзывов."},
    )
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        label="Категория",
        empty_label=None,
        error_messages={
            "required": "Выберите категорию.",
            "invalid_choice": "Такой категории нет — обновите таблицу.",
        },
    )

    class Meta:
        model = Course
        fields = ("title", "price", "student_qty", "reviews_qty", "category")
