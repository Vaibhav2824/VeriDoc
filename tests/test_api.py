"""API boundary checks — in-memory mode, no VLM or DB calls."""

from collections.abc import Iterator
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.api import main


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(main, "_db_available", False)
    monkeypatch.setattr(main, "_in_memory", {})
    monkeypatch.setattr(main, "_run_extraction", AsyncMock())
    yield TestClient(main.app)


def test_rejects_oversized_upload(client: TestClient) -> None:
    big = b"0" * (main.MAX_UPLOAD_BYTES + 1)
    r = client.post("/v1/extract", files={"file": ("a.pdf", big)})
    assert r.status_code == 413


def test_rejects_unsupported_type(client: TestClient) -> None:
    r = client.post("/v1/extract", files={"file": ("a.exe", b"x")})
    assert r.status_code == 400


def test_upload_creates_job(client: TestClient) -> None:
    r = client.post("/v1/extract", files={"file": ("a.png", b"x")})
    assert r.status_code == 202
    assert client.get(f"/v1/jobs/{r.json()['job_id']}").status_code == 200


def test_resolve_updates_queue_and_404s_on_unknown(client: TestClient) -> None:
    main._in_memory["j1"] = {
        "status": "done", "doc_name": "d",
        "review_queue": [{"field_name": "total", "resolved": False}],
    }
    body = {"corrected_value": "9.99"}
    assert client.post("/v1/queue/nope/total/resolve", json=body).status_code == 404
    assert client.post("/v1/queue/j1/other/resolve", json=body).status_code == 404
    assert client.post("/v1/queue/j1/total/resolve", json=body).status_code == 200
    item = client.get("/v1/jobs/j1").json()["review_queue"][0]
    assert item["resolved"] is True and item["corrected_value"] == "9.99"
    assert client.get("/v1/stats").json()["pending_review_items"] == 0
