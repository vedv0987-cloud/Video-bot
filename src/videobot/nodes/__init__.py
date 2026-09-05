"""Pipeline nodes.

    research ─▶ script ─┬─▶ voice ─┬─▶ align ─┐
                        │          └─▶ beats ─┤
                        └─▶ media ────────────┴─▶ compose ─▶ scene-spec.json
"""

from ..dag import Node
from .align import AlignNode
from .beats import BeatsNode
from .compose import ComposeNode
from .media import MediaNode
from .research import ResearchNode
from .script import ScriptNode
from .voice import VoiceNode

__all__ = [
    "AlignNode",
    "BeatsNode",
    "ComposeNode",
    "MediaNode",
    "ResearchNode",
    "ScriptNode",
    "VoiceNode",
    "default_nodes",
]


def default_nodes() -> dict[str, Node]:
    nodes = [
        ResearchNode(),
        ScriptNode(),
        MediaNode(),
        VoiceNode(),
        AlignNode(),
        BeatsNode(),
        ComposeNode(),
    ]
    return {node.name: node for node in nodes}
