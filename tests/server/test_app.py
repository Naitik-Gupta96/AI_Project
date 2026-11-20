import time

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from ai_project.server.app import create_app  # noqa: E402


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path, catalog_size=3, web_dir=tmp_path / "none")) as c:
        yield c


def start(client, **kw):
    body = {"task_id": "architecture", "cf_agents": ["analyst"], "pace": 0, **kw}
    response = client.post("/api/sessions", json=body)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def wait_finished(client, session_id, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        summary = client.get(f"/api/sessions/{session_id}").json()
        if summary["state"] in ("finished", "error"):
            return summary
        time.sleep(0.02)
    raise AssertionError("session did not finish")


def test_health_and_catalog(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    catalog = client.get("/api/catalog").json()
    synthetic = next(b for b in catalog["benchmarks"] if b["name"] == "synthetic")
    assert synthetic["tasks"][0]["task_id"] == "architecture"
    assert synthetic["tasks"][0]["roles"] == ["analyst", "critic", "specialist"]
    assert catalog["providers"][0]["spec"] == "mock"


def test_session_runs_and_exposes_events_and_states(client):
    session_id = start(client)
    summary = wait_finished(client, session_id)
    assert summary["status"] == "CONSENSUS"
    assert summary["result"]["final_prediction"] == "Option B"
    events = client.get(f"/api/sessions/{session_id}/events").json()
    assert events[0]["kind"] == "task"
    assert [e["seq"] for e in events] == list(range(1, len(events) + 1))
    later = client.get(f"/api/sessions/{session_id}/events", params={"since": 5}).json()
    assert later[0]["seq"] == 6
    first = client.get(f"/api/sessions/{session_id}/state", params={"at": 1}).json()
    assert first["status"] == "INITIALIZED" and first["iteration"] == 0
    final = client.get(f"/api/sessions/{session_id}/state").json()
    assert final["status"] == "CONSENSUS"
    assert client.get(f"/api/sessions/{session_id}/state", params={"at": 10**6}).status_code == 400


def test_websocket_replays_backlog_then_ends(client):
    session_id = start(client)
    wait_finished(client, session_id)
    seen = []
    with client.websocket_connect(f"/ws/sessions/{session_id}") as ws:
        while True:
            message = ws.receive_json()
            seen.append(message)
            if message["type"] == "end":
                break
    board = [m["event"]["seq"] for m in seen if m["type"] == "board"]
    assert board == sorted(set(board)) and board[0] == 1
    kinds = [m["kind"] for m in seen if m["type"] == "cf"]
    assert kinds[0] == "cf.start" and kinds[-1] == "cf.applied"
    assert seen[-1]["result"]["status"] == "CONSENSUS"


def test_live_websocket_and_controls(client):
    session_id = start(client, pace=0.05, start_paused=True)
    assert client.get(f"/api/sessions/{session_id}").json()["paused"]
    with client.websocket_connect(f"/ws/sessions/{session_id}") as ws:
        assert ws.receive_json()["event"]["kind"] == "task"
        client.post(f"/api/sessions/{session_id}/control", json={"action": "step"})
        kinds = []
        while "message" not in kinds:
            kinds.append(ws.receive_json()["event"]["kind"])
        assert kinds[-1] == "message"
        client.post(f"/api/sessions/{session_id}/control", json={"action": "resume"})
        while ws.receive_json()["type"] != "end":
            pass
    assert client.get(f"/api/sessions/{session_id}").json()["status"] == "CONSENSUS"


def test_stopped_session_ends(client):
    session_id = start(client, pace=0.2)
    client.post(f"/api/sessions/{session_id}/control", json={"action": "stop"})
    summary = wait_finished(client, session_id)
    assert summary["result"]["scheduler"]["stop_reason"] == "stopped"


def test_stored_sessions_survive_a_restart(tmp_path):
    with TestClient(create_app(tmp_path, catalog_size=1, web_dir=tmp_path / "none")) as c:
        session_id = start(c)
        wait_finished(c, session_id)
    with TestClient(create_app(tmp_path, catalog_size=1, web_dir=tmp_path / "none")) as c:
        listed = c.get("/api/sessions").json()
        assert listed[0]["id"] == session_id and listed[0]["state"] == "stored"
        assert c.get(f"/api/sessions/{session_id}/state").json()["status"] == "CONSENSUS"
        with c.websocket_connect(f"/ws/sessions/{session_id}") as ws:
            messages = []
            while True:
                m = ws.receive_json()
                messages.append(m)
                if m["type"] == "end":
                    break
        assert messages[-1]["stored"] is True


@pytest.mark.parametrize(("body", "code"), [
    ({"task_id": "nope"}, 404),
    ({"provider": "gpt5"}, 400),
    ({"cf_agents": ["ghost"]}, 400),
    ({"apply": "magic"}, 422),
])
def test_bad_requests(client, body, code):
    assert client.post("/api/sessions", json={"pace": 0, **body}).status_code == code


def test_unknown_session(client):
    assert client.get("/api/sessions/missing/events").status_code == 404
    assert client.post("/api/sessions/missing/control", json={"action": "pause"}).status_code == 404
