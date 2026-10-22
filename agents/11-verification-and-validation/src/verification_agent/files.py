"""Read bounded regular files without following the final path component.

O_NONBLOCK prevents FIFO opens from waiting before fstat can reject them.
O_NOFOLLOW closes the final-component symlink race. These checks are input
hygiene; parent directories and the installed package are not an OS sandbox.
"""

import os
from pathlib import Path
import stat

from .domain import VerificationError

REQUEST_LIMIT = 65_536
SNAPSHOT_LIMIT = 262_144


def read_regular(path: Path | str, limit: int, error: type[VerificationError]) -> bytes:
    """Read at most limit + 1 bytes, closing the descriptor on every exit path."""
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise error("not_regular_file")
            if metadata.st_size > limit:
                raise error("too_large")
            chunks = []
            remaining = limit + 1
            while remaining:
                chunk = os.read(descriptor, min(remaining, 65_536))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            if remaining == 0:
                raise error("too_large")
            return b"".join(chunks)
        finally:
            os.close(descriptor)
    except (OSError, ValueError, TypeError):
        raise error("unreadable_file") from None
