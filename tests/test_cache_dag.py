from __future__ import annotations

import pytest

from videobot.cache import Cache
from videobot.dag import Node, Runner, topological_order
from videobot.hashing import canonical_json, digest_data


class Recorder(Node):
    """Node that counts how often it actually computed."""

    suffix = ".txt"

    def __init__(self, name: str, deps: tuple[str, ...] = (), payload: str = "x") -> None:
        self.name = name
        self.deps = deps
        self.payload = payload
        self.calls = 0

    def params(self, ctx):
        return {"payload": self.payload}

    def produce(self, ctx, inputs):
        self.calls += 1
        upstream = "".join(a.read_bytes().decode() for a in inputs.values())
        return (upstream + self.payload).encode()


def test_canonical_json_is_key_order_independent():
    assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})
    assert digest_data({"b": 1, "a": 2}) == digest_data({"a": 2, "b": 1})


def test_canonical_json_rejects_non_representable():
    with pytest.raises(TypeError):
        canonical_json({"when": object()})


def test_cache_roundtrip(tmp_path):
    cache = Cache(tmp_path)
    key = cache.key("n", "1", {"a": 1})
    assert cache.get("n", key, ".txt") is None

    artifact = cache.put("n", key, ".txt", b"hello", meta={"v": 1})
    fetched = cache.get("n", key, ".txt")
    assert fetched is not None
    assert fetched.digest == artifact.digest
    assert fetched.read_bytes() == b"hello"


def test_cache_key_tracks_params_and_input_digests(tmp_path):
    cache = Cache(tmp_path)
    base = cache.key("n", "1", {"a": 1})
    assert cache.key("n", "1", {"a": 2}) != base
    assert cache.key("n", "2", {"a": 1}) != base

    upstream = cache.put("u", "k", ".txt", b"one")
    changed = cache.put("u", "k2", ".txt", b"two")
    assert cache.key("n", "1", {}, [upstream]) != cache.key("n", "1", {}, [changed])


def test_payload_without_sidecar_is_a_miss(tmp_path):
    """An interrupted write must not read back as a hit."""
    cache = Cache(tmp_path)
    key = cache.key("n", "1", {})
    cache.put("n", key, ".txt", b"hello")
    (tmp_path / "n" / f"{key}.meta.json").unlink()
    assert cache.get("n", key, ".txt") is None


def test_topological_order_respects_dependencies():
    nodes = {n.name: n for n in [Recorder("c", ("b",)), Recorder("a"), Recorder("b", ("a",))]}
    assert topological_order(nodes) == ["a", "b", "c"]


def test_cycles_are_rejected():
    nodes = {n.name: n for n in [Recorder("a", ("b",)), Recorder("b", ("a",))]}
    with pytest.raises(ValueError, match="dependency cycle"):
        topological_order(nodes)


def test_unknown_dependency_is_rejected():
    nodes = {"a": Recorder("a", ("nope",))}
    with pytest.raises(KeyError, match="unknown dependency"):
        topological_order(nodes)


def test_runner_rejects_name_mismatch(tmp_path):
    with pytest.raises(ValueError, match="name mismatch"):
        Runner(Cache(tmp_path), {"wrong": Recorder("right")})


def test_second_run_is_all_cache_hits(tmp_path):
    nodes = {n.name: n for n in [Recorder("a"), Recorder("b", ("a",))]}
    runner = Runner(Cache(tmp_path), nodes)

    first = runner.run({})
    assert first.misses == ["a", "b"]

    second = Runner(Cache(tmp_path), {n.name: n for n in [Recorder("a"), Recorder("b", ("a",))]}).run({})
    assert second.hits == ["a", "b"]
    assert second.misses == []


def test_force_recomputes_but_identical_output_keeps_downstream_cached(tmp_path):
    """Digest-keyed, not timestamp-keyed: recomputing to the same bytes is free."""
    make = lambda: {n.name: n for n in [Recorder("a"), Recorder("b", ("a",))]}
    Runner(Cache(tmp_path), make()).run({})

    nodes = make()
    report = Runner(Cache(tmp_path), nodes).run({}, force=frozenset({"a"}))
    assert report.misses == ["a"]
    assert report.hits == ["b"]
    assert nodes["a"].calls == 1
    assert nodes["b"].calls == 0


def test_changed_upstream_invalidates_downstream(tmp_path):
    Runner(Cache(tmp_path), {n.name: n for n in [Recorder("a"), Recorder("b", ("a",))]}).run({})

    nodes = {n.name: n for n in [Recorder("a", payload="CHANGED"), Recorder("b", ("a",))]}
    report = Runner(Cache(tmp_path), nodes).run({})
    assert report.misses == ["a", "b"]


def test_forcing_unknown_node_raises(tmp_path):
    runner = Runner(Cache(tmp_path), {"a": Recorder("a")})
    with pytest.raises(KeyError, match="cannot force unknown"):
        runner.run({}, force=frozenset({"ghost"}))


def test_clear_drops_one_node_and_keeps_the_rest(tmp_path):
    cache = Cache(tmp_path)
    cache.put("a", "k", ".txt", b"one")
    cache.put("b", "k", ".txt", b"two")

    cache.clear("a")
    assert cache.get("a", "k", ".txt") is None
    assert cache.get("b", "k", ".txt") is not None

    cache.clear()
    assert cache.get("b", "k", ".txt") is None
