"""Тесты модели ApiKey: выпуск ключа, проверка, скоупы, срок действия."""

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from api.models import ApiKey, generate_key, hash_key, parse_prefix

pytestmark = pytest.mark.django_db


class TestKeyGeneration:
    def test_key_has_prefix_and_secret(self):
        raw_key, prefix = generate_key()
        assert raw_key.startswith(f"kcn_{prefix}_")
        assert len(prefix) == 8

    def test_parse_prefix_roundtrip(self):
        raw_key, prefix = generate_key()
        assert parse_prefix(raw_key) == prefix

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "abc",
            "kcn_",
            "kcn__secret",
            "kcn_deadbeef_",
            "wrong_deadbeef_secret",
        ],
    )
    def test_parse_prefix_rejects_invalid_values(self, value):
        assert parse_prefix(value) is None

    def test_parse_prefix_keeps_underscores_inside_secret(self):
        """Секрет от token_urlsafe может содержать «_» — это не ломает разбор."""
        assert parse_prefix("kcn_deadbeef_secret_with_underscores") == "deadbeef"

    def test_generated_keys_are_unique(self):
        first, _ = generate_key()
        second, _ = generate_key()
        assert first != second


class TestCreateAndVerify:
    def test_database_stores_hash_only(self):
        api_key, raw_key = ApiKey.objects.create_key(name="Учебный скрипт")
        assert api_key.hashed_key == hash_key(raw_key)
        assert api_key.hashed_key != raw_key
        assert len(api_key.hashed_key) == 64

    def test_verify_finds_key_by_raw_value(self):
        api_key, raw_key = ApiKey.objects.create_key(name="Учебный скрипт")
        assert ApiKey.objects.verify(raw_key) == api_key

    def test_verify_marks_last_used_at(self):
        _, raw_key = ApiKey.objects.create_key(name="Учебный скрипт")
        verified = ApiKey.objects.verify(raw_key)
        assert verified.last_used_at is not None

    def test_verify_rejects_unknown_prefix(self):
        assert ApiKey.objects.verify("kcn_deadbeef_somesecret") is None

    def test_verify_rejects_wrong_secret(self):
        _, raw_key = ApiKey.objects.create_key(name="Учебный скрипт")
        prefix = parse_prefix(raw_key)
        assert ApiKey.objects.verify(f"kcn_{prefix}_wrong-secret") is None

    def test_verify_rejects_malformed_value(self):
        assert ApiKey.objects.verify("не ключ") is None

    def test_verify_rejects_inactive_key(self):
        _, raw_key = ApiKey.objects.create_key(name="Отозван", is_active=False)
        assert ApiKey.objects.verify(raw_key) is None

    def test_verify_rejects_expired_key(self):
        _, raw_key = ApiKey.objects.create_key(
            name="Просрочен", expires_at=timezone.now() - timedelta(minutes=1)
        )
        assert ApiKey.objects.verify(raw_key) is None

    def test_verify_accepts_key_expiring_later(self):
        _, raw_key = ApiKey.objects.create_key(
            name="Действующий", expires_at=timezone.now() + timedelta(days=1)
        )
        assert ApiKey.objects.verify(raw_key) is not None


class TestScopes:
    def test_normalize_scopes_removes_duplicates_and_case(self):
        assert ApiKey.normalize_scopes(" Write, DELETE ,write ") == "write, delete"

    def test_normalize_scopes_handles_empty_value(self):
        assert ApiKey.normalize_scopes(None) == ""
        assert ApiKey.normalize_scopes("  ") == ""

    def test_save_normalizes_scopes(self):
        api_key, _ = ApiKey.objects.create_key(name="Ключ", scopes="WRITE,write")
        assert api_key.scopes == "write"

    def test_write_scope_does_not_allow_delete(self):
        api_key, _ = ApiKey.objects.create_key(name="Ключ", scopes="write")
        assert api_key.has_scope(ApiKey.Scope.WRITE)
        assert not api_key.has_scope(ApiKey.Scope.DELETE)

    def test_manage_scope_covers_write_and_delete(self):
        api_key, _ = ApiKey.objects.create_key(name="Ключ", scopes="manage")
        assert api_key.has_scope(ApiKey.Scope.WRITE)
        assert api_key.has_scope(ApiKey.Scope.DELETE)

    def test_clean_rejects_unknown_scope(self):
        api_key = ApiKey(
            name="Ключ", prefix="deadbeef", hashed_key="0" * 64, scopes="read"
        )
        with pytest.raises(ValidationError) as exc_info:
            api_key.full_clean()
        assert "scopes" in exc_info.value.message_dict

    def test_clean_rejects_missing_scopes(self):
        api_key = ApiKey(name="Ключ", prefix="deadbeef", hashed_key="0" * 64, scopes="")
        with pytest.raises(ValidationError) as exc_info:
            api_key.full_clean()
        assert "scopes" in exc_info.value.message_dict
