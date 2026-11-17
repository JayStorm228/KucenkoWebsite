/* Табличная панель админки: категории и курсы редактируются на месте.
 *
 * Правки копятся на клиенте (изменённые ячейки, новые и удалённые строки),
 * подсвечиваются и уходят одним пакетом по кнопке «Сохранить». Данные
 * приходят с admin_panel:data — все колонки базы, которых нет в публичном API.
 */
(function () {
    "use strict";

    var app = document.getElementById("panel-app");
    if (!app) {
        return;
    }
    if (typeof Tabulator === "undefined") {
        // Без библиотеки таблицы остались бы пустыми без объяснения причины.
        app.insertAdjacentHTML(
            "afterbegin",
            "<div class='alert alert-danger' role='alert'>Не загрузилась библиотека таблиц " +
                "(static/vendor/tabulator/tabulator.min.js). Проверьте, что сервер отдаёт " +
                "статические файлы.</div>"
        );
        return;
    }

    // Стили тем грида: оба файла в странице, включён ровно один (атрибут media).
    var themeLinks = {
        light: document.getElementById("tabulator-theme-light"),
        dark: document.getElementById("tabulator-theme-dark")
    };

    /* -------------------------------------------------------------- *
     * Разделы панели: колонки, значения по умолчанию, валидация        *
     * -------------------------------------------------------------- */

    var SECTIONS = {
        categories: {
            element: "categories-grid",
            addField: "title",
            defaults: {title: ""},
            fields: ["title"],
            columns: [
                {title: "ID", field: "id", width: 90, editable: false, formatter: idFormatter},
                {
                    title: "Название",
                    field: "title",
                    minWidth: 260,
                    editor: "input",
                    validator: withValidators([
                        validatorRequired("Укажите название категории"),
                        validatorMaxLength(255, "Не длиннее 255 символов")
                    ]),
                    cellEdited: onCellEdited
                },
                {
                    title: "Курсов",
                    field: "courses_count",
                    width: 110,
                    hozAlign: "right",
                    editable: false,
                    formatter: countFormatter,
                    headerTooltip: "Сколько курсов привязано к категории"
                },
                {
                    title: "Создана",
                    field: "created_at",
                    width: 180,
                    editable: false,
                    formatter: dateFormatter
                },
                actionsColumn(onRowDelete, "Удалить категорию вместе с её курсами")
            ]
        },
        courses: {
            element: "courses-grid",
            addField: "title",
            defaults: {title: "", price: 0, student_qty: 0, reviews_qty: 0, category: null},
            fields: ["title", "price", "student_qty", "reviews_qty", "category"],
            columns: [
                {title: "ID", field: "id", width: 90, editable: false, formatter: idFormatter},
                {
                    title: "Название",
                    field: "title",
                    minWidth: 260,
                    editor: "input",
                    validator: withValidators([
                        validatorRequired("Укажите название курса"),
                        validatorMaxLength(255, "Не длиннее 255 символов")
                    ]),
                    cellEdited: onCellEdited
                },
                {
                    title: "Цена",
                    field: "price",
                    width: 140,
                    hozAlign: "right",
                    editor: "number",
                    editorParams: {min: 0, step: "any", selectContents: true},
                    formatter: moneyFormatter,
                    validator: withValidators([validatorRequired("Укажите цену"), validatorNumber(0, null)]),
                    cellEdited: onCellEdited
                },
                {
                    title: "Студентов",
                    field: "student_qty",
                    width: 130,
                    hozAlign: "right",
                    editor: "number",
                    editorParams: {min: 0, step: 1, verticalNavigation: "editor"},
                    validator: withValidators([validatorRequired("Укажите количество"), validatorNumber(0, null)]),
                    cellEdited: onCellEdited
                },
                {
                    title: "Отзывов",
                    field: "reviews_qty",
                    width: 120,
                    hozAlign: "right",
                    editor: "number",
                    editorParams: {min: 0, step: 1, verticalNavigation: "editor"},
                    validator: withValidators([validatorRequired("Укажите количество"), validatorNumber(0, null)]),
                    cellEdited: onCellEdited
                },
                {
                    title: "Категория",
                    field: "category",
                    width: 240,
                    editor: "list",
                    editorParams: categoryListParams,
                    formatter: categoryFormatter,
                    validator: validatorRequired("Выберите категорию"),
                    cellEdited: onCellEdited
                },
                {
                    title: "Создан",
                    field: "created_at",
                    width: 180,
                    editable: false,
                    formatter: dateFormatter
                },
                actionsColumn(onRowDelete, "Удалить курс")
            ]
        }
    };

    var SECTION_ORDER = ["categories", "courses"];

    /* -------------------------------------------------------------- *
     * Состояние                                                        *
     * -------------------------------------------------------------- */

    var state = {
        grids: {},
        saved: {}, // последние данные с сервера по разделам
        changes: {}, // {section: {created: {}, updated: {}, deleted: {}}}
        categories: [], // [{id, title}] для списка категорий
        dirty: false,
        saving: false,
        lastSection: null, // где было последнее действие — туда и «Отменить шаг»
        actions: 0, // сколько действий можно отменить до ближайшей загрузки данных
        touched: false, // пользователь уже правил таблицы после последней загрузки
        filling: false // таблицы заполняются целиком (начальная загрузка)
    };

    function emptyChanges() {
        return {created: {}, updated: {}, deleted: {}};
    }

    SECTION_ORDER.forEach(function (name) {
        state.changes[name] = emptyChanges();
    });

    /* -------------------------------------------------------------- *
     * Утилиты                                                          *
     * -------------------------------------------------------------- */

    function csrfToken() {
        var input = document.querySelector("#panel-app input[name=csrfmiddlewaretoken]");
        return input ? input.value : "";
    }

    function parseJson(text, fallback) {
        try {
            return JSON.parse(text);
        } catch (error) {
            return fallback;
        }
    }

    function savedRow(name, id) {
        var rows = state.saved[name] || [];
        for (var i = 0; i < rows.length; i++) {
            if (rows[i].id === id) {
                return rows[i];
            }
        }
        return null;
    }

    function isTempRow(row) {
        return typeof row.id === "number" && row.id < 0;
    }

    function equalValues(a, b) {
        if (a === b) {
            return true;
        }
        if ((a === null || a === undefined) && (b === null || b === undefined)) {
            return true;
        }
        // Значения из базы и из редактора сравниваем как числа: 100 == "100".
        if (a !== "" && b !== "" && !isNaN(Number(a)) && !isNaN(Number(b))) {
            return Number(a) === Number(b);
        }
        return false;
    }

    function pickFields(data, fields) {
        var row = {};
        fields.forEach(function (field) {
            row[field] = data[field];
        });
        return row;
    }

    function formatDateTime(value) {
        if (!value) {
            return "";
        }
        var date = new Date(value);
        if (isNaN(date.getTime())) {
            return value;
        }
        function pad(number) {
            return number < 10 ? "0" + number : String(number);
        }
        return (
            pad(date.getDate()) + "." + pad(date.getMonth() + 1) + "." + date.getFullYear() +
            " " + pad(date.getHours()) + ":" + pad(date.getMinutes())
        );
    }

    function formatMoney(value) {
        if (value === null || value === undefined || value === "") {
            return "";
        }
        var number = Number(value);
        if (isNaN(number)) {
            return String(value);
        }
        return number.toLocaleString("ru-RU", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }) + " ₽";
    }

    function categoryTitle(id) {
        for (var i = 0; i < state.categories.length; i++) {
            if (state.categories[i].id === id) {
                return state.categories[i].title;
            }
        }
        return "";
    }

    /* -------------------------------------------------------------- *
     * Форматеры и валидаторы Tabulator                                 *
     * -------------------------------------------------------------- */

    function idFormatter(cell) {
        return isTempRow(cell.getRow().getData()) ? "<em class='text-muted'>новая</em>" : cell.getValue();
    }

    function countFormatter(cell) {
        var value = Number(cell.getValue()) || 0;
        return value > 0 ? String(value) : "<span class='text-muted'>0</span>";
    }

    function dateFormatter(cell) {
        var value = formatDateTime(cell.getValue());
        return value || "<span class='text-muted'>—</span>";
    }

    function moneyFormatter(cell) {
        var value = cell.getValue();
        return value === null || value === undefined || value === ""
            ? "<span class='text-muted'>—</span>"
            : formatMoney(value);
    }

    function categoryFormatter(cell) {
        var value = cell.getValue();
        var title = value === null || value === undefined || value === ""
            ? ""
            : categoryTitle(value);
        return title || "<span class='text-muted'>не выбрана</span>";
    }

    /**
     * Сброс подсветки ошибки первым валидатором цепочки: иначе следующий
     * успешный валидатор снял бы ошибку, поставленную предыдущим.
     */
    function validatorReset(cell) {
        clearCellError(cell);
        return true;
    }

    function withValidators(validators) {
        return [validatorReset].concat(validators);
    }

    function validatorRequired(message) {
        return function (cell, value) {
            if (value === null || value === undefined || String(value).trim() === "") {
                setCellError(cell, message);
                return false;
            }
            return true;
        };
    }

    function validatorNumber(min, max) {
        return function (cell, value) {
            if (value === null || value === undefined || value === "") {
                return true; // пустое значение ловит validatorRequired
            }
            var number = Number(value);
            if (isNaN(number)) {
                setCellError(cell, "Нужно число");
                return false;
            }
            if (min !== null && number < min) {
                setCellError(cell, "Не меньше " + min);
                return false;
            }
            if (max !== null && number > max) {
                setCellError(cell, "Не больше " + max);
                return false;
            }
            return true;
        };
    }

    function validatorMaxLength(maxLength, message) {
        return function (cell, value) {
            if (value && String(value).length > maxLength) {
                setCellError(cell, message);
                return false;
            }
            return true;
        };
    }

    function setCellError(cell, message) {
        if (!cell || !cell.getElement) {
            return;
        }
        var element = cell.getElement();
        element.classList.add("cell-error");
        element.setAttribute("title", message || "Проверьте значение");
    }

    function clearCellError(cell) {
        if (!cell || !cell.getElement) {
            return;
        }
        var element = cell.getElement();
        element.classList.remove("cell-error");
        element.removeAttribute("title");
    }

    /* -------------------------------------------------------------- *
     * Список категорий для колонки Course.category                     *
     * -------------------------------------------------------------- */

    // Именно valuesLookup, а не values: в Tabulator 6 функция в values не
    // вызывается (список получается пустым), а valuesLookup пересчитывается
    // при каждом открытии редактора — свежие категории попадают в список сами.
    function categoryListParams() {
        return {
            valuesLookup: function () {
                return state.categories.map(function (category) {
                    return {label: category.title, value: category.id};
                });
            },
            placeholderEmpty: "Нет категорий — сначала добавьте категорию"
        };
    }

    function refreshCategories() {
        var categories = [];
        var deletedCategories = state.changes.categories.deleted;
        state.grids.categories.getData().forEach(function (row) {
            if (deletedCategories[row.id]) {
                return;
            }
            categories.push({id: row.id, title: row.title});
        });
        // Новые категории (отрицательные id) — в конец списка.
        categories.sort(function (a, b) {
            var aNew = a.id < 0;
            var bNew = b.id < 0;
            if (aNew !== bNew) {
                return aNew ? 1 : -1;
            }
            return a.id - b.id;
        });
        state.categories = categories;

        // Названия категорий показаны форматером — перерисовываем курсы.
        // При начальном заполнении это лишнее: курсы заполнятся следом и возьмут
        // свежий список сами.
        var courses = state.grids.courses;
        if (!state.filling && courses && courses._built) {
            courses._built.then(function () {
                courses.getRows().forEach(function (row) {
                    row.reformat();
                });
            });
        }
    }

    /** Заполнить таблицы по порядку: сначала категории, потом курсы. */
    function fillSections(getRows) {
        state.filling = true;
        return SECTION_ORDER.reduce(function (chain, name) {
            return chain.then(function () {
                return setData(name, getRows(name));
            });
        }, Promise.resolve()).then(function () {
            state.filling = false;
        });
    }

    /* -------------------------------------------------------------- *
     * Подсветка строк и пересчёт пакета изменений                       *
     * -------------------------------------------------------------- */

    function markNewRow(row, section) {
        var element = row.getElement();
        if (element) {
            element.classList.add("row-new");
        }
        section.fields.forEach(function (field) {
            var cell = row.getCell(field);
            if (cell) {
                cell.getElement().classList.add("cell-edited");
            }
        });
    }

    function refreshRowState(name, row) {
        var section = SECTIONS[name];
        var data = row.getData();
        if (isTempRow(data)) {
            markNewRow(row, section);
            return;
        }
        var element = row.getElement();
        if (element) {
            element.classList.remove("row-new");
        }
        var saved = savedRow(name, data.id);
        var changed = false;
        section.fields.forEach(function (field) {
            var cell = row.getCell(field);
            if (!cell) {
                return;
            }
            var isChanged = saved === null || !equalValues(saved[field], data[field]);
            cell.getElement().classList.toggle("cell-edited", isChanged);
            changed = changed || isChanged;
        });
        if (changed) {
            state.changes[name].updated[data.id] = pickFields(data, section.fields);
        } else {
            delete state.changes[name].updated[data.id];
        }
    }

    /** Имя раздела по элементу таблицы: data-section на контейнере грида. */
    function sectionOf(element) {
        var grid = element && element.closest ? element.closest("[data-section]") : null;
        return grid ? grid.getAttribute("data-section") : null;
    }

    function onCellEdited(cell) {
        var name = sectionOf(cell.getElement());
        var row = cell.getRow();
        var data = row.getData();

        state.lastSection = name;
        state.actions += 1;
        state.touched = true;
        // Правка прошла валидацию таблицы — снимаем отметку об ошибке.
        clearCellError(cell);
        if (isTempRow(data)) {
            state.changes[name].created[data.id] = pickFields(data, SECTIONS[name].fields);
        }
        refreshRowState(name, row);
        if (name === "categories") {
            refreshCategories();
        }
        updateToolbar();
    }

    /** Пересобрать пакет изменений по текущему содержимому таблиц. */
    function rebuildChanges() {
        SECTION_ORDER.forEach(function (name) {
            var table = state.grids[name];
            var section = SECTIONS[name];
            var changes = emptyChanges();
            var present = {};

            table.getData().forEach(function (data) {
                present[data.id] = true;
                if (isTempRow(data)) {
                    changes.created[data.id] = pickFields(data, section.fields);
                    return;
                }
                var saved = savedRow(name, data.id);
                if (saved === null) {
                    return;
                }
                var changed = section.fields.some(function (field) {
                    return !equalValues(saved[field], data[field]);
                });
                if (changed) {
                    changes.updated[data.id] = pickFields(data, section.fields);
                }
            });

            (state.saved[name] || []).forEach(function (saved) {
                if (!present[saved.id]) {
                    changes.deleted[saved.id] = {title: saved.title};
                }
            });

            state.changes[name] = changes;
            table.getRows().forEach(function (row) {
                refreshRowState(name, row);
            });
        });
        refreshCategories();
        updateToolbar();
    }

    /* -------------------------------------------------------------- *
     * Удаление строки                                                  *
     * -------------------------------------------------------------- */

    function actionsColumn(handler, tooltip) {
        return {
            title: "",
            field: "actions",
            width: 70,
            hozAlign: "center",
            headerSort: false,
            editable: false,
            cellClick: function (event, cell) {
                event.preventDefault();
                event.stopPropagation();
                handler(cell.getRow());
            },
            formatter: function () {
                return (
                    "<div class='cell-actions'>" +
                    "<button type='button' class='btn btn-sm btn-outline-danger' title='" +
                    tooltip + "'>✕</button></div>"
                );
            }
        };
    }

    function onRowDelete(row) {
        var name = sectionOf(row.getElement());
        var table = state.grids[name];
        var data = row.getData();
        var changes = state.changes[name];
        var message;

        if (name === "categories") {
            var courses = 0;
            state.grids.courses.getData().forEach(function (course) {
                if (!state.changes.courses.deleted[course.id] && course.category === data.id) {
                    courses += 1;
                }
            });
            message = courses > 0
                ? "Удалить категорию «" + data.title + "»? Вместе с ней будут удалены её курсы: " +
                  courses + " шт."
                : "Удалить категорию «" + data.title + "»?";
        } else {
            message = "Удалить курс «" + data.title + "»?";
        }

        if (!window.confirm(message)) {
            return;
        }

        if (!isTempRow(data)) {
            changes.deleted[data.id] = {title: data.title};
        }
        state.lastSection = name;
        state.actions += 1;
        state.touched = true;
        table.deleteRow(row);
        rebuildChanges();
        showAlert("warning", "Строка помечена к удалению — изменения применятся после сохранения.");
    }

    /* -------------------------------------------------------------- *
     * Добавление строки                                                *
     * -------------------------------------------------------------- */

    function addRow(name) {
        var table = state.grids[name];
        var section = SECTIONS[name];
        if (!table || state.saving) {
            return;
        }
        var data = {id: table._nextTempId};
        table._nextTempId -= 1;
        Object.keys(section.defaults).forEach(function (field) {
            data[field] = section.defaults[field];
        });

        table.clearFilter();
        table.addRow(data, true);
        state.lastSection = name;
        state.actions += 1;
        state.touched = true;

        var added = null;
        table.getRows().forEach(function (candidate) {
            if (candidate.getData().id === data.id) {
                added = candidate;
            }
        });
        if (added) {
            added.reformat();
            markNewRow(added, section);
            state.changes[name].created[data.id] = pickFields(data, section.fields);
            if (name === "categories") {
                refreshCategories();
            }
            var cell = added.getCell(section.addField);
            if (cell) {
                cell.edit(true);
            }
        }
        updateToolbar();
    }

    /* -------------------------------------------------------------- *
     * Сборка таблиц и загрузка данных                                  *
     * -------------------------------------------------------------- */

    function buildTable(name) {
        var section = SECTIONS[name];
        var table = new Tabulator("#" + section.element, {
            data: [],
            layout: "fitDataStretch",
            maxHeight: 600,
            placeholder: "Нет записей — добавьте первую",
            selectableRows: 1,
            history: true,
            columnDefaults: {
                resizable: true,
                headerSort: true,
                headerSortTristate: true,
                tooltip: true
            },
            columns: section.columns
        });
        table._nextTempId = -1;
        // Методы заполнения и перерисовки работают только после tableBuilt:
        // до него внутренние структуры таблицы (в том числе рендерер строк)
        // ещё не созданы, и вызов setData() падает, оставляя таблицу пустой.
        table._built = new Promise(function (resolve) {
            table.on("tableBuilt", resolve);
        });
        state.grids[name] = table;
        return table;
    }

    /* Строки должны появиться сразу вместе с данными. Если таблица измерила
     * нулевую высоту (стили, шрифты или размеры контейнера ещё не готовы),
     * виртуальный рендер не рисует ничего, хотя данные уже загружены — тогда
     * перерисовку повторяем, пока строки не появятся. */
    var RENDER_RETRIES = 6;
    var RENDER_RETRY_DELAY = 120;

    /** Сколько строк с данными реально отрисовано в таблице. */
    function renderedRows(table) {
        if (!table || !table.element) {
            return 0;
        }
        // Строка-заглушка «No Data» тоже имеет класс tabulator-row.
        return table.element.querySelectorAll(".tabulator-row:not(.tabulator-placeholder)").length;
    }

    function ensureRowsRendered(name, attempt) {
        var table = state.grids[name];
        var tries = attempt || 0;
        if (!table || !table.initialized || tries >= RENDER_RETRIES) {
            return;
        }
        if (renderedRows(table) > 0 || table.getDataCount() === 0) {
            return;
        }
        window.setTimeout(function () {
            table.redraw(true);
            ensureRowsRendered(name, tries + 1);
        }, RENDER_RETRY_DELAY * (tries + 1));
    }

    function setData(name, rows) {
        var table = state.grids[name];
        var source = rows || [];
        // Таблица правит полученные объекты на месте, поэтому эталон для
        // сравнения «изменилось ли» храним отдельными копиями строк.
        state.saved[name] = source.map(function (row) {
            return Object.assign({}, row);
        });
        state.changes[name] = emptyChanges();
        state.actions = 0;
        state.touched = false;
        state.lastSection = null;
        var done = table._built.then(function () {
            return table.setData(source);
        }).then(function () {
            // Перерисовка после заполнения: к этому моменту стили и шрифты
            // уже применены, и строки получают настоящую высоту.
            table.redraw(true);
            ensureRowsRendered(name);
            table.getRows().forEach(function (row) {
                refreshRowState(name, row);
            });
            // Список категорий строится из данных таблицы, поэтому обновляем
            // его уже после заполнения, а не до.
            if (name === "categories") {
                refreshCategories();
            }
            updateCounts();
        });
        return done;
    }

    function updateCounts() {
        SECTION_ORDER.forEach(function (name) {
            var element = document.getElementById(name + "-count");
            if (element) {
                element.textContent = "— записей: " + state.grids[name].getData().length;
            }
        });
    }

    /* -------------------------------------------------------------- *
     * Панель инструментов                                              *
     * -------------------------------------------------------------- */

    function changeCount() {
        var total = 0;
        SECTION_ORDER.forEach(function (name) {
            var changes = state.changes[name];
            total += Object.keys(changes.created).length;
            total += Object.keys(changes.updated).length;
            total += Object.keys(changes.deleted).length;
        });
        return total;
    }

    function updateToolbar() {
        var count = changeCount();
        state.dirty = count > 0;
        var badge = document.getElementById("panel-changes-count");
        var saveButton = document.getElementById("panel-save");
        var undoButton = document.getElementById("panel-undo");
        if (badge) {
            badge.textContent = count > 0
                ? "Несохранённых изменений: " + count
                : "Нет несохранённых изменений";
            badge.className = "badge " + (count > 0 ? "text-bg-warning" : "text-bg-secondary");
        }
        if (saveButton) {
            saveButton.disabled = !state.dirty || state.saving;
        }
        if (undoButton) {
            undoButton.disabled = state.saving || state.actions === 0;
        }
        updateCounts();
    }

    /* -------------------------------------------------------------- *
     * Сообщения                                                        *
     * -------------------------------------------------------------- */

    var ALERT_VARIANTS = {
        success: "success",
        error: "danger",
        warning: "warning",
        info: "info"
    };

    function showAlert(kind, message) {
        var container = document.getElementById("panel-alerts");
        if (!container) {
            return;
        }
        var alert = document.createElement("div");
        alert.className = "alert alert-" + (ALERT_VARIANTS[kind] || "secondary") + " alert-dismissible fade show";
        alert.setAttribute("role", "alert");

        var body = document.createElement("div");
        body.textContent = message;

        var close = document.createElement("button");
        close.type = "button";
        close.className = "btn-close";
        close.setAttribute("aria-label", "Закрыть");
        close.addEventListener("click", function () {
            alert.remove();
        });

        alert.appendChild(body);
        alert.appendChild(close);
        container.appendChild(alert);
        if (kind !== "error") {
            window.setTimeout(function () {
                if (alert.isConnected) {
                    alert.remove();
                }
            }, 6000);
        }
    }

    function applyServerErrors(payload) {
        var errors = payload.errors || {};
        SECTION_ORDER.forEach(function (name) {
            var table = state.grids[name];
            var sectionErrors = errors[name] || {};
            Object.keys(sectionErrors).forEach(function (key) {
                var id = Number(key);
                var row = null;
                table.getRows().forEach(function (candidate) {
                    if (candidate.getData().id === id) {
                        row = candidate;
                    }
                });
                if (!row) {
                    return;
                }
                row.reformat();
                var messages = [];
                Object.keys(sectionErrors[key]).forEach(function (field) {
                    var list = sectionErrors[key][field];
                    var text = Array.isArray(list) ? list.join(" ") : String(list);
                    messages.push(field + ": " + text);
                    var cell = row.getCell(field);
                    if (cell) {
                        setCellError(cell, text);
                    }
                });
                var element = row.getElement();
                if (element) {
                    element.setAttribute("title", messages.join("; "));
                }
            });
        });
    }

    /* -------------------------------------------------------------- *
     * Обмен с сервером                                                 *
     * -------------------------------------------------------------- */

    function buildPayload() {
        var payload = {};
        SECTION_ORDER.forEach(function (name) {
            var changes = state.changes[name];
            payload[name] = {
                created: Object.keys(changes.created).map(function (key) {
                    return Object.assign({temp_id: Number(key)}, changes.created[key]);
                }),
                updated: Object.keys(changes.updated).map(function (key) {
                    return Object.assign({id: Number(key)}, changes.updated[key]);
                }),
                deleted: Object.keys(changes.deleted).map(function (key) {
                    return Number(key);
                })
            };
        });
        return payload;
    }

    function request(url, options) {
        return fetch(url, options).then(function (response) {
            return response.text().then(function (text) {
                return {status: response.status, ok: response.ok, body: parseJson(text, null)};
            });
        });
    }

    /**
     * Запись данных, отданная страницей сразу (json_script в шаблоне).
     * С ней таблицы заполняются с первым кадром, без ожидания запроса к API.
     */
    function readEmbeddedData() {
        var node = document.getElementById("panel-initial-data");
        if (!node) {
            return null;
        }
        try {
            var parsed = JSON.parse(node.textContent);
            return parsed && typeof parsed === "object" ? parsed : null;
        } catch (error) {
            return null;
        }
    }

    /** Совпадают ли свежие данные с уже показанными (чтобы не дёргать таблицы). */
    function sameAsRendered(data) {
        return SECTION_ORDER.every(function (name) {
            return JSON.stringify(data[name] || []) === JSON.stringify(state.saved[name] || []);
        });
    }

    function showEmbeddedData() {
        var embedded = readEmbeddedData();
        if (!embedded) {
            return null;
        }
        return fillSections(function (name) {
            return embedded[name];
        });
    }

    /**
     * Запрос данных к API.
     * @param {object} options ifFresh — не трогать таблицы, пока показанные
     *     данные актуальны или пользователь уже начал править; quiet — не
     *     показывать ошибку как блокирующую (данные на экране уже есть).
     */
    function loadData(options) {
        var settings = options || {};
        return request(app.dataset.urlData, {headers: {"X-Requested-With": "XMLHttpRequest"}})
            .then(function (response) {
                if (!response.ok || !response.body || !response.body.ok) {
                    throw new Error(
                        (response.body && response.body.detail) || "Не удалось загрузить данные"
                    );
                }
                // Фоновая сверка не должна перетирать историю правок: применяем
                // её, только пока пользователь ничего не сделал и данные изменились.
                if (
                    settings.ifFresh &&
                    (state.touched || state.dirty || sameAsRendered(response.body.data))
                ) {
                    return;
                }
                return fillSections(function (name) {
                    return response.body.data[name];
                }).then(updateToolbar);
            })
            .catch(function (error) {
                if (settings.quiet) {
                    showAlert("warning", "Не удалось проверить обновления данных: " + error.message);
                    return;
                }
                showAlert("error", error.message);
            });
    }

    function saveChanges() {
        if (state.saving || !state.dirty) {
            return;
        }
        state.saving = true;
        updateToolbar();
        request(app.dataset.urlSave, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken(),
                "X-Requested-With": "XMLHttpRequest"
            },
            body: JSON.stringify(buildPayload())
        })
            .then(function (response) {
                if (response.ok && response.body && response.body.ok) {
                    SECTION_ORDER.forEach(function (name) {
                        setData(name, response.body.data[name]);
                    });
                    updateToolbar();
                    showAlert("success", "Сохранено. " + summarize(response.body.summary));
                } else if (response.body && response.body.errors) {
                    applyServerErrors(response.body);
                    showAlert("error", response.body.detail || "Изменения не сохранены.");
                } else {
                    var detail = (response.body && response.body.detail) ||
                        "Сервер отклонил изменения (HTTP " + response.status + ").";
                    loadData();
                    showAlert("error", detail);
                }
            })
            .catch(function (error) {
                showAlert("error", "Ошибка сохранения: " + error.message);
            })
            .finally(function () {
                state.saving = false;
                updateToolbar();
            });
    }

    function summarize(summary) {
        summary = summary || {};
        var parts = [];
        if (summary.created) {
            parts.push("добавлено: " + summary.created);
        }
        if (summary.updated) {
            parts.push("изменено: " + summary.updated);
        }
        if (summary.deleted) {
            parts.push("удалено: " + summary.deleted);
        }
        return parts.length ? parts.join(", ") + "." : "Изменений не было.";
    }

    function revertChanges() {
        if (state.saving) {
            return;
        }
        if (
            state.dirty &&
            !window.confirm("Отменить все несохранённые изменения и вернуть таблицы к данным базы?")
        ) {
            return;
        }
        loadData();
    }

    /** Отменить последнее действие в той таблице, где его сделали. */
    function undoLastStep() {
        var name = state.lastSection;
        if (state.saving || !name || state.actions === 0) {
            return;
        }
        var table = state.grids[name];
        state.touched = true;
        if (table && table.undo()) {
            state.actions -= 1;
        } else {
            state.actions = 0; // истории таблицы больше нет
        }
        rebuildChanges();
    }

    /* -------------------------------------------------------------- *
     * Темы: грид переключается вместе с админкой                        *
     * -------------------------------------------------------------- */

    // Текущая тема; совпадает с фактической при старте, чтобы первый вызов
    // applyGridTheme() (до построения таблиц) не дёргал redraw().
    var appliedDark = effectiveDark();

    function effectiveDark() {
        var theme = document.documentElement.getAttribute("data-theme") || "auto";
        if (theme === "dark") {
            return true;
        }
        if (theme === "light") {
            return false;
        }
        return Boolean(window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
    }

    /** Перерисовать таблицы: стили или размеры могли измениться. */
    function redrawGrids() {
        SECTION_ORDER.forEach(function (name) {
            var table = state.grids[name];
            // До tableBuilt вызов redraw() бессмысленен и ломает сборку таблицы.
            if (table && table._built) {
                table._built.then(function () {
                    if (!table.initialized) {
                        return;
                    }
                    table.redraw(true);
                    ensureRowsRendered(name);
                });
            }
        });
    }

    function applyGridTheme() {
        if (!themeLinks.light || !themeLinks.dark) {
            return;
        }
        var dark = effectiveDark();
        // Bootstrap-компоненты панели (карточки, кнопки, бейджи, алерты)
        // переключаются своим атрибутом, на остальную админку он не влияет.
        app.setAttribute("data-bs-theme", dark ? "dark" : "light");

        // Оба файла тем уже в странице, переключение атрибутом media мгновенное.
        // Подмена href так не работает: старый стиль отключается сразу, новый
        // приходит по сети позже, и таблица остаётся без CSS — в этот момент
        // Tabulator измеряет нулевую высоту и не рисует строки, хотя данные
        // уже загружены.
        if (!dark) {
            themeLinks.dark.media = "print";
            themeLinks.light.media = "all";
        } else {
            // Тёмная тема подключена позже светлой и перекрывает её, поэтому
            // светлую отключаем только когда тёмная точно загружена (link.sheet).
            themeLinks.dark.media = "all";
            if (themeLinks.dark.sheet) {
                themeLinks.light.media = "print";
            } else {
                themeLinks.dark.addEventListener(
                    "load",
                    function () {
                        themeLinks.light.media = "print";
                        redrawGrids();
                    },
                    {once: true}
                );
            }
        }

        if (appliedDark !== dark) {
            appliedDark = dark;
            redrawGrids();
        }
    }

    /* -------------------------------------------------------------- *
     * Запуск                                                           *
     * -------------------------------------------------------------- */

    SECTION_ORDER.forEach(buildTable);

    document.getElementById("add-category").addEventListener("click", function () {
        addRow("categories");
    });
    document.getElementById("add-course").addEventListener("click", function () {
        addRow("courses");
    });
    document.getElementById("panel-save").addEventListener("click", saveChanges);
    document.getElementById("panel-reload").addEventListener("click", revertChanges);
    document.getElementById("panel-undo").addEventListener("click", undoLastStep);

    document.addEventListener("keydown", function (event) {
        if (!(event.ctrlKey || event.metaKey)) {
            return;
        }
        var key = event.key.toLowerCase();
        if (key === "s") {
            event.preventDefault();
            saveChanges();
        } else if (key === "z" && !event.shiftKey) {
            event.preventDefault();
            undoLastStep();
        }
    });

    window.addEventListener("beforeunload", function (event) {
        if (state.dirty) {
            event.preventDefault();
            event.returnValue = "";
        }
    });

    applyGridTheme();
    // Если тема доехала по сети позже таблиц — перерисовываем по факту загрузки.
    [themeLinks.light, themeLinks.dark].forEach(function (link) {
        if (link) {
            link.addEventListener("load", redrawGrids);
        }
    });
    // То же на случай шрифтов и прочих ресурсов, догрузившихся после таблиц.
    window.addEventListener("load", redrawGrids);
    new MutationObserver(applyGridTheme).observe(document.documentElement, {
        attributes: true,
        attributeFilter: ["data-theme"]
    });
    if (window.matchMedia) {
        window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", applyGridTheme);
    }

    // Сначала показываем записи, которые пришли вместе со страницей, затем
    // фоном сверяемся с базой: если там что-то изменилось и правок ещё нет,
    // таблицы обновятся сами.
    var shown = showEmbeddedData();
    if (shown) {
        shown.then(function () {
            updateToolbar();
            loadData({ifFresh: true, quiet: true});
        });
    } else {
        loadData();
    }
    updateToolbar();
})();
