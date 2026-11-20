import json

import pytest

from ai_project.blackboard import Blackboard, JsonStore, MemoryStore, RedisStore, StoreError
from tests.helpers import msg


def run_short_session(store, session_id="s1"):
    board = Blackboard(store=store, session_id=session_id)
    board.initialize_task("Pick", {"options": ["A", "B"]}, agents=["a", "b"])
    board.commit(msg("a", "INIT", "A"))
    board.commit(msg("b", "RATIFY", "A", judgment=(True, True, False)))
    board.set_weight("b", 0.5)
    return board


def test_memory_store_reload():
    store = MemoryStore()
    board = run_short_session(store)
    again = Blackboard.load(store, "s1")
    assert again.get_state().to_dict() == board.get_state().to_dict()
    with pytest.raises(StoreError):
        store.load("missing")


def test_json_store_reload(tmp_path):
    store = JsonStore(tmp_path)
    board = run_short_session(store)
    again = Blackboard.load(JsonStore(tmp_path), "s1")
    assert again.get_state().to_dict() == board.get_state().to_dict()
    assert store.sessions() == ["s1"]
    lines = (tmp_path / "s1" / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["seq"] for line in lines] == [1, 2, 3, 4]


def test_json_store_ignores_a_torn_last_write(tmp_path):
    store = JsonStore(tmp_path)
    board = run_short_session(store)
    with open(tmp_path / "s1" / "events.jsonl", "a", encoding="utf-8") as f:
        f.write('{"seq": 5, "kind": "wei')  # crash mid-write
    again = Blackboard.load(store, "s1")
    assert again.version == board.version


def test_json_store_rejects_corruption_in_the_middle(tmp_path):
    store = JsonStore(tmp_path)
    run_short_session(store)
    path = tmp_path / "s1" / "events.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[1] = "{not json"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(StoreError):
        store.load("s1")


def test_json_store_meta_is_replaced_atomically(tmp_path):
    store = JsonStore(tmp_path)
    store.write_meta("s1", {"status": "RUNNING"})
    store.write_meta("s1", {"status": "CONSENSUS"})
    assert store.read_meta("s1") == {"status": "CONSENSUS"}
    assert not list((tmp_path / "s1").glob("*.tmp"))


@pytest.mark.parametrize("bad", ["", "..", "a/b", "c:d"])
def test_json_store_rejects_unsafe_session_ids(tmp_path, bad):
    with pytest.raises(StoreError):
        JsonStore(tmp_path).append(bad, None)


class FakeRedis:
    def __init__(self):
        self.streams, self.values = {}, {}

    def xadd(self, key, fields):
        self.streams.setdefault(key, []).append((str(len(self.streams.get(key, []))), fields))

    def xrange(self, key):
        return list(self.streams.get(key, []))

    def scan_iter(self, match):
        prefix = match.rstrip("*")
        return [k for k in [*self.streams, *self.values] if k.startswith(prefix)]

    def set(self, key, value):
        self.values[key] = value

    def get(self, key):
        return self.values.get(key)


def test_redis_store_round_trip():
    store = RedisStore(client=FakeRedis())
    board = run_short_session(store)
    store.write_meta("s1", {"ok": True})
    assert Blackboard.load(store, "s1").get_state().to_dict() == board.get_state().to_dict()
    assert store.sessions() == ["s1"]
    assert store.read_meta("s1") == {"ok": True}
