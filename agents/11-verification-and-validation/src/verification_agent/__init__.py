"""Verify a document against fixed synthetic evidence with no persistent state."""

from .domain import InputError, Report, SourceError
from .verifier import verify_document

__all__ = ["InputError", "Report", "SourceError", "verify_document"]
