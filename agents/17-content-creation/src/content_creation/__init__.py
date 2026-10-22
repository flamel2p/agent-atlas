"""Compose two synthetic content artifacts through a bounded review loop.

The public API accepts an immutable Brief and returns an immutable RunResult.
Validation establishes agreement with packaged fixtures, never human approval.
"""

from .domain import Brief, InputError, RunResult, create_content

__all__ = ["Brief", "InputError", "RunResult", "create_content"]
