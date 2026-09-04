"""Retrieval sources.

Each source returns `Evidence`: a passage plus enough identity to cite it and
find it again. A claim without one of these never reaches the script.
"""

from .base import Evidence, GatherResult, SourceSet, live_sources
from .pubmed import PubMedSource
from .wikipedia import WikipediaSource

__all__ = ["Evidence", "GatherResult", "SourceSet", "live_sources", "PubMedSource", "WikipediaSource"]
