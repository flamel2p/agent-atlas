"""Bound JSON and explicit-file reads before any adapter process is launched.

Numbers stay Decimal, so the host never changes a supplied probability through
binary floating-point conversion. Files are caller-selected read-only inputs;
no component of an explicit path may be a symlink, and FIFOs cannot block reads.
"""

import json
import os
import stat
from decimal import Decimal, InvalidOperation
from pathlib import Path

MAX_BYTES = 65_536
MAX_DEPTH = 8


class Invalid(ValueError):
    """A sanitized boundary failure; the message is a fixed host-owned code."""


def number(token: str) -> Decimal:
    if len(token) > 64:
        raise Invalid("number_limit")
    try:
        value = Decimal(token)
    except InvalidOperation:
        raise Invalid("invalid_number") from None
    if not value.is_finite() or not -1000 <= value.adjusted() <= 1000:
        raise Invalid("invalid_number")
    return value


def _pairs(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise Invalid("duplicate_key")
        result[key] = value
    return result


def loads(data: bytes) -> object:
    """Parse strict UTF-8 JSON with bounded nesting and duplicate detection."""
    if type(data) is not bytes or len(data) > MAX_BYTES:
        raise Invalid("json_byte_limit")
    try:
        source = data.decode("utf-8", errors="strict")
        depth, quoted, escaped = 0, False, False
        # Scan before json.loads, whose own recursion limit is much larger.
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
                    raise Invalid("json_depth_limit")
            elif char in "]}":
                depth -= 1
        return json.loads(source, object_pairs_hook=_pairs, parse_float=number,
                          parse_int=number, parse_constant=lambda _: _bad_constant())
    except (UnicodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, Invalid):
            raise
        raise Invalid("malformed_json") from None


def _bad_constant():
    raise Invalid("invalid_number")


def dumps(value: object) -> str:
    """Emit exact Decimal probability tokens and bounded trusted result trees."""
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise Invalid("invalid_number")
        return str(value)
    if isinstance(value, dict):
        return "{" + ",".join(json.dumps(k, ensure_ascii=False) + ":" + dumps(v)
                              for k, v in value.items()) + "}"
    if isinstance(value, (tuple, list)):
        return "[" + ",".join(dumps(v) for v in value) + "]"
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def snapshot(value: object) -> object:
    """Apply the JSON byte/depth/type limits to in-memory library fixtures too."""
    pending = [(value, 0)]
    budget = 0
    while pending:
        item, depth = pending.pop()
        kind = type(item)
        if kind in (dict, list):
            depth += 1
            if depth > MAX_DEPTH:
                raise Invalid("json_depth_limit")
            budget += 2 + max(0, len(item) - 1)
            if len(item) > MAX_BYTES:
                raise Invalid("json_byte_limit")
            if kind is dict:
                for key, child in item.items():
                    if type(key) is not str or len(key) > MAX_BYTES:
                        raise Invalid("invalid_fields")
                    budget += _utf8_size(json.dumps(key, ensure_ascii=False)) + 1
                    pending.append((child, depth))
            else:
                pending.extend((child, depth) for child in item)
        elif kind is str:
            if len(item) > MAX_BYTES:
                raise Invalid("json_byte_limit")
            budget += _utf8_size(json.dumps(item, ensure_ascii=False))
        elif kind in (int, float, Decimal):
            budget += len(str(number(str(item))))
        elif item is None or kind is bool:
            budget += len(dumps(item))
        else:
            raise Invalid("invalid_json_type")
        if budget > MAX_BYTES:
            raise Invalid("json_byte_limit")
    return loads(dumps(value).encode("utf-8"))


def _utf8_size(value: str) -> int:
    try:
        return len(value.encode("utf-8"))
    except UnicodeError:
        raise Invalid("invalid_text") from None


def read_file(path: str | Path) -> bytes:
    """Open each path component relative to a held directory descriptor.

    O_NOFOLLOW closes the usual check/open race. O_NONBLOCK prevents a FIFO
    substituted at the leaf from hanging before fstat rejects its file type.
    macOS and Linux with POSIX dir_fd support are the selected platforms.
    """
    try:
        if ".." in Path(path).parts:
            raise Invalid("invalid_file")
        parts = Path(os.path.abspath(path)).parts
        directory = os.open(parts[0], os.O_RDONLY | os.O_DIRECTORY)
        try:
            for part in parts[1:-1]:
                following = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                    dir_fd=directory)
                os.close(directory)
                directory = following
            fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                         dir_fd=directory)
            with os.fdopen(fd, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
                    raise Invalid("invalid_file")
                data = stream.read(MAX_BYTES + 1)
                if len(data) > MAX_BYTES:
                    raise Invalid("json_byte_limit")
                return data
        finally:
            os.close(directory)
    except (OSError, ValueError, TypeError):
        raise Invalid("invalid_file") from None
