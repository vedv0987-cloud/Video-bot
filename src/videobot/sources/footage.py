"""Footage sources — moving pictures under the type.

Two backends behind one shape, because they fail in different ways and only
one of them can be fixed by the user:

* `local` reads a folder of clips you already own. No key, no network, no
  licence question, and for a designer with an asset library it is usually the
  better footage anyway.
* `pexels` searches the Pexels video API. Free, commercial use, no attribution
  required — but it needs a key, and without one it says so rather than
  quietly returning nothing.

Wikimedia Commons is deliberately not among them. It was tried: the pool for
health topics is clinical documentation, and a general search for "dehydration"
returns an aerial photograph of ploughed fields.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from ..http import FetchError, get_json

VIDEO_SUFFIXES = (".mp4", ".mov", ".m4v", ".webm")

MIN_WIDTH = 1080
"""Below the delivery width, upscaling shows. A clip that cannot fill the
frame is not a clip we can use."""

MIN_DURATION_S = 3.0
"""Shorter than this and a scene outlasts its own footage."""


@dataclass(frozen=True)
class Clip:
    """One usable piece of footage, wherever it came from."""

    src: str
    """A URL to download, or an absolute path already on disk."""

    credit: str
    licence: str
    width: int
    height: int
    duration_s: float
    page: str = ""
    local: bool = False

    def portrait_fit(self, aspect: str) -> bool:
        """Whether this clip can fill the frame without upscaling."""
        if self.width < MIN_WIDTH or self.duration_s < MIN_DURATION_S:
            return False
        ratio = self.width / self.height if self.height else 0
        if aspect == "9:16":
            return ratio <= 1.05  # portrait or square; a landscape clip crops to nothing
        if aspect == "1:1":
            return 0.7 <= ratio <= 1.45
        return ratio >= 1.2


class LocalFootageSource:
    """Clips from a folder on this machine.

    Ordering is by name so the choice is a pure function of the folder's
    contents — the cache depends on it, and "whatever the filesystem returned
    first" is not a decision anyone can reproduce.
    """

    kind = "local"
    version = "1"

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory).expanduser()

    def fetch(self, query: str, limit: int) -> Sequence[Clip]:
        if not self.directory.is_dir():
            raise FetchError(f"footage folder not found: {self.directory}")

        files = sorted(
            path
            for path in self.directory.rglob("*")
            if path.suffix.lower() in VIDEO_SUFFIXES and path.is_file()
        )
        if not files:
            raise FetchError(
                f"no video files in {self.directory} "
                f"(looked for {', '.join(VIDEO_SUFFIXES)})"
            )

        # Dimensions and duration are read by the media node with ffprobe; a
        # local clip is trusted to be usable, since someone chose to put it
        # there. Zeroes mean "not measured yet", not "unusable".
        return [
            Clip(
                src=str(path.resolve()),
                credit=path.stem,
                licence="local",
                width=0,
                height=0,
                duration_s=0.0,
                local=True,
            )
            for path in files[:limit]
        ]


class PexelsVideoSource:
    """The Pexels video API. Free, commercial use, no attribution required."""

    kind = "pexels"
    version = "1"
    ENDPOINT = "https://api.pexels.com/videos/search"
    KEY_ENV = "PEXELS_API_KEY"

    def __init__(self, key: str | None = None) -> None:
        self.key = key or os.environ.get(self.KEY_ENV, "")

    def fetch(self, query: str, limit: int) -> Sequence[Clip]:
        if not self.key:
            raise FetchError(
                f"no Pexels API key — set {self.KEY_ENV}. One is free at "
                "https://www.pexels.com/api/, or use --footage <folder> with your own clips"
            )

        payload = get_json(
            self.ENDPOINT,
            {"query": query, "per_page": max(limit, 10), "orientation": "portrait"},
            headers={"Authorization": self.key},
        )

        clips: list[Clip] = []
        for video in payload.get("videos", []):
            best = _best_rendition(video.get("video_files", []))
            if best is None:
                continue
            clips.append(
                Clip(
                    src=best["link"],
                    credit=video.get("user", {}).get("name", "Pexels"),
                    licence="Pexels licence — free for commercial use, no attribution required",
                    width=int(best.get("width") or 0),
                    height=int(best.get("height") or 0),
                    duration_s=float(video.get("duration") or 0),
                    page=video.get("url", ""),
                )
            )
        return clips[:limit]


def _best_rendition(files: Sequence[dict]) -> dict | None:
    """The smallest rendition that still fills the frame.

    Not the largest: a 4K master costs minutes of download and is scaled back
    down at authoring resolution anyway.
    """
    usable = [
        f
        for f in files
        if f.get("link") and int(f.get("width") or 0) >= MIN_WIDTH and f.get("file_type") == "video/mp4"
    ]
    if not usable:
        return None
    return min(usable, key=lambda f: int(f["width"]))


def probe_clip(path: Path | str) -> float:
    """Duration of a clip, in seconds, via ffprobe.

    A local clip's length is not knowable without asking the file, and a scene
    that outlasts its footage freezes on the last frame — which reads as a
    crash, not a choice.
    """
    import subprocess

    done = subprocess.run(  # noqa: S603 - fixed argv, shell=False, path from the filesystem
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        shell=False,
    )
    if done.returncode != 0:
        raise RuntimeError(f"ffprobe could not read {path}: {done.stderr.strip()[:200]}")
    try:
        return float(done.stdout.strip())
    except ValueError as exc:
        raise RuntimeError(f"ffprobe gave no duration for {path}") from exc
