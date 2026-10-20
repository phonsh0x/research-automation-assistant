"""API 层回归测试（路由可达性）。

这些测试不启动任何服务，只使用 Starlette 的进程内 TestClient。
为避免副作用，所有会触达数据库/网络的端点都打了桩。
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402


def _convert_route_paths() -> list[str]:
    return [r.path for r in app.routes if getattr(r, "path", "").startswith("/api/v1/convert")]


class TestRouteOrdering:
    def test_static_batch_route_is_declared_before_dynamic(self):
        """`/convert/batch` 必须声明在 `/convert/{paper_id}` 之前。

        Starlette 按声明顺序匹配路由；若动态路由在前，`batch` 会被当作
        `paper_id` 解析并返回 422。
        """
        paths = _convert_route_paths()
        assert "/api/v1/convert/batch" in paths
        assert "/api/v1/convert/{paper_id}" in paths
        assert paths.index("/api/v1/convert/batch") < paths.index(
            "/api/v1/convert/{paper_id}"
        )

    def test_convert_batch_is_reachable(self, monkeypatch):
        """请求 /convert/batch 应命中批量端点，而不是动态路由。"""
        import ui.services.pdf_convert_ui_service as svc

        captured = {}

        def fake_convert_batch(limit=10):
            captured["limit"] = limit
            return {"success": True, "data": {"converted": 0}, "message": "stub"}

        monkeypatch.setattr(svc, "convert_batch", fake_convert_batch)

        client = TestClient(app)
        response = client.post("/api/v1/convert/batch", params={"limit": 3})

        assert response.status_code == 200
        assert captured.get("limit") == 3
        body = response.json()
        assert body["success"] is True
        assert body["message"] == "stub"

    def test_convert_single_still_resolves(self, monkeypatch):
        """动态路由本身仍应正常工作。"""
        import ui.services.pdf_convert_ui_service as svc

        captured = {}

        def fake_convert_single(paper_id):
            captured["paper_id"] = paper_id
            return {"success": True, "data": {"paper_id": paper_id}}

        monkeypatch.setattr(svc, "convert_single", fake_convert_single)

        client = TestClient(app)
        response = client.post("/api/v1/convert/42")

        assert response.status_code == 200
        assert captured.get("paper_id") == 42
        assert response.json()["success"] is True


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
