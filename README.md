# Магазин Куценко В.

Учебный проект на Django: витрина курсов, REST API версии v1 на Django REST Framework,
админ-панель в стиле сайта и табличный интерфейс для правки данных прямо в таблицах.

## Состав

| Что | Где |
| --- | --- |
| Витрина курсов | приложение `shop`, маршруты `/` и `/shop/` |
| API v1 | приложение `api`, маршруты `/api/v1/` |
| Админ-панель | `/admin/`, оформление — `templates/admin/base_site.html` и `static/css/admin_site.css` |
| Табличная панель | приложение `admin_panel`, страница `/admin/panel/` (категории и курсы как в базе) |

Приложение `shop` продолжает работать как раньше: правки коснулись только файла
`shop/admin.py` (настройка панели администратора), а также подключения API и панели
в `config/settings.py` (`INSTALLED_APPS`, `REST_FRAMEWORK`, `DEBUG`) и `config/urls.py`
(маршруты `api/v1/` и `admin/panel/`). Модели, представления и адреса `shop` не изменялись.

## Запуск

```bash
uv sync                                   # зависимости из pyproject.toml / uv.lock
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Статические файлы

Проект учебный и в продакшен не выкладывается, поэтому в `config/settings.py` стоит
`DEBUG = True`: `runserver` сам раздаёт файлы из `static/` и из приложений — ни
`collectstatic`, ни флаг `--insecure` не нужны. `ALLOWED_HOSTS` при этом оставлен
как есть (`localhost`, `127.0.0.1`), то есть сайт открывается только с локальной машины.

Если когда-нибудь понадобится режим `DEBUG = False`, статика перестанет отдаваться
(страницы отвечают 200, а `/static/...` — 404). Тогда помогает одно из двух:

```bash
# локально — отдавать статику силами runserver даже при DEBUG=False
python manage.py runserver --insecure

