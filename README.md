# Магазин Куценко В.

Учебный проект на Django: витрина курсов, REST API версии v1 на Django REST Framework
и админ-панель, оформленная в стиле сайта.

## Состав

| Что | Где |
| --- | --- |
| Витрина курсов | приложение `shop`, маршруты `/` и `/shop/` |
| API v1 | приложение `api`, маршруты `/api/v1/` |
| Админ-панель | `/admin/`, оформление — `templates/admin/base_site.html` и `static/css/admin_site.css` |

Приложение `shop` продолжает работать как раньше: правки коснулись только файла
`shop/admin.py` (настройка панели администратора), а также подключения API в
`config/settings.py` (`INSTALLED_APPS`, `REST_FRAMEWORK`) и `config/urls.py`
(маршрут `api/v1/`). Модели, представления и адреса `shop` не изменялись.

## Запуск

```bash
uv sync                                   # зависимости из pyproject.toml / uv.lock
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Статические файлы

В проекте `DEBUG = False`, а в этом режиме `runserver` статику **не отдаёт**: страницы
открываются с кодом 200, но любые `/static/...` отвечают 404, и сайт с админкой выглядят
-unstyled. Это не связано с API: так же ведёт себя и Bootstrap, который витрина использует
с самого начала. Два рабочих варианта:

```bash
# локально — отдавать статику силами runserver даже при DEBUG=False
python manage.py runserver --insecure

