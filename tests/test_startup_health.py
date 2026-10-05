"""Boot readiness gate for the API gateway (`api/main.py`)."""

from __future__ import annotations

from pathlib import Path

import pytest

from api import main


def test_serving_check_disabled_in_mock_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "USE_MOCKS", True)
    monkeypatch.delenv("SKIP_SERVING_CHECK", raising=False)

    assert main._serving_check_enabled() is False


def test_serving_check_disabled_by_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "USE_MOCKS", False)
    monkeypatch.setenv("SKIP_SERVING_CHECK", "1")

    assert main._serving_check_enabled() is False


def test_serving_check_enabled_in_live_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "USE_MOCKS", False)
    monkeypatch.delenv("SKIP_SERVING_CHECK", raising=False)

    assert main._serving_check_enabled() is True


def test_verify_raises_when_database_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(main, "USE_MOCKS", False)
    monkeypatch.delenv("SKIP_SERVING_CHECK", raising=False)
    monkeypatch.setattr(main, "DUCKDB_PATH", tmp_path / "missing.duckdb")

    with pytest.raises(RuntimeError):
        main._verify_serving_artifacts()


def test_verify_skips_in_mock_mode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(main, "USE_MOCKS", True)
    monkeypatch.setattr(main, "DUCKDB_PATH", tmp_path / "missing.duckdb")

    main._verify_serving_artifacts()
