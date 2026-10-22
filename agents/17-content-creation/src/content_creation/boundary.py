"""Read and validate caller JSON and the fixed packaged evidence snapshot.

All reads are bounded. Brief files are opened without following a final symlink
and nonblocking so a raced special file cannot hang the process. Resource
names are selected by code, never supplied by a brief. No read grants writes.
"""

import hashlib
from importlib.resources import files
import json
import os
from pathlib import Path
import re
import stat
import unicodedata

from .domain import (
    AudiencePriority, Brief, CHANNELS, COPY_SLOTS, Copy, Fact, FixtureError,
    InputError, Snapshot, Source, safe_text,
)

BRIEF_MAX_BYTES = 16 * 1024
FIXTURE_MAX_BYTES = 32 * 1024
SCENARIOS = ("launch", "relaxed", "exhausted", "length-repair", "impossible-length", "mixed")
BRIEF_FIELDS = {"audience", "required_fact_ids", "forbidden_phrases", "email_max_words", "docs_max_words"}
IDENTITY = re.compile(r"[a-z][a-z0-9_]{0,39}\Z")


def _invalid(*_: object) -> None:
    raise InputError("JSON contains an unsupported numeric value.")


def _integer(token: str) -> int:
    if len(token) > 20:
        raise InputError("JSON integer exceeds the supported size.")
    return int(token)


def _object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError("JSON contains duplicate object keys.")
        result[key] = value
    return result


def strict_json(raw: bytes, limit: int) -> object:
    """Reject ambiguous syntax and unsupported Unicode before schema validation."""
    if len(raw) > limit:
        raise InputError("JSON input exceeds the byte limit.")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_object,
                           parse_constant=_invalid, parse_float=_invalid, parse_int=_integer)
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as error:
        if isinstance(error, InputError):
            raise
        raise InputError("Input must be bounded valid UTF-8 JSON.") from None
    pending = [(value, 0)]
    count = 0
    while pending:
        item, depth = pending.pop()
        count += 1
        if depth > 16 or count > 4096:
            raise InputError("JSON nesting or item count exceeds the supported limit.")
        if isinstance(item, dict):
            pending.extend((child, depth + 1) for pair in item.items() for child in pair)
        elif isinstance(item, list):
            pending.extend((child, depth + 1) for child in item)
        elif isinstance(item, str):
            if any(unicodedata.category(char) in {"Cc", "Cs"} and char not in "\t\n\r" for char in item):
                raise InputError("JSON contains unsupported control or surrogate characters.")
    return value


def brief_from_bytes(raw: bytes) -> Brief:
    value = strict_json(raw, BRIEF_MAX_BYTES)
    if type(value) is not dict or set(value) != BRIEF_FIELDS:
        raise InputError("Brief fields do not match the required schema.")
    if type(value["required_fact_ids"]) is not list or type(value["forbidden_phrases"]) is not list:
        raise InputError("Fact IDs and forbidden phrases must be JSON arrays.")
    return Brief(value["audience"], tuple(value["required_fact_ids"]),
                 tuple(value["forbidden_phrases"]), value["email_max_words"], value["docs_max_words"])


def load_brief_file(path: str | os.PathLike[str]) -> Brief:
    """Read one regular file without following a symlink at the selected filename.

    Directory aliases, including macOS /tmp, are allowed. The selected file must
    remain the same regular inode between inspection and opening.
    """
    directory_fd = None
    file_fd = None
    try:
        selected = Path(path)
        if not selected.name:
            raise InputError("Brief path must name a regular file.")
        directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
        directory_fd = os.open(selected.parent, directory_flags)
        inspected = os.stat(selected.name, dir_fd=directory_fd, follow_symlinks=False)
        if not stat.S_ISREG(inspected.st_mode) or inspected.st_size > BRIEF_MAX_BYTES:
            raise InputError("Brief must be a regular file within the byte limit.")
        file_fd = os.open(selected.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                          dir_fd=directory_fd)
        opened = os.fstat(file_fd)
        if (not stat.S_ISREG(opened.st_mode) or opened.st_size > BRIEF_MAX_BYTES
                or (opened.st_dev, opened.st_ino) != (inspected.st_dev, inspected.st_ino)):
            raise InputError("Brief file changed or is not a bounded regular file.")
        chunks = bytearray()
        while len(chunks) <= BRIEF_MAX_BYTES:
            chunk = os.read(file_fd, BRIEF_MAX_BYTES + 1 - len(chunks))
            if not chunk:
                break
            chunks.extend(chunk)
        return brief_from_bytes(bytes(chunks))
    except (OSError, TypeError, ValueError) as error:
        if isinstance(error, InputError):
            raise
        raise InputError("Unable to read a regular brief file safely.") from None
    finally:
        if file_fd is not None:
            os.close(file_fd)
        if directory_fd is not None:
            os.close(directory_fd)


