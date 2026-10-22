"""Synthetic course dialogue. All authority belongs to deterministic host code."""

from .domain import TurnRequest, TurnResult
from .service import Conversation

__all__ = ["Conversation", "TurnRequest", "TurnResult"]
