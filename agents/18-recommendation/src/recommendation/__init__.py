"""One-call recommendation API with no persistent state or external actions."""

from .documents import InputError
from .domain import recommend

__all__ = ["InputError", "recommend"]
