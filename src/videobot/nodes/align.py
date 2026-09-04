"""Alignment node — word timings against the rendered voiceover."""

from __future__ import annotations

import json
from typing import Any, Mapping

from ..audio.align import get_aligner
from ..audio.speech import wav_duration
from ..cache import Artifact
from ..dag import Node


class AlignNode(Node):
    name = "align"
    version = "1"
    deps = ("script", "voice")
    suffix = ".json"

    def params(self, ctx: Mapping[str, Any]) -> dict[str, Any]:
        return {"aligner": ctx["aligner"]}

    def produce(self, ctx: Mapping[str, Any], inputs: Mapping[str, Artifact]) -> bytes:
        script = inputs["script"].read_json()
        duration = wav_duration(inputs["voice"].path)

        result = get_aligner(ctx["aligner"]).align(script["sections"], duration)
        payload = {
            "method": result.method,
            "duration_s": round(result.duration_s, 3),
            "words": result.words,
            "sections": result.sections,
        }
        return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
