"""Bound JSON and file authority before domain validation.

Only plain JSON values are accepted. Container depth counts the root as one.
Regular-file descriptors use no-follow and nonblocking open flags so a selected
FIFO or final-component symlink cannot turn a bounded read into an open-ended
operation. Directory aliases remain permitted. This module never writes files.
"""

import json
import math
import os
import stat
from importlib import resources

MAX_DOCUMENT_BYTES = 256 * 1024
MAX_DEPTH = 32
_MAX_NODES = MAX_DOCUMENT_BYTES


class InputError(ValueError):
    """A sanitized boundary failure, independent of private input contents."""

    def __init__(self) -> None:
        super().__init__("Input does not satisfy the recommendation contract.")


class ResourceError(Exception):
    """A fixed package resource could not be read."""


def check_json_value(value: object) -> None:
    """Reject cycles, excess depth, custom Python objects, and oversized values.

    The explicit stack avoids recursing through caller-controlled containers.
    Active ancestry detects cycles while permitting repeated acyclic values.
    Encoded size uses compact UTF-8 JSON, the direct API's document equivalent.
    """
    stack = [(value, 0, False)]
    active: set[int] = set()
    nodes = 0
    while stack:
        item, depth, leaving = stack.pop()
        if leaving:
            active.remove(id(item))
            continue
        nodes += 1
        if nodes > _MAX_NODES:
            raise InputError()
        kind = type(item)
        if kind in (dict, list):
            depth += 1
            if depth > MAX_DEPTH or id(item) in active or len(item) > _MAX_NODES:
                raise InputError()
            active.add(id(item))
            stack.append((item, depth, True))
            if kind is dict:
                for key, child in item.items():
                    if type(key) is not str or len(key) > MAX_DOCUMENT_BYTES:
                        raise InputError()
                    stack.append((key, depth, False))
                    stack.append((child, depth, False))
            else:
                stack.extend((child, depth, False) for child in item)
        elif kind is str:
            if len(item) > MAX_DOCUMENT_BYTES:
                raise InputError()
        elif kind is float:
            if not math.isfinite(item):
                raise InputError()
        elif kind not in (int, bool, type(None)):
            raise InputError()
    try:
        size = 0
        encoder = json.JSONEncoder(ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        for part in encoder.iterencode(value):
            size += len(part.encode("utf-8"))
            if size > MAX_DOCUMENT_BYTES:
                raise InputError()
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise InputError() from None


def decode_json(data: bytes) -> object:
    """Decode strict UTF-8 JSON after checking text nesting before the parser."""
    if len(data) > MAX_DOCUMENT_BYTES:
        raise InputError()
    try:
        source = data.decode("utf-8")
        depth = 0
        quoted = False
        escaped = False
        for char in source:
            if quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
            elif char in "[{":
                depth += 1
                if depth > MAX_DEPTH:
                    raise InputError()
            elif char in "]}":
                depth -= 1

        def unique_object(pairs: list[tuple[str, object]]) -> dict:
            result = {}
            for key, value in pairs:
                if key in result:
                    raise InputError()
                result[key] = value
            return result

        def invalid_constant(_: str) -> None:
            raise InputError()

        value = json.loads(source, object_pairs_hook=unique_object, parse_constant=invalid_constant)
        check_json_value(value)
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise InputError() from None


def read_request(path: str | os.PathLike) -> object:
    """Read only the explicitly selected regular file and at most 256 KiB + 1."""
    descriptor = None
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise InputError()
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = None
            data = stream.read(MAX_DOCUMENT_BYTES + 1)
        return decode_json(data)
    except (OSError, ValueError, TypeError):
        raise InputError() from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def read_resource(name: str) -> object:
    """Read a host-selected package resource without a caller-selected path."""
    try:
        resource = resources.files("recommendation").joinpath("data", name)
        return read_request(os.fspath(resource))
    except (OSError, TypeError, InputError):
        raise ResourceError() from None
