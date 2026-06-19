"""Health endpoint always answers 200 so the frontend status dot can render."""
from __future__ import annotations


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db"] in {"ok", "down"}
    assert body["version"]