# для развёртывания — собрать статику в STATIC_ROOT и отдавать её веб-сервером
python manage.py collectstatic        # -> staticfiles/ (каталог в .gitignore)
```

Копировать в папку `static/` проекта файлы админки (`admin/css/base.css`, `dark_mode.css`,
`nav_sidebar.css`, `dashboard.css`, `responsive.css`, `admin/js/theme.js`,
`admin/js/nav_sidebar.js`) **не нужно**: их отдаёт приложение `django.contrib.admin`
через `AppDirectoriesFinder`, а `collectstatic` сам собирает их в `STATIC_ROOT` вместе с
`static/css/admin_site.css`, Bootstrap и остальной статикой проекта. Из своих файлов
админке нужны только два, и они в репозитории есть:

| Файл | Где | Зачем |
| --- | --- | --- |
| `static/css/admin_site.css` | проект | палитра и вид панели в стиле сайта |
| `static/css/bootstrap.min.css`, `static/js/bootstrap.bundle.min.js` | проект | навигационная панель и сетка Bootstrap |
| `static/admin/**` | пакет `django.contrib.admin` | служебные стили и скрипты самой админки |

## API v1

### Маршруты и права доступа

| Метод | Маршрут | Доступ | Что делает |
| --- | --- | --- | --- |
| GET | `/api/v1/` | без ключа | корень API: ссылки на ресурсы |
| GET | `/api/v1/courses/` | без ключа | список курсов |
| GET | `/api/v1/courses/{id}/` | без ключа | курс по id |
| POST | `/api/v1/courses/` | ключ `write`/`manage` | создать курс |
| PUT, PATCH, POST | `/api/v1/courses/{id}/` | ключ `write`/`manage` | изменить курс по id |
| DELETE | `/api/v1/courses/{id}/` | ключ `delete`/`manage` | удалить курс по id |
| GET | `/api/v1/categories/` | без ключа | список категорий |
| GET | `/api/v1/categories/{id}/` | без ключа | категорию по id |
| POST | `/api/v1/categories/` | ключ `write`/`manage` | создать категорию |
| PUT, PATCH, POST | `/api/v1/categories/{id}/` | ключ `write`/`manage` | изменить категорию по id |
| DELETE | `/api/v1/categories/{id}/` | ключ `delete`/`manage` | удалить категорию по id |

POST на детальный маршрут (`/api/v1/courses/{id}/`) работает как PATCH — частичное
изменение: это требование задачи, по умолчанию DRF отвечает на такой запрос 405.
PUT ожидает полный набор полей, PATCH и POST — любые поля частично.

Работают оба написания адреса — со слэшем на конце и без него
(`/api/v1/courses/` и `/api/v1/courses`, `/api/v1/courses/1/` и `/api/v1/courses/1`):
в задании маршруты указаны без слэша, а роутер DRF формирует адреса со слэшем,
поэтому варианты без слэша продублированы в `api/urls.py`. Без этого POST на
адрес без слэша не доходит до представления (в DEBUG — `RuntimeError` из
`APPEND_SLASH`, в боевом режиме — редирект 301 с потерей тела запроса).

### Формат ответов

```jsonc
// GET /api/v1/courses/1/
{ "id": 1, "title": "Python Basic", "price": 1500.0, "student_qty": 12, "category": 1 }

// GET /api/v1/categories/1/
{ "id": 1, "title": "Программирование" }
```

Поля `reviews_qty` и `created_at` у курса, а также `created_at` у категории
**полностью исключены из API**: их нельзя ни прочитать, ни передать. Значения,
присланные клиентом в этих полях, игнорируются. Так как у `Course.reviews_qty`
в модели нет значения по умолчанию, при создании курса через API сериализатор
подставляет `0` (см. `DEFAULT_REVIEWS_QTY` в `api/serializers.py`); `created_at`
получает текущее время из default-значения модели.

### Аутентификация: API-ключ

Ключ передаётся в заголовке `X-API-Key` либо в `Authorization` со схемой `ApiKey`:

```bash
curl -H "X-API-Key: kcn_1a2b3c4d_xxxxxxxx" http://127.0.0.1:8000/api/v1/courses/
curl -H "Authorization: ApiKey kcn_1a2b3c4d_xxxxxxxx" http://127.0.0.1:8000/api/v1/courses/
```

Ключ состоит из префикса и секретной части (`kcn_<префикс>_<секрет>`). В базе
(`api_apikey`) хранится только SHA-256 хэш, поэтому значение показывается **один раз**
в момент создания и не восстанавливается: потерянный ключ заменяют новым.
Ключ можно отозвать (флажок «активен») или ограничить сроком (`expires_at`).

Выпустить ключ можно двумя способами:

```bash
# в командной строке
python manage.py create_api_key --name "Учебный скрипт" --scopes write,delete
python manage.py create_api_key --name "Интеграция" --scopes manage --expires-in-days 30
```

либо в админ-панели: раздел **API → API-ключи → Добавить**.

### Авторизация: скоупы

| Скоуп | Разрешает |
| --- | --- |
| `write` | POST (создание), PUT/PATCH/POST (изменение) |
| `delete` | DELETE (удаление) |
| `manage` | то же, что `write` + `delete` |

Чтение (GET, HEAD, OPTIONS) доступно всем без ключа. Дополнительно запись разрешена
сотруднику (`is_staff`), вошедшему в админ-панель, — через сессию, что удобно для
проверки в Browsable API.

Коды ответов при отказе в доступе:

* **401 Unauthorized** — ключ не передан, неизвестен, отключён или просрочен
  (в ответе есть заголовок `WWW-Authenticate: ApiKey realm="api"`);
* **403 Forbidden** — ключ действителен, но нужного скоупа не хватает
  (в теле — поясняющее сообщение);
* **404 Not Found** — ресурса с таким id нет.

### Капитализация заголовков

При создании и изменении курса или категории через API заголовок автоматически
приводится к виду «Каждое Слово С Большой Буквы» (`api/utils.py:capitalize_title`),
лишние пробелы убираются:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/courses/ \
     -H "X-API-Key: $WRITE_KEY" -H "Content-Type: application/json" \
     -d '{"title": "  deep   learning с нуля ", "price": 3200, "student_qty": 4, "category": 1}'
# -> 201 {"id": 6, "title": "Deep Learning С Нуля", "price": 3200.0, "student_qty": 4, "category": 1}
```

Капитализация выполняется в сериализаторе API, поэтому данные, добавленные через
админ-панель или оболочку, остаются нетронутыми.

### Примеры всех операций

```bash
BASE=http://127.0.0.1:8000/api/v1
WRITE_KEY=kcn_...   # ключ со скоупом write
DELETE_KEY=kcn_...  # ключ со скоупом delete

# 1. Чтение курса по id — без ключа
curl $BASE/courses/1/

# 2. Изменение и удаление курса по id — по ключу
curl -X PATCH  $BASE/courses/1/ -H "X-API-Key: $WRITE_KEY"  -H "Content-Type: application/json" -d '{"price": 1990}'
curl -X POST   $BASE/courses/1/ -H "X-API-Key: $WRITE_KEY"  -H "Content-Type: application/json" -d '{"title": "python pro"}'
curl -X DELETE $BASE/courses/1/ -H "X-API-Key: $DELETE_KEY"

# 3. Чтение категории по id — без ключа
curl $BASE/categories/1/

# 4. Изменение и удаление категории по id — по ключу
curl -X PUT    $BASE/categories/1/ -H "X-API-Key: $WRITE_KEY"  -H "Content-Type: application/json" -d '{"title": "программирование"}'
curl -X DELETE $BASE/categories/1/ -H "X-API-Key: $DELETE_KEY"

# 5. Создание курса
curl -X POST $BASE/courses/ -H "X-API-Key: $WRITE_KEY" -H "Content-Type: application/json" \
     -d '{"title": "django master", "price": 2500, "student_qty": 7, "category": 1}'

# 6. Создание категории
curl -X POST $BASE/categories/ -H "X-API-Key: $WRITE_KEY" -H "Content-Type: application/json" \
     -d '{"title": "аналитика данных"}'

# Отказ в доступе: 401 без ключа и 403 при нехватке скоупа
curl -i -X POST $BASE/courses/ -H "Content-Type: application/json" -d '{"title": "x", "price": 1, "student_qty": 1, "category": 1}'
curl -i -X DELETE $BASE/courses/1/ -H "X-API-Key: $WRITE_KEY"
```

## Админ-панель

* **Категории и курсы на одной странице.** В форму категории встроен табличный
  инлайн «Курсы категории»: курсы можно добавлять, править и удалять, не покидая
  страницу категории (`shop/admin.py`). Отдельный список всех курсов сохранён —
  он удобен для поиска, фильтра по категориям и массовых действий; в списке
  категорий показывается счётчик курсов.
* **Стиль как у сайта.** `templates/admin/base_site.html` добавляет ту же тёмную
  навигационную панель Bootstrap 5, что и на витрине, подключает `bootstrap.min.css`
  и `bootstrap.bundle.min.js`. Файл `static/css/admin_site.css` переводит палитру
  админки на цвета Bootstrap (переопределяются CSS-переменные Django) и приводит
  таблицы, кнопки, поля форм и сообщения к виду сайта: тёмная шапка таблиц, полосы,
  кнопки как `btn-primary`, поля как `form-control`, сообщения как `alert`.
* **Управление API-ключами.** Раздел **API** содержит модель `ApiKey`: список ключей
  с префиксом, скоупами, сроком действия и временем последнего использования.
  Скоупы вводятся через запятую и проверяются моделью (`clean()`), неизвестный
  скоуп не сохранится.

## Тесты

```bash
uv run pytest            # или: pytest
uv run pytest -q api/tests/test_courses_api.py
```

Настройки pytest (`DJANGO_SETTINGS_MODULE`, `pythonpath`, `testpaths`) заданы в
`pyproject.toml`. Тесты покрывают: публичное чтение, отсутствие в ответах
`reviews_qty`/`created_at`, создание и изменение по ключу, поведение POST на
детальном маршруте, скоупы и коды 401/403/404, капитализацию заголовков, выпуск
и проверку ключей (в том числе отзыв и срок действия), работу инлайна в админке
и показ значения ключа ровно один раз.

## Структура приложения `api`

```
api/
├── models.py           # ApiKey: генерация, хэш, скоупы, срок действия, проверка
├── authentication.py   # ApiKeyAuthentication — заголовки X-API-Key / Authorization
├── permissions.py      # ApiKeyScopePermission — соответствие метода и скоупа
├── serializers.py      # Category/Course: капитализация title, скрытые поля
├── routers.py          # ApiV1Router — POST на детальном маршруте
├── views.py            # CourseViewSet, CategoryViewSet
├── urls.py             # маршруты ресурсов
├── admin.py            # ApiKeyAdmin + заголовки админ-сайта
├── management/commands/create_api_key.py
└── tests/              # pytest-тесты API, модели ключа и админ-панели
```
