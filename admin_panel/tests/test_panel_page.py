"""Страница табличной панели и переключение тем."""

import re
from pathlib import Path

from django.conf import settings

from .conftest import DATA_URL, PANEL_URL, SAVE_URL

BASE_DIR = Path(settings.BASE_DIR)
ADMIN_SITE_CSS = BASE_DIR / "static" / "css" / "admin_site.css"
PANEL_CSS = BASE_DIR / "static" / "admin_panel" / "css" / "panel.css"


def css_rules(text: str):
    """Пары (селектор, тело) для каждого правила CSS без вложенности."""
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", text):
        yield match.group(1), match.group(2)


class TestPanelPage:
    """Страница доступна сотрудникам и оформлена как остальная админка."""

    def test_staff_sees_page(self, staff_client):
        response = staff_client.get(PANEL_URL)
        assert response.status_code == 200

    def test_page_contains_both_grids(self, staff_client):
        content = staff_client.get(PANEL_URL).content.decode()
        assert 'id="categories-grid"' in content
        assert 'id="courses-grid"' in content
        assert 'id="add-category"' in content
        assert 'id="add-course"' in content
        assert 'id="panel-save"' in content
        assert 'id="panel-reload"' in content

    def test_page_points_to_own_json_endpoints(self, staff_client):
        content = staff_client.get(PANEL_URL).content.decode()
        assert f'data-url-data="{DATA_URL}"' in content
        assert f'data-url-save="{SAVE_URL}"' in content

    def test_page_has_csrf_token_for_saving(self, staff_client):
        content = staff_client.get(PANEL_URL).content.decode()
        assert "csrfmiddlewaretoken" in content

    def test_grids_are_marked_with_section(self, staff_client):
        """panel.js определяет таблицу по data-section контейнера."""
        content = staff_client.get(PANEL_URL).content.decode()
        assert 'id="categories-grid" class="panel-grid"' in content
        assert 'data-section="categories"' in content
        assert 'id="courses-grid" class="panel-grid"' in content
        assert 'data-section="courses"' in content

    def test_page_loads_vendored_tabulator(self, staff_client):
        content = staff_client.get(PANEL_URL).content.decode()
        assert "vendor/tabulator/tabulator.min.js" in content
        assert "vendor/tabulator/tabulator_bootstrap5.min.css" in content
        assert "vendor/tabulator/tabulator_midnight.min.css" in content
        assert "admin_panel/css/panel.css" in content
        assert "admin_panel/js/panel.js" in content

    def test_vendored_files_exist(self):
        vendor = BASE_DIR / "static" / "vendor" / "tabulator"
        for name in (
            "tabulator.min.js",
            "tabulator_bootstrap5.min.css",
            "tabulator_midnight.min.css",
            "LICENSE",
        ):
            assert (vendor / name).is_file(), f"нет файла {name}"
        assert (BASE_DIR / "static" / "admin_panel" / "js" / "panel.js").is_file()

    def test_page_reuses_admin_layout(self, staff_client):
        content = staff_client.get(PANEL_URL).content.decode()
        assert "admin-navbar" in content
        assert "css/bootstrap.min.css" in content
        assert "Магазин Куценко В." in content

    def test_navbar_marks_panel_active(self, staff_client):
        content = staff_client.get(PANEL_URL).content.decode()
        link = re.search(r'<a class="nav-link active"[^>]*>([^<]+)</a>', content)
        assert link is not None
        assert link.group(1).strip() == "Таблицы данных"

    def test_navbar_links_panel_from_admin_index(self, staff_client):
        content = staff_client.get("/admin/").content.decode()
        assert PANEL_URL in content
        assert "Таблицы данных" in content

    def test_anonymous_is_redirected_to_login(self, anonymous_client):
        response = anonymous_client.get(PANEL_URL)
        assert response.status_code == 302
        assert response["Location"].startswith("/admin/login/")
        assert f"next={PANEL_URL}" in response["Location"]

    def test_regular_user_is_redirected_to_login(self, user_client):
        response = user_client.get(PANEL_URL)
        assert response.status_code == 302
        assert response["Location"].startswith("/admin/login/")

    def test_regular_admin_pages_still_work(self, admin_client):
        """Новая страница не сломала штатные разделы админки (суперпользователь)."""
        for url in (
            "/admin/",
            "/admin/shop/category/",
            "/admin/shop/course/",
            "/admin/api/apikey/",
        ):
            assert admin_client.get(url).status_code == 200, url


class TestThemeSwitch:
    """Штатный переключатель темы Django работает, тёмная палитра задана."""

    def test_theme_toggle_is_rendered(self, staff_client):
        content = staff_client.get(PANEL_URL).content.decode()
        assert 'class="theme-toggle"' in content
        assert "admin/js/theme.js" in content

    def test_theme_toggle_is_rendered_on_admin_pages(self, admin_client):
        content = admin_client.get("/admin/shop/category/").content.decode()
        assert 'class="theme-toggle"' in content

    def test_css_does_not_hide_theme_toggle(self):
        css = ADMIN_SITE_CSS.read_text(encoding="utf-8")
        for selector, body in css_rules(css):
            if ".theme-toggle" in selector:
                assert "display: none" not in body, selector

    def test_css_defines_dark_palette(self):
        css = ADMIN_SITE_CSS.read_text(encoding="utf-8")
        # Тёмная палитра нужна и при явном выборе темы, и в режиме auto.
        assert 'html[data-theme="dark"]' in css
        assert "prefers-color-scheme: dark" in css
        # Светлая палитра повторяет селектор Django, иначе тёмная не применится.
        assert 'html[data-theme="light"]' in css

    def test_dark_palette_redefines_brand_tokens(self):
        css = ADMIN_SITE_CSS.read_text(encoding="utf-8")
        dark = re.search(r'html\[data-theme="dark"\]\s*\{([^}]*)\}', css)
        assert dark is not None
        body = dark.group(1)
        for token in (
            "--admin-bg",
            "--admin-text",
            "--admin-border",
            "--admin-primary",
            "--body-bg",
            "--body-fg",
            "--link-fg",
            "--border-color",
        ):
            assert token in body, token

    def test_light_palette_keeps_site_brand(self):
        css = ADMIN_SITE_CSS.read_text(encoding="utf-8")
        light = re.search(r'html\[data-theme="light"\],\s*:root\s*\{([^}]*)\}', css)
        assert light is not None
        assert "#0d6efd" in light.group(1)  # фирменный синий Bootstrap
        assert "#ffffff" in light.group(1)  # светлый фон карточек

    def test_panel_css_follows_admin_tokens(self):
        css = PANEL_CSS.read_text(encoding="utf-8")
        assert "var(--admin-bg)" in css
        assert "var(--admin-border)" in css
        assert "var(--admin-table-head-bg)" in css


def test_data_endpoint_answers_json_without_login(anonymous_client):
    """Не вошедший клиент получает 403 с JSON, а не редирект на форму входа."""
    response = anonymous_client.get(DATA_URL)
    assert response.status_code == 403
    assert response["Content-Type"] == "application/json"
    assert response.json()["ok"] is False


def test_save_endpoint_answers_json_without_login(anonymous_client):
    response = anonymous_client.post(SAVE_URL, data={}, content_type="application/json")
    assert response.status_code == 403
    assert response["Content-Type"] == "application/json"
    assert response.json()["ok"] is False
