import os

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    # module scoped: the MCP session manager can only be started once per process
    out = tmp_path_factory.mktemp("renders")
    old = {k: os.environ.get(k) for k in ("SFX_OUT_DIR", "SFX_NO_PLAYBACK")}
    os.environ["SFX_OUT_DIR"] = str(out)
    os.environ["SFX_NO_PLAYBACK"] = "1"
    from sfx.server.rest import app

    with TestClient(app) as c:
        yield c
    for k, v in old.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def test_rest_roundtrip(client):
    assert client.get("/api/health").json()["ok"] is True
    assert "Laser" in client.get("/api/cookbook").json()["cookbook"]
    assert "coin" in client.get("/api/presets").json()
    assert "<title>sfx-api renders" in client.get("/").text

    r = client.post("/api/presets/coin/render", json={"overrides": {"master": {"target_lufs": -20}}})
    assert r.status_code == 200, r.text
    data = r.json()
    assert os.path.exists(data["path"]) and data["spec"]["master"]["target_lufs"] == -20
    sid = data["id"]

    wav = client.get(f"/api/renders/{sid}.wav")
    assert wav.status_code == 200 and wav.headers["content-type"].startswith("audio/wav")

    lst = client.get("/api/renders").json()["renders"]
    assert lst[0]["id"] == sid and "features" in lst[0]

    t = client.post(f"/api/renders/{sid}/tweak", json={"patch": {"master": {"target_lufs": -14}}})
    assert t.status_code == 200 and t.json()["spec"]["master"]["target_lufs"] == -14

    v = client.post("/api/variations", json={"sound_id": sid, "count": 2})
    assert [x["id"] for x in v.json()["variations"]] == [f"{sid}-v1", f"{sid}-v2"]

    assert client.post(f"/api/renders/{sid}/play").json()["played"] is False
    assert client.get("/api/renders/nope").status_code == 404
    bad = client.post("/api/render", json={"spec": {"layers": [{"source": {"type": "nope"}}]}})
    assert bad.status_code == 400 and "error" in bad.json()


def test_mcp_mounted_over_http(client):
    init = {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}},
    }
    r = client.post("/mcp/", json=init, headers={"accept": "application/json, text/event-stream", "host": "127.0.0.1:8765"})
    assert r.status_code == 200, r.text
    assert "sfx-api" in r.text
