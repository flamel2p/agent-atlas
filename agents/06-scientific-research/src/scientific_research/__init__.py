"""Deterministic synthetic literature mapping with local, bounded inputs."""

from .corpus import Corpus, Paper, parse_corpus
from .mapping import LiteratureMap, ResearchRequest, map_literature

__all__ = ["Corpus", "Paper", "LiteratureMap", "ResearchRequest", "parse_corpus", "map_literature"]
