"""Case-local public library for synthetic typed categorical decision mechanics.

Use predict with JSON-shaped request and bound fixture dictionaries. Policy is
host-owned, Result is terminal and request-local, and every probability remains
explicitly synthetic. No callable live adapters or downstream effects exist.
"""

from .contracts import Policy, Result
from .runtime import predict

__all__ = ["Policy", "Result", "predict"]
