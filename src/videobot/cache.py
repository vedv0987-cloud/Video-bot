"""Content-addressed artifact cache.

A node's key is derived from its identity, its parameters, and the digests of
its inputs — never from wall-clock time or output paths. Change a word in the
script and only the nodes downstream of that word re-run.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from .hashing import canonical_json, digest_bytes, digest_data


@dataclass(frozen=True)
class Artifact:
    """One cached output. `path` is guaranteed to exist while the cache does."""

    node: str
    key: str
    path: Path
    digest: str
    meta: dict[str, Any] = field(default_factory=dict)

    def read_bytes(self) -> bytes:
        return self.path.read_bytes()

    def read_json(self) -> Any:
        return json.loads(self.path.read_text("utf-8"))

    def as_ref(self) -> dict[str, str]:
        """Reference form embedded in the scene spec."""
        return {"node": self.node, "digest": self.digest, "path": str(self.path)}


class Cache:
    """Filesystem cache rooted at `root`, laid out as `<root>/<node>/<key><suffix>`."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def key(
        self,
        node: str,
        version: str,
        params: Mapping[str, Any],
        inputs: Sequence[Artifact] = (),
    ) -> str:
        """Cache key for a node invocation.

        Input *digests* participate, not input paths — so relocating the cache
        does not invalidate it, while changing upstream content does.
        """
        return digest_data(
            {
                "node": node,
                "version": version,
                "params": json.loads(canonical_json(params)),
                "inputs": [a.digest for a in inputs],
            }
        )

    def _paths(self, node: str, key: str, suffix: str) -> tuple[Path, Path]:
        base = self.root / node
        return base / f"{key}{suffix}", base / f"{key}.meta.json"

    def get(self, node: str, key: str, suffix: str) -> Artifact | None:
        """Return the cached artifact, or None on a miss.

        A payload without its sidecar counts as a miss: it was written by an
        interrupted run and cannot be trusted.
        """
        payload, sidecar = self._paths(node, key, suffix)
        if not payload.exists() or not sidecar.exists():
            return None
        meta = json.loads(sidecar.read_text("utf-8"))
        return Artifact(
            node=node,
            key=key,
            path=payload,
            digest=meta["digest"],
            meta=meta.get("meta", {}),
        )

    def put(
        self,
        node: str,
        key: str,
        suffix: str,
        payload: bytes,
        meta: Mapping[str, Any] | None = None,
    ) -> Artifact:
        """Write an artifact and its sidecar.

        The payload lands via a temp file so a crash mid-write cannot leave a
        truncated artifact that later reads as a cache hit.
        """
        path, sidecar = self._paths(node, key, suffix)
        path.parent.mkdir(parents=True, exist_ok=True)
        digest = digest_bytes(payload)

        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(payload)
        tmp.replace(path)

        sidecar.write_text(
            json.dumps({"digest": digest, "meta": dict(meta or {})}, indent=2, sort_keys=True),
            "utf-8",
        )
        return Artifact(node=node, key=key, path=path, digest=digest, meta=dict(meta or {}))

    def clear(self, node: str | None = None) -> None:
        """Drop the whole cache, or one node's slice of it."""
        target = self.root / node if node else self.root
        if target.exists():
            shutil.rmtree(target)
