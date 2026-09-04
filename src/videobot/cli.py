"""Command line entry point.

    videobot --topic "hydration"

Phase 1 stops at the spec: it emits `scene-spec.json` and validates it. No
pixels are rendered — that is the motion layer's job, and it is deliberately
not wired yet (UPGRADE-PLAN §6, Phase 1).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from .brand import BrandError, load_brand
from .cache import Cache
from .dag import Runner
from .nodes import default_nodes
from .platforms import FORMATS
from . import spec as spec_mod

DEFAULT_BRAND = Path("brand/health-v2.json")
DEFAULT_CACHE = Path(".cache")
DEFAULT_OUT = Path("output")


def slugify(text: str) -> str:
    """Lowercase, hyphenated, matching the spec schema's `slug` pattern."""
    cleaned = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if not cleaned:
        raise ValueError(f"topic {text!r} contains no usable characters")
    return cleaned


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="videobot", description="Generate a scene spec for a short health video."
    )
    parser.add_argument("--topic", required=True, help="subject of the video, e.g. 'hydration'")
    parser.add_argument("--aspect", default="9:16", choices=sorted(FORMATS), help="delivery aspect")
    parser.add_argument("--brand", type=Path, default=DEFAULT_BRAND, help="brand token file")
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE, help="artifact cache root")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory")
    parser.add_argument(
        "--force",
        default="",
        help="comma-separated node names to recompute even on a cache hit",
    )
    parser.add_argument("--print", action="store_true", dest="show", help="print the spec to stdout")
    parser.add_argument(
        "--strict", action="store_true", help="exit non-zero if any lint warning is raised"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        slug = slugify(args.topic)
        brand = load_brand(args.brand)
    except (BrandError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    ctx = {"topic": args.topic, "slug": slug, "aspect": args.aspect, "brand": brand}
    force = frozenset(name for name in args.force.split(",") if name)

    runner = Runner(Cache(args.cache), default_nodes())
    try:
        report = runner.run(ctx, force=force)
    except KeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    scene_spec = report.artifacts["compose"].read_json()

    try:
        spec_mod.validate(scene_spec)
    except spec_mod.SpecError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    warnings = spec_mod.lint(scene_spec)
    out_dir = args.out / slug
    spec_path = spec_mod.write(scene_spec, out_dir / "scene-spec.json")

    # Provenance is deliberately NOT part of the spec: a timestamp inside a
    # cached artifact would change its digest every run and defeat the cache.
    run_path = out_dir / "run.json"
    run_path.write_text(
        json.dumps(
            {
                "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "topic": args.topic,
                "aspect": args.aspect,
                "brand": brand.ref(),
                "cache": {"hits": report.hits, "misses": report.misses},
                "artifacts": {
                    name: artifact.as_ref() for name, artifact in report.artifacts.items()
                },
                "warnings": warnings,
            },
            indent=2,
        )
        + "\n",
        "utf-8",
    )

    for name in report.order:
        state = "hit " if name in report.hits else "miss"
        print(f"  [{state}] {name}  {report.artifacts[name].digest}")
    print(f"\nspec:  {spec_path}")
    print(f"run:   {run_path}")
    print(
        f"scenes: {len(scene_spec['scenes'])}  "
        f"duration: {scene_spec['meta']['duration_s']}s  "
        f"gate: {scene_spec['compliance']['gate']}"
    )

    if warnings:
        print(f"\n{len(warnings)} warning(s):")
        for warning in warnings:
            print(f"  ! {warning}")

    if args.show:
        print()
        print(spec_mod.dumps(scene_spec), end="")

    return 1 if (args.strict and warnings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
