"""Whose sets are whose.

The models all live in one store on one server, so "My sets" has to be told
which install is asking. Without that every visitor is shown everyone else's
work, and the homepage examples -- which live in the same store so they open
as ordinary sets -- are listed as though the visitor had made them.
"""

from __future__ import annotations

import io
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.main import app

ALICE = {"X-BrickSnap-Client": "client-alice"}
BOB = {"X-BrickSnap-Client": "client-bob"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _photo() -> bytes:
    im = Image.new("RGB", (320, 320), "white")
    d = ImageDraw.Draw(im)
    d.rectangle((110, 90, 210, 250), fill=(200, 40, 40))
    d.rectangle((130, 40, 190, 95), fill=(60, 60, 200))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture(scope="module")
def alices_model(client) -> str:
    job = client.post("/api/jobs", headers=ALICE,
                      files={"files": ("ref.png", _photo(), "image/png")},
                      data={"angles": "front"})
    assert job.status_code == 200, job.text
    job_id = job.json()["id"]

    started = client.post("/api/jobs/%s/build" % job_id, headers=ALICE,
                          json={"size": "mini", "detail": "simple",
                                "priority": "balanced", "unseen_back": "mirror"})
    assert started.status_code == 200, started.text

    for _ in range(120):
        state = client.get("/api/jobs/%s" % job_id, headers=ALICE).json()
        if state["status"] == "done":
            return state["model_id"]
        if state["status"] == "failed":
            pytest.fail("build failed: %s" % state.get("error"))
        time.sleep(0.5)
    pytest.fail("build did not finish")


def _ids(client, headers) -> set:
    r = client.get("/api/models", headers=headers)
    assert r.status_code == 200
    return {m["id"] for m in r.json()["models"]}


def test_a_set_is_listed_for_the_install_that_made_it(client, alices_model):
    assert alices_model in _ids(client, ALICE)


def test_a_set_is_not_listed_for_anyone_else(client, alices_model):
    assert alices_model not in _ids(client, BOB)
    # An install that has made nothing sees nothing, not everything.
    assert _ids(client, BOB) == set()


def test_an_unidentified_caller_is_not_shown_everything(client, alices_model):
    assert alices_model not in _ids(client, {})


def test_the_shops_examples_are_not_listed_as_yours(client):
    assert not any(i.startswith("example-") for i in _ids(client, ALICE))


def test_a_set_still_opens_by_its_id_for_anyone_given_the_link(client,
                                                               alices_model):
    # Ownership decides what is listed, not what resolves: a link someone was
    # sent has to keep working.
    assert client.get("/api/models/%s" % alices_model, headers=BOB).status_code == 200
