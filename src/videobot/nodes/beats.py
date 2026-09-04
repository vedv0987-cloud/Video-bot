"""Beat map node."""

from __future__ import annotations

import json
from typing import Any, Mapping

from ..audio.beats import get_beat_source
from ..audio.speech import wav_duration
from ..cache import Artifact
from ..dag import Node


class BeatsNode(Node):
    name = "beats"
    version = "1"
    deps = ("voice",)
    suffix = ".json"

    def params(self, ctx: Mapping[str, Any]) -> dict[str, Any]:
        return {"source": ctx["beats"], "bpm": ctx["bpm"]}

    def produce(self, ctx: Mapping[str, Any], inputs: Mapping[str, Artifact]) -> bytes:
        duration = wav_duration(inputs["voice"].path)
        beat_map = get_beat_source(ctx["beats"], ctx["bpm"]).beats(duration)
        payload = {"method": beat_map.method, "bpm": beat_map.bpm, "beats": beat_map.beats}
        return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
