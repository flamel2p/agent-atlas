"""Explain recorded synthetic task priorities without model or external effects.

Parse a request at the boundary, classify it once, then pass its immutable trace
through the all-audience explanation gate. No module keeps state across runs.
"""

from .decision import classify, load_trace, parse_request, trace_to_dict
from .explanation import explain

__all__ = ["classify", "explain", "load_trace", "parse_request", "trace_to_dict"]
