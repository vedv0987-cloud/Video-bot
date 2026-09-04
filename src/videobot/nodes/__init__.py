"""Pipeline nodes.

    research ─▶ script ─▶ voice ─┬─▶ align ─┐
                                 └─▶ beats ─┴─▶ compose ─▶ scene-spec.json
"""

from ..dag import Node
from .align import AlignNode
from .beats import BeatsNode
from .compose import ComposeNode
from .research import ResearchNode
from .script import ScriptNode
from .voice import VoiceNode

__all__ = [
    "AlignNode",
    "BeatsNode",
    "ComposeNode",
    "ResearchNode",
    "ScriptNode",
    "VoiceNode",
    "default_nodes",
]


def default_nodes() -> dict[str, Node]:
    nodes = [ResearchNode(), ScriptNode(), VoiceNode(), AlignNode(), BeatsNode(), ComposeNode()]
    return {node.name: node for node in nodes}