# для развёртывания — собрать статику в STATIC_ROOT и отдавать её веб-сервером
python manage.py collectstatic        # -> staticfiles/ (каталог в .gitignore)
```

Откуда берутся файлы стилей и скриптов:

| Файл | Где | Зачем |
| --- | --- | --- |
| `static/css/admin_site.css` | проект | палитра и вид панели в стиле сайта, светлая и тёмная темы |
| `static/css/bootstrap.min.css`, `static/js/bootstrap.bundle.min.js` | проект | навигационная панель и сетка Bootstrap 5.3 |
| `static/vendor/tabulator/` | проект (вендоринг) | таблицы табличной панели: `tabulator.min.js` и темы `bootstrap5` / `midnight` |
| `static/admin_panel/` | проект | стили и скрипт табличной панели |
| `static/admin/**` | пакет `django.contrib.admin` | служебные стили и скрипты самой админки, включая `theme.js` |

Копировать в папку `static/` файлы админки (`admin/css/base.css`, `dark_mode.css`,
`nav_sidebar.css`, `dashboard.css`, `responsive.css`, `admin/js/theme.js`,
`admin/js/nav_sidebar.js`) **не нужно**: их отдаёт приложение `django.contrib.admin`
через `AppDirectoriesFinder`.

**Tabulator** (v6.7.1, лицензия MIT, без зависимостей) положен в репозиторий целиком —
четыре файла в `static/vendor/tabulator/`. Проект не собирается в продакшен, поэтому
вендоринг выбран вместо сборки через npm: панели не нужны ни `node_modules`, ни сборщик,
файлы отдаются как обычная статика. Лицензионный текст лежит рядом, в `LICENSE`.

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
* **Табличный интерфейс `/admin/panel/`** — категории и курсы как таблицы в БД-приложении:
  правка ячеек на месте, добавление и удаление строк, сохранение пакетом. Подробнее —
  в разделе ниже.
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

### Табличная панель `/admin/panel/`

Страница для сотрудников (`is_staff`), ссылка «Таблицы данных» в навигационной панели
админки. Обе таблицы — категории и курсы — показывают **все колонки базы**, их можно
смотреть, сортировать, править, добавлять и удалять строки, не открывая отдельные формы.

| Колонки | Редактируются | Только чтение |
| --- | --- | --- |
| Категории | `title` | `id`, `courses_count`, `created_at` |
| Курсы | `title`, `price`, `student_qty`, `reviews_qty`, `category` | `id`, `created_at` |

Как это работает:

* **Правка на месте.** Клик по ячейке открывает редактор: текст для названий, число
  для цены и счётчиков, выпадающий список для категории. Значения проверяются сразу —
  пустое название или отрицательная цена подсвечиваются красным и не фиксируются.
* **Явные изменения.** Изменённые ячейки подсвечены жёлтым, новые строки помечены
  целиком, счётчик несохранённых изменений виден в панели инструментов.
* **Сохранение пакетом.** Кнопка **Сохранить** (или `Ctrl+S`) отправляет все изменения
  одним запросом. Кнопка **Отменить изменения** возвращает таблицы к данным базы,
  **Отменить шаг** (или `Ctrl+Z`) отменяет последнее действие в таблице.
* **Удаление категории** запрашивает подтверждение и сразу сообщает, сколько курсов
  будет удалено вместе с ней (`Course.category` объявлен с `on_delete=CASCADE`).
* **Ошибки сервера** возвращаются построчно: проблемные ячейки подсвечиваются, а
  изменения не применяются вовсе — сохранение идёт одной транзакцией.

Отличия от публичного API v1 (это намеренно):

| | API v1 | Табличная панель |
| --- | --- | --- |
| `reviews_qty`, `created_at` у курса | скрыты | видны, `reviews_qty` редактируется |
| Заголовки | приводятся к Title Case | сохраняются как введены |
| Доступ | API-ключ со скоупом или сессия сотрудника | только сессия сотрудника |

Свои JSON-эндпоинты панели (доступны только сотрудникам, ключи API v1 здесь не работают):

```bash
# все данные обеих таблиц одним ответом
curl -b cookies.txt http://127.0.0.1:8000/admin/panel/api/data/
# -> {"ok": true, "data": {"categories": [...], "courses": [...]}}

# пакетное сохранение: создание, правка и удаление
curl -b cookies.txt -X POST http://127.0.0.1:8000/admin/panel/api/save/ \
  -H "Content-Type: application/json" -H "X-CSRFToken: $CSRF" -d '{
    "categories": {"created": [{"temp_id": -1, "title": "Аналитика"}],
                   "updated": [{"id": 2, "title": "Дизайн интерфейсов"}],
                   "deleted": [3]},
    "courses":    {"created": [{"temp_id": -2, "title": "SQL", "price": 1200,
                                "student_qty": 0, "reviews_qty": 0, "category": -1}],
                   "updated": [{"id": 1, "title": "Python Basic", "price": 1500,
                                "student_qty": 12, "reviews_qty": 7, "category": 1}],
                   "deleted": [5]}
  }'
# -> {"ok": true, "summary": {"created": 2, "updated": 2, "deleted": 2}, "data": {...}}
```

Правила пакета:

* строки `created` несут `temp_id` (любое отрицательное число) и все редактируемые поля;
* строки `updated` несут `id` и все редактируемые поля;
* `deleted` — список `id`;
* курс может ссылаться на категорию, созданную в том же пакете, по её `temp_id`;
* порядок применения: создание и правка категорий → создание и правка курсов →
  удаление курсов → удаление категорий;
* `id` и `created_at` в пакете игнорируются, лишние поля отбрасываются;
* при любой ошибке валидации ответ `400` с разбором `errors: {раздел: {строка: {поле: [сообщения]}}}`,
  и не сохраняется ничего.

Внутри приложения:

```
admin_panel/
├── views.py       # страница + два JSON-эндпоинта, доступ только для is_staff
├── services.py    # данные таблиц, разбор пакета, валидация, транзакция
├── forms.py       # CategoryForm / CourseForm — поля строки таблицы
├── urls.py        # /admin/panel/, api/data/, api/save/
├── templates/admin_panel/panel.html
└── tests/         # 76 pytest-тестов страницы, чтения и сохранения

static/admin_panel/js/panel.js    # таблицы Tabulator, правки, подсветка, сохранение
static/admin_panel/css/panel.css  # оформление таблиц на токенах админки
static/vendor/tabulator/          # Tabulator 6.7.1 (MIT) + темы bootstrap5 и midnight
```

### Тёмная и светлая темы

Штатный переключатель Django в шапке админки (кнопка рядом с именем пользователя)
возвращён: он перебирает **авто → тёмная → светлая**, пишет выбор в `localStorage`
и применяет его до отрисовки страницы (`admin/js/theme.js`).

* `static/css/admin_site.css` задаёт фирменную палитру токенами `--admin-*` и
  переопределяет переменные Django в трёх селекторах: `html[data-theme="light"], :root`
  (светлая), `html:not([data-theme="light"])` внутри `@media (prefers-color-scheme: dark)`
  (авто при тёмной теме системы) и `html[data-theme="dark"]` (явный выбор). Тёмная
  палитра — та же синяя гамма Bootstrap, но на тёмном фоне.
* Таблицы панели следят за `data-theme` через `MutationObserver` и подменяют тему
  Tabulator: `tabulator_bootstrap5.min.css` в светлой и `tabulator_midnight.min.css`
  в тёмной. Bootstrap-компоненты страницы (карточки, кнопки, бейджи, сообщения)
  переключаются атрибутом `data-bs-theme` на контейнере панели.
* Темы действуют **только в админке** (`/admin/`, включая `/admin/panel/`): витрина
  `/shop/` и главная страница остаются светлыми, как и были.

## Тесты

```bash
uv run pytest            # или: pytest
uv run pytest -q admin_panel          # только табличная панель
uv run pytest -q api/tests/test_courses_api.py
```

Настройки pytest (`DJANGO_SETTINGS_MODULE`, `pythonpath`, `testpaths`) заданы в
`pyproject.toml`. Всего **170 тестов**:

* API v1 — публичное чтение, отсутствие в ответах `reviews_qty`/`created_at`, создание
  и изменение по ключу, поведение POST на детальном маршруте, маршруты без завершающего
  слэша, скоупы и коды 401/403/404, капитализация заголовков, выпуск и проверка ключей
  (в том числе отзыв и срок действия);
* админка Django — работа инлайна курсов в форме категории и показ значения ключа
  ровно один раз;
* табличная панель — доступ (сотрудник, обычный пользователь, ключ API, CSRF), состав
  колонок и сырые значения без капитализации, создание/правка/удаление, временные id
  категорий, каскадное удаление, валидация и атомарность пакета, переключение тем и
  наличие штатного переключателя.

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
