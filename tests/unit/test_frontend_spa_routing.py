"""Tests for SPA deep-link routing when serving built frontend."""

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from taxtracker.cli import app as app_module

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.unit
def test_frontend_route_w4_serves_spa_index(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Refreshing /w4 should serve index.html for the SPA router."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True)
    index_file = dist_dir / "index.html"
    index_file.write_text("<html><body>SPA Index</body></html>", encoding="utf-8")

    monkeypatch.setattr(app_module, "_FRONTEND_DIST", dist_dir)

    app = app_module.create_app(skip_db_init=True, serve_frontend=True)
    with TestClient(app) as client:
        response = client.get("/w4")

    assert response.status_code == 200
    assert "SPA Index" in response.text


@pytest.mark.unit
def test_nested_w4_path_stays_api_namespace(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Unknown nested /w4/* paths should not be swallowed by SPA fallback."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text("<html><body>SPA Index</body></html>", encoding="utf-8")

    monkeypatch.setattr(app_module, "_FRONTEND_DIST", dist_dir)

    app = app_module.create_app(skip_db_init=True, serve_frontend=True)
    with TestClient(app) as client:
        response = client.get("/w4/not-a-real-api-route")

    assert response.status_code == 404
    assert response.json()["detail"] == "Not Found"
