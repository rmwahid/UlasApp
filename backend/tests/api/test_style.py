"""The style endpoint: what it accepts, what it refuses, and what it means for the next generate."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.api.routes import jobs
from app.main import app
from app.services.state import initial_state, script_fingerprint


class FakeJob:
    id = "stylecheck"
    title = "Style check"
    status = "draft"
    stage = None
    error = None
    aspect = "9:16"
    mode = "voiceless"
    created_at = datetime.now(UTC)
    project_dir = ""


@pytest.fixture
def store(monkeypatch, tmp_path):
    """A project with no database and no files behind it, only the state the route reads."""
    holder = {
        "state": initial_state(
            "stylecheck", "Style check", "9:16", "voiceless", {"assets": [], "music": None}
        ),
        "written": [],
    }

    def fake_get(job_id):
        job = FakeJob()
        job.project_dir = str(tmp_path / "proj")
        return job

    def fake_read(directory):
        return holder["state"]

    def fake_write(directory, state):
        holder["written"].append(state)
        holder["state"] = state

    monkeypatch.setattr(jobs, "_get_job", fake_get)
    monkeypatch.setattr(jobs, "read_state", fake_read)
    monkeypatch.setattr(jobs, "write_state", fake_write)
    return holder


def patch_style(payload):
    with TestClient(app) as client:
        return client.patch("/api/jobs/stylecheck/style", json=payload)


def test_a_project_starts_on_the_default_style(store):
    with TestClient(app) as client:
        body = client.get("/api/jobs/stylecheck").json()
    assert body["state"]["style"] == {
        "shape": "ulasan",
        "beats": [],
        "tone": "bersih",
        "accent": None,
        "energy": "normal",
        "badge": "pill",
    }
    catalog = body["style_catalog"]
    assert [tone["id"] for tone in catalog["tones"]] == ["bersih", "tegas", "hangat", "toko"]
    assert [shape["id"] for shape in catalog["shapes"]] == ["ulasan", "reveal"]
    assert len(catalog["beats"]) == 11
    assert catalog["min_beats"] == 4 and catalog["max_beats"] == 9


def test_a_change_keeps_the_rest_of_the_block(store):
    response = patch_style({"tone": "tegas"})
    assert response.status_code == 200
    style = response.json()["style"]
    assert style["tone"] == "tegas"
    assert style["shape"] == "ulasan"
    assert style["badge"] == "pill"
    assert store["state"]["style"]["tone"] == "tegas"


@pytest.mark.parametrize(
    "payload",
    [
        {"tone": "neon"},
        {"energy": "hyper"},
        {"badge": "sticker"},
        {"accent": "red"},
        {"accent": "#12345"},
        {"shape": "custom", "beats": ["problem", "solution", "proof", "cta"]},
        {"shape": "custom", "beats": ["hook", "reveal", "reveal", "proof", "cta"]},
        {"shape": "custom", "beats": ["hook", "teleport", "proof", "cta"]},
        {"shape": "custom", "beats": ["hook", "proof", "cta"]},
    ],
)
def test_bad_choices_are_refused(store, payload):
    response = patch_style(payload)
    assert response.status_code == 422
    assert store["written"] == [], "a refused change must not be written"


def test_a_custom_shape_is_accepted_and_stored(store):
    beats = ["hook", "bait", "demo", "proof", "cta"]
    response = patch_style({"shape": "custom", "beats": beats})
    assert response.status_code == 200
    assert response.json()["style"] == {
        "shape": "custom",
        "beats": beats,
        "tone": "bersih",
        "accent": None,
        "energy": "normal",
        "badge": "pill",
    }


def test_only_the_shape_rewrites_the_script(store):
    """The tone is form: it must not cost the user the words they already approved."""
    store["state"]["style"] = {**store["state"]["style"], "shape": "reveal", "beats": []}
    store["state"]["script_fingerprint"] = script_fingerprint(store["state"])

    tone_change = patch_style({"tone": "hangat", "energy": "tenang"}).json()
    assert tone_change["script_exists"] is True
    assert tone_change["script_rewrites"] is False

    shape_change = patch_style({"shape": "ulasan", "beats": []}).json()
    assert shape_change["script_rewrites"] is True


def test_a_project_without_a_script_claims_no_rewrite(store):
    body = patch_style({"tone": "toko"}).json()
    assert body["script_exists"] is False
    assert body["script_rewrites"] is False
