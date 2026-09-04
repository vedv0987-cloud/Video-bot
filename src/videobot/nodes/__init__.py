"""Pipeline nodes.

Phase 1 wires the graph end to end with placeholder content so the cache,
schema, and validator are provable before any model is loaded. `research` and
`script` are replaced in Phase 2; `compose` is the real thing already.
"""

from ..dag import Node
from .compose import ComposeNode
from .research import ResearchNode
from .script import ScriptNode

__all__ = ["ComposeNode", "ResearchNode", "ScriptNode", "default_nodes"]


def default_nodes() -> dict[str, Node]:
    """The Phase 1 graph: research -> script -> compose."""
    nodes = [ResearchNode(), ScriptNode(), ComposeNode()]
    return {node.name: node for node in nodes}
