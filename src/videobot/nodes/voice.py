"""Voiceover node."""

from __future__ import annotations

from typing import Any, Mapping

from ..audio.speech import get_speech_backend
from ..cache import Artifact
from ..dag import Node
from .script import spoken_text


class VoiceNode(Node):
    name = "voice"
    version = "1"
    deps = ("script",)
    suffix = ".wav"

    def params(self, ctx: Mapping[str, Any]) -> dict[str, Any]:
        backend = get_speech_backend(ctx["voice"])
        return {"backend": backend.name, "model": backend.model}

    def produce(self, ctx: Mapping[str, Any], inputs: Mapping[str, Artifact]) -> bytes:
        script = inputs["script"].read_json()
        backend = get_speech_backend(ctx["voice"])
        text = " ".join(spoken_text(section) for section in script["sections"])
        return backend.synthesize(text)
