"""Local dashboard — the pipeline without a terminal.

    videobot-dashboard          # then open http://127.0.0.1:8765

Deliberately stdlib only. Every setup failure on this project so far has come
from something that had to be installed first, and a control panel that needs
its own build step is a control panel you cannot open when you need it.

Security posture, all of it load-bearing:

* binds to 127.0.0.1, never 0.0.0.0 — this is a personal tool, not a service;
* the topic is validated through `slugify` before it reaches anything, and is
  never interpolated into a shell — the renderer is invoked with an argument
  list and `shell=False`;
* files are served only from inside the output directory, checked after
  resolution so `..` and symlinks cannot escape it.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import queue
import subprocess
import threading
import traceback
import uuid
import webbrowser
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .audio.align import ALIGNERS
from .audio.beats import BEAT_SOURCES, DEFAULT_BPM
from .audio.speech import SPEECH_BACKENDS
from .cli import DEFAULT_BRAND, DEFAULT_CACHE, DEFAULT_OUT, run_pipeline, slugify
from .nodes import default_nodes
from .platforms import FORMATS
from .nodes.script import REWRITERS

HOST = "127.0.0.1"
DEFAULT_PORT = 8765
WEB_ROOT = Path(__file__).parent / "web"

NODE_NAMES = list(default_nodes())
"""The graph decides the checklist, so the dashboard cannot drift from it."""


@dataclass
class Job:
    """One generation, and everything a browser needs to follow it."""

    id: str
    topic: str
    events: queue.Queue = field(default_factory=queue.Queue)
    done: bool = False

    def emit(self, kind: str, **payload: Any) -> None:
        self.events.put({"kind": kind, **payload})


class Studio:
    """Owns the jobs and the paths. One per server."""

    def __init__(self, root: Path, out: Path, cache: Path, brand: Path) -> None:
        self.root = root.resolve()
        self.out = out.resolve()
        self.cache = cache
        self.brand = brand
        self.jobs: dict[str, Job] = {}

    # --- generation -------------------------------------------------------

    def start(self, request: dict[str, Any]) -> Job:
        topic = str(request.get("topic", "")).strip()
        slugify(topic)  # raises ValueError on anything that cannot be a slug

        job = Job(id=uuid.uuid4().hex[:12], topic=topic)
        self.jobs[job.id] = job
        threading.Thread(target=self._run, args=(job, request), daemon=True).start()
        return job

    def _run(self, job: Job, request: dict[str, Any]) -> None:
        try:
            args = argparse.Namespace(
                topic=job.topic,
                aspect=_choice(request.get("aspect"), FORMATS, "9:16"),
                voice=_choice(request.get("voice"), SPEECH_BACKENDS, "kokoro"),
                rewriter=_choice(request.get("rewriter"), REWRITERS, "template"),
                aligner=_choice(request.get("aligner"), ALIGNERS, "estimated"),
                beats=_choice(request.get("beats"), BEAT_SOURCES, "fixed-tempo"),
                bpm=DEFAULT_BPM,
                media=bool(request.get("media")),
                offline=bool(request.get("offline")),
                brand=self.brand,
                cache=self.cache,
                out=self.out,
                force="",
                show=False,
                strict=False,
            )

            job.emit("stage", stage="spec", label="Building the scene spec")
            outcome = run_pipeline(
                args,
                on_node=lambda name, cached, digest: job.emit(
                    "node", node=name, cached=cached, digest=digest
                ),
            )
            job.emit(
                "spec",
                slug=outcome.slug,
                scenes=len(outcome.spec["scenes"]),
                duration=outcome.spec["meta"]["duration_s"],
                citations=len(outcome.spec["citations"]),
                gate=outcome.spec["compliance"]["gate"],
                warnings=outcome.warnings,
                screened=outcome.screened,
            )

            if request.get("render"):
                self._render(job, outcome.slug, request)
            job.emit("done", slug=outcome.slug)
        except Exception as exc:  # noqa: BLE001 - the browser must see the reason
            job.emit("failed", error=f"{type(exc).__name__}: {exc}", detail=traceback.format_exc())
        finally:
            job.done = True

    def _render(self, job: Job, slug: str, request: dict[str, Any]) -> None:
        """Hand the spec to the motion layer.

        `shell=False` with an argument list: the topic reached the filesystem as
        a validated slug and reaches node as one element of argv, so there is no
        string for a shell to reinterpret.
        """
        motion = self.root / "motion"
        spec = self.out / slug / "scene-spec.json"
        if not (motion / "node_modules").exists():
            raise RuntimeError(
                "the motion layer is not installed — run ./scripts/make-video.sh once first"
            )

        job.emit("stage", stage="render", label="Rendering frames")
        for command, note in (
            (["node", "scripts/prepare-data.mjs", str(spec)], "Staging the spec"),
            (["node", "scripts/render.mjs", *_render_flags(request)], "Rendering frames"),
        ):
            job.emit("stage", stage="render", label=note)
            done = subprocess.run(  # noqa: S603 - fixed argv, shell=False, validated slug
                command, cwd=motion, capture_output=True, text=True, shell=False
            )
            if done.returncode != 0:
                raise RuntimeError(f"{note.lower()} failed:\n{done.stderr.strip()[-1200:]}")

        job.emit("video", url=f"/media/{slug}/{slug}-9x16.mp4")

    # --- library ----------------------------------------------------------

    def runs(self) -> list[dict[str, Any]]:
        found = []
        if not self.out.exists():
            return found
        for directory in sorted(self.out.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            spec_path = directory / "scene-spec.json"
            if not spec_path.is_file():
                continue
            try:
                spec = json.loads(spec_path.read_text("utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            videos = sorted(directory.glob("*.mp4"))
            found.append(
                {
                    "slug": directory.name,
                    "topic": spec["meta"]["topic"],
                    "duration": spec["meta"]["duration_s"],
                    "scenes": len(spec["scenes"]),
                    "citations": len(spec["citations"]),
                    "gate": spec["compliance"]["gate"],
                    "video": f"/media/{directory.name}/{videos[-1].name}" if videos else None,
                }
            )
        return found

    def media(self, relative: str) -> Path:
        """Resolve a media path, refusing anything outside the output tree."""
        candidate = (self.out / relative).resolve()
        if not candidate.is_relative_to(self.out) or not candidate.is_file():
            raise FileNotFoundError(relative)
        return candidate


def _choice(value: Any, allowed: Any, fallback: str) -> str:
    return value if isinstance(value, str) and value in allowed else fallback


def _render_flags(request: dict[str, Any]) -> list[str]:
    """Preview flags, built from numbers rather than from anything typed."""
    if not request.get("preview"):
        return []
    return ["--scale", "0.25", "--seconds", "4"]


class Handler(BaseHTTPRequestHandler):
    studio: Studio
    server_version = "videobot"

    def log_message(self, fmt: str, *fmt_args: Any) -> None:
        pass  # the dashboard is the log

    # --- routes -----------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's interface
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            self._file(WEB_ROOT / "index.html")
        elif path == "/api/runs":
            self._json({"runs": self.studio.runs()})
        elif path == "/api/options":
            self._json(
                {
                    "aspects": sorted(FORMATS),
                    "voices": sorted(SPEECH_BACKENDS),
                    "nodes": NODE_NAMES,
                }
            )
        elif path.startswith("/api/events/"):
            self._stream(path.rsplit("/", 1)[-1])
        elif path.startswith("/media/"):
            self._media(path[len("/media/") :])
        else:
            self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/generate":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        try:
            request = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._json({"error": "malformed request"}, status=400)
            return
        try:
            job = self.studio.start(request)
        except ValueError as exc:
            self._json({"error": str(exc)}, status=400)
            return
        self._json({"job": job.id})

    # --- responses --------------------------------------------------------

    def _json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path) -> None:
        try:
            body = path.read_bytes()
        except OSError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _media(self, relative: str) -> None:
        try:
            path = self.studio.media(relative)
        except (FileNotFoundError, OSError):
            self.send_error(404)
            return
        # Range support, so the browser can scrub a video rather than only play it.
        size = path.stat().st_size
        start, end = 0, size - 1
        header = self.headers.get("Range")
        if header and header.startswith("bytes="):
            first, _, last = header[6:].partition("-")
            start = int(first or 0)
            end = int(last) if last else end
            end = min(end, size - 1)
        length = max(0, end - start + 1)

        self.send_response(206 if header else 200)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Accept-Ranges", "bytes")
        if header:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(length))
        self.end_headers()
        with path.open("rb") as handle:
            handle.seek(start)
            self.wfile.write(handle.read(length))

    def _stream(self, job_id: str) -> None:
        job = self.studio.jobs.get(job_id)
        if job is None:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        while True:
            try:
                event = job.events.get(timeout=30)
            except queue.Empty:
                if job.done:
                    return
                self.wfile.write(b": keepalive\n\n")  # a proxy-safe heartbeat
                self.wfile.flush()
                continue
            try:
                self.wfile.write(f"data: {json.dumps(event)}\n\n".encode("utf-8"))
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                return
            if event["kind"] in ("done", "failed"):
                return


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="videobot-dashboard", description="Local web dashboard for the video pipeline."
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--brand", type=Path, default=DEFAULT_BRAND)
    parser.add_argument("--no-open", action="store_true", help="do not open a browser")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    handler = type("BoundHandler", (Handler,), {"studio": Studio(args.root, args.out, args.cache, args.brand)})
    server = ThreadingHTTPServer((HOST, args.port), handler)
    url = f"http://{HOST}:{args.port}"
    print(f"Video studio → {url}\nCtrl-C to stop.")
    if not args.no_open:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
