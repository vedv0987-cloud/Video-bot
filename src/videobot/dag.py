"""Node graph and runner.

Nodes declare what they depend on; the runner topologically orders them, checks
the cache, and only calls `produce` on a miss.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from .cache import Artifact, Cache


class Node:
    """A single pipeline step.

    Subclasses set `name`, `version`, `deps`, `suffix` and implement `produce`.
    Bump `version` whenever the output of `produce` changes for unchanged
    inputs — that is what invalidates already-cached artifacts.
    """

    name: str = ""
    version: str = "1"
    deps: tuple[str, ...] = ()
    suffix: str = ".json"

    def params(self, ctx: Mapping[str, Any]) -> dict[str, Any]:
        """Run parameters that affect output. Must be JSON-representable."""
        return {}

    def produce(self, ctx: Mapping[str, Any], inputs: Mapping[str, Artifact]) -> bytes:
        raise NotImplementedError


@dataclass
class RunReport:
    """What the runner did, for CLI output and tests."""

    hits: list[str] = field(default_factory=list)
    misses: list[str] = field(default_factory=list)
    artifacts: dict[str, Artifact] = field(default_factory=dict)

    @property
    def order(self) -> list[str]:
        return list(self.artifacts)


def topological_order(nodes: Mapping[str, Node]) -> list[str]:
    """Depth-first topological sort. Raises on cycles and unknown deps."""
    ordered: list[str] = []
    state: dict[str, str] = {}

    def visit(name: str, trail: tuple[str, ...]) -> None:
        mark = state.get(name)
        if mark == "done":
            return
        if mark == "active":
            cycle = " -> ".join(trail + (name,))
            raise ValueError(f"dependency cycle: {cycle}")
        if name not in nodes:
            raise KeyError(f"unknown dependency {name!r} (required by {trail[-1]!r})")
        state[name] = "active"
        for dep in nodes[name].deps:
            visit(dep, trail + (name,))
        state[name] = "done"
        ordered.append(name)

    for name in nodes:
        visit(name, ())
    return ordered


class Runner:
    """Executes a node graph against a cache."""

    def __init__(self, cache: Cache, nodes: Mapping[str, Node]) -> None:
        mismatched = [n for n, node in nodes.items() if node.name != n]
        if mismatched:
            raise ValueError(f"node name mismatch for: {', '.join(mismatched)}")
        self.cache = cache
        self.nodes = dict(nodes)

    def run(
        self,
        ctx: Mapping[str, Any],
        force: frozenset[str] = frozenset(),
        on_node: Callable[[str, bool, str], None] | None = None,
    ) -> RunReport:
        """Run every node in dependency order.

        `force` names nodes to recompute even on a cache hit. Their downstream
        nodes re-run only if the forced node's content actually changed — which
        is the point of keying on digests rather than on timestamps.

        `on_node(name, was_cached, digest)` fires as each node settles, so a
        caller can report progress while the graph is still running. A voice
        node that takes half a minute should not look like a hang.
        """
        unknown = force - self.nodes.keys()
        if unknown:
            raise KeyError(f"cannot force unknown node(s): {', '.join(sorted(unknown))}")

        report = RunReport()
        for name in topological_order(self.nodes):
            node = self.nodes[name]
            inputs = {dep: report.artifacts[dep] for dep in node.deps}
            key = self.cache.key(name, node.version, node.params(ctx), list(inputs.values()))

            artifact = None if name in force else self.cache.get(name, key, node.suffix)
            if artifact is None:
                payload = node.produce(ctx, inputs)
                artifact = self.cache.put(
                    name,
                    key,
                    node.suffix,
                    payload,
                    meta={"version": node.version, "deps": list(node.deps)},
                )
                report.misses.append(name)
            else:
                report.hits.append(name)
            report.artifacts[name] = artifact
            if on_node is not None:
                on_node(name, name in report.hits, artifact.digest)
        return report
