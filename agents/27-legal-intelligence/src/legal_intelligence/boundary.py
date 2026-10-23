"""Bound JSON and local file authority before creating domain state.

Descriptor-relative traversal rejects symlinks at every path component. No source
text can request tools, writes, imports, or configuration changes.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
from typing import Any

MAX_BYTES = 32_768
MAX_DEPTH = 8


class InvalidInput(ValueError):
    """A bounded public failure code, never containing the supplied document."""


def read_local(path: str | Path) -> bytes:
    """Read one regular file without following links or blocking on a FIFO."""
    raw = os.fspath(path)
    if not raw or "\x00" in raw or ".." in Path(raw).parts:
        raise InvalidInput("invalid_path")
    absolute = Path(os.path.abspath(raw))
    descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in absolute.parts[1:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        leaf = os.open(absolute.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                       dir_fd=descriptor)
        try:
            metadata = os.fstat(leaf)
            if not stat.S_ISREG(metadata.st_mode):
                raise InvalidInput("regular_file_required")
            if metadata.st_size > MAX_BYTES:
                raise InvalidInput("input_too_large")
            # A bounded read also catches a file that grows after fstat.
            chunks = bytearray()
            while len(chunks) <= MAX_BYTES:
                piece = os.read(leaf, min(4096, MAX_BYTES + 1 - len(chunks)))
                if not piece:
                    break
                chunks.extend(piece)
            if len(chunks) > MAX_BYTES:
                raise InvalidInput("input_too_large")
            return bytes(chunks)
        finally:
            os.close(leaf)
    except OSError as error:
        raise InvalidInput("unreadable_regular_file") from error
    finally:
        os.close(descriptor)


def decode_json(raw: bytes, *, corpus: bool = False) -> Any:
    """Reject parser ambiguities, deep documents, and unsupported scalar types."""
    if len(raw) > MAX_BYTES:
        raise InvalidInput("input_too_large")
    try:
        document = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise InvalidInput("invalid_utf8") from error
    depth = 0
    quoted = escaped = False
    for character in document:
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
        elif character == '"':
            quoted = True
        elif character in "[{":
            depth += 1
            if depth > MAX_DEPTH:
                raise InvalidInput("nesting_limit")
        elif character in "]}":
            depth -= 1

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise InvalidInput("duplicate_key")
            result[key] = value
        return result

    def reject_constant(_: str) -> None:
        raise InvalidInput("nonfinite_number")

    try:
        value = json.loads(document, object_pairs_hook=pairs,
                           parse_constant=reject_constant)
    except (ValueError, RecursionError) as error:
        if isinstance(error, InvalidInput):
            raise
        raise InvalidInput("invalid_json") from error

    def inspect(item: Any) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                inspect(key)
                inspect(child)
        elif isinstance(item, list):
            for child in item:
                inspect(child)
        elif isinstance(item, str):
            if len(item) > 512 or any(0xD800 <= ord(c) <= 0xDFFF for c in item):
                raise InvalidInput("invalid_string")
        elif not (corpus and type(item) is int):
            raise InvalidInput("unsupported_scalar")
    inspect(value)
    return value


def fields(value: Any, required: set[str], optional: set[str] = frozenset()) -> dict[str, Any]:
    if not isinstance(value, dict) or not required <= value.keys() or value.keys() - required - optional:
        raise InvalidInput("object_fields")
    return value


def sequence(value: Any, minimum: int, maximum: int) -> list[Any]:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise InvalidInput("array_bounds")
    return value


def choice(value: Any, options: Any) -> str:
    if not isinstance(value, str) or value not in options:
        raise InvalidInput("unsupported_tag")
    return value


def identifier(value: Any) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 48 or not value.isascii():
        raise InvalidInput("invalid_identifier")
    if any(not (c.isalnum() or c in "_-") for c in value):
        raise InvalidInput("invalid_identifier")
    return value
