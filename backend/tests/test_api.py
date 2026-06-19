"""API tests for POST /api/sign and the Vapi /api/ingest webhook (§3.5)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.gloss import GlossService, PassthroughProvider
from app.lookup import DictionaryLookup
from app.main import app
from app.pipeline import SignPipeline
from app.stub_dictionary import build_stub_clips


@pytest.fixture
def client():
    with TestClient(app) as c:
        # Override the startup pipeline with a hermetic one (no network).
        c.app.state.pipeline = SignPipeline(
            GlossService(providers=[PassthroughProvider()]),
            DictionaryLookup(build_stub_clips()),
            transition_frames=4,
        )
        yield c


def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_sign_returns_valid_sequence(client):
    r = client.post("/api/sign", json={"text": "My name is Jade."})
    assert r.status_code == 200
    body = r.json()
    assert body["model"] == "SMPLX_NEUTRAL"
    assert body["fps"] > 0
    assert len(body["frames"]) > 0
    assert len(body["betas"]) == 10
    # a frame conforms to §3.1 dims
    f = body["frames"][0]
    assert len(f["left_hand_pose"]) == 45 and len(f["body_pose"]) == 63


def test_sign_422_on_zero_match(client):
    r = client.post("/api/sign", json={"text": "xylophone zebra"})
    assert r.status_code == 422
    body = r.json()
    assert body["error"]
    assert body["unmatched"]  # non-empty


def test_ingest_webhook(client):
    r = client.post(
        "/api/ingest",
        json={"type": "transcript", "transcript": "Hello.", "timestamp": 0},
    )
    assert r.status_code == 200
    assert r.json()["model"] == "SMPLX_NEUTRAL"


def test_sign_rejects_bad_body(client):
    # missing "text" -> FastAPI request validation 422 (not our SignError shape)
    assert client.post("/api/sign", json={}).status_code == 422