def _resource_bytes(*names: str) -> bytes:
    limit = FIXTURE_MAX_BYTES if names == ("content.json",) else BRIEF_MAX_BYTES
    with files("content_creation").joinpath("data", *names).open("rb") as resource:
        return resource.read(limit + 1)


def load_scenario(name: str) -> Brief:
    if name not in SCENARIOS:
        raise InputError("Unknown packaged scenario.")
    try:
        return brief_from_bytes(_resource_bytes("briefs", name + ".json"))
    except (OSError, InputError) as error:
        raise FixtureError("Packaged brief is missing or invalid.") from None


def _require(condition: bool) -> None:
    if not condition:
        raise FixtureError("Packaged content fixture is invalid.")


def _fields(value: object, expected: set[str]) -> bool:
    return type(value) is dict and set(value) == expected


def _fixture_text(value: object, maximum: int) -> bool:
    return safe_text(value, max_length=maximum) and value == value.strip()


def _identity(value: object) -> bool:
    return type(value) is str and IDENTITY.fullmatch(value) is not None


def snapshot_from_bytes(raw: bytes) -> Snapshot:
    """Validate identities, references, and bounds before creating immutable values."""
    try:
        data = strict_json(raw, FIXTURE_MAX_BYTES)
    except InputError:
        raise FixtureError("Packaged content fixture is invalid.") from None
    _require(_fields(data, {"product", "sources", "facts", "copy", "priorities"}))
    _require(_fixture_text(data["product"], 60))
    _require(type(data["sources"]) is list and 1 <= len(data["sources"]) <= 6)
    sources = []
    for entry in data["sources"]:
        _require(_fields(entry, {"id", "title"}))
        _require(_identity(entry["id"]) and _fixture_text(entry["title"], 100))
        sources.append(Source(entry["id"], entry["title"]))
    source_ids = {source.id for source in sources}
    _require(len(source_ids) == len(sources))
    _require(type(data["facts"]) is list and 1 <= len(data["facts"]) <= 6)
    facts = []
    for entry in data["facts"]:
        _require(_fields(entry, {"id", "source_id", "text"}))
        _require(_identity(entry["id"]) and _identity(entry["source_id"]))
        _require(entry["source_id"] in source_ids and _fixture_text(entry["text"], 240))
        _require(entry["text"].startswith(data["product"] + " ") and entry["text"].endswith("."))
        facts.append(Fact(entry["id"], entry["source_id"], entry["text"]))
    fact_ids = {fact.id for fact in facts}
    _require(len(fact_ids) == len(facts) and len({fact.text for fact in facts}) == len(facts))
    _require(_fields(data["copy"], set(CHANNELS)))
    copies = []
    for kind in CHANNELS:
        _require(_fields(data["copy"][kind], set(COPY_SLOTS)))
        variants = []
        for slot in COPY_SLOTS:
            values = data["copy"][kind][slot]
            _require(type(values) is list and 1 <= len(values) <= 6)
            _require(all(_fixture_text(value, 200) for value in values))
            _require(len(set(values)) == len(values))
            variants.append(tuple(values))
        copies.append(Copy(kind, tuple(variants)))
    _require(_fields(data["priorities"], {"team_leads", "developers"}))
    priorities = []
    for audience in ("team_leads", "developers"):
        entries = data["priorities"][audience]
        _require(type(entries) is list and len(entries) == len(facts))
        ranked = []
        for entry in entries:
            _require(_fields(entry, {"fact_id", "rank"}))
            _require(_identity(entry["fact_id"]) and entry["fact_id"] in fact_ids)
            _require(type(entry["rank"]) is int and 0 <= entry["rank"] <= 100)
            ranked.append((entry["rank"], entry["fact_id"]))
        _require({fact_id for _, fact_id in ranked} == fact_ids)
        priorities.append(AudiencePriority(audience, tuple(fact_id for _, fact_id in sorted(ranked))))
    return Snapshot(data["product"], tuple(sources), tuple(facts), tuple(copies), tuple(priorities),
                    hashlib.sha256(raw).hexdigest())


def load_snapshot() -> Snapshot:
    # This is the single fixture read for a run; hashing and validation share bytes.
    try:
        return snapshot_from_bytes(_resource_bytes("content.json"))
    except OSError:
        raise FixtureError("Packaged content fixture is unavailable.") from None
