"""Public document boundary and immutable result type for the scheduling demo."""

from .domain import InputError, Report
from .solver import solve_document

__all__ = ["InputError", "Report", "solve_document"]
