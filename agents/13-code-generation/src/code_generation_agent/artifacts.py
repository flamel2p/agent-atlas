"""Host-only workspace ownership and exclusive artifact publication.

Every run owns a new directory beneath a physical case workspace. Markers prevent
accidental writes to other projects; they do not authenticate a malicious local
operator. Files are flushed and synced before the terminal report is linked into
place atomically without replacing an existing name. That link is the completion
point. This is not a crash-recovery or hostile concurrent-filesystem protocol.
"""

from dataclasses import asdict
import os
from pathlib import Path
import re
import tomllib
from uuid import uuid4

from .domain import Attempt, RunResult, json_text
from .interpreter import source_bytes

PROJECT_NAME = "agent-atlas-13-code-generation"
SLUG = "13-code-generation"
MAX_JSON_BYTES = 262_144


class InvalidInput(ValueError):
    """A normalized caller error detected before creating a run."""


class ArtifactError(OSError):
    """An artifact operation failed; no exception text or private data is echoed."""


def _physical(path: Path) -> Path:
    # Reject traversal before normalization can erase a symlink component.
    if ".." in path.parts:
        raise InvalidInput("workspace_escape")
    absolute = Path(os.path.abspath(path))
    if any(component.is_symlink() for component in (absolute, *absolute.parents)):
        raise InvalidInput("symlink_path")
    if absolute.resolve() != absolute:
        raise InvalidInput("workspace_escape")
    return absolute


def validate_workspace(workspace: Path | str) -> Path:
    """Require bounded physical SPEC/pyproject markers before any artifact write."""
    try:
        root = _physical(Path(workspace))
        markers = (root / "SPEC.md", root / "pyproject.toml")
        if not root.is_dir() or any(
            marker.is_symlink() or not marker.is_file() or marker.stat().st_size > 65_536
            for marker in markers
        ):
            raise InvalidInput("workspace_markers")
        specification = markers[0].read_text(encoding="utf-8")
        metadata = tomllib.loads(markers[1].read_text(encoding="utf-8"))
        if (
            re.findall(r"^Slug: (.+)$", specification, re.MULTILINE) != [SLUG]
            or metadata.get("project", {}).get("name") != PROJECT_NAME
        ):
            raise InvalidInput("workspace_markers")
        artifact_root = root / "artifacts"
        if artifact_root.is_symlink() or (artifact_root.exists() and not artifact_root.is_dir()):
            raise InvalidInput("artifact_root")
        return root
    except InvalidInput:
        raise
    except (OSError, ValueError, TypeError, AttributeError):
        raise InvalidInput("workspace_markers") from None


class ArtifactStore:
    def __init__(self, workspace: Path | str, run_id: str | None = None):
        root = validate_workspace(workspace)
        identifier = uuid4().hex if run_id is None else run_id
        if type(identifier) is not str or re.fullmatch(r"[A-Za-z0-9_-]{1,64}", identifier) is None:
            raise InvalidInput("run_id")
        artifact_root = root / "artifacts"
        destination = artifact_root / identifier
        if destination.exists() or destination.is_symlink():
            raise InvalidInput("existing_run")
        try:
            artifact_root.mkdir(mode=0o700, exist_ok=True)
            destination.mkdir(mode=0o700, exist_ok=False)
        except OSError:
            raise ArtifactError("artifact_create") from None
        self.directory = destination
        self._published = False

    @property
    def published(self) -> bool:
        if self._published:
            return True
        # A signal can arrive after link(2) commits but before Python assigns
        # _published. Matching inodes closes that completion-point gap.
        try:
            self._published = (self.directory / ".report.tmp").samefile(self.directory / "report.json")
            return self._published
        except OSError:
            return False

    @staticmethod
    def _write(path: Path, data: bytes) -> None:
        if len(data) > MAX_JSON_BYTES:
            raise ArtifactError("artifact_size")
        with path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())

    def record(self, attempt: Attempt, source: str | None) -> None:
        """Persist validated source and feedback; None records metadata only."""
        if type(attempt.number) is not int or not 1 <= attempt.number <= 3:
            raise ArtifactError("attempt_number")
        directory = self.directory / f"attempt-{attempt.number}"
        try:
            directory.mkdir(mode=0o700, exist_ok=False)
            if source is not None:
                self._write(directory / "candidate.txt", source_bytes(source))
            self._write(directory / "feedback.json", json_text(asdict(attempt)).encode("utf-8"))
        except OSError:
            raise ArtifactError("artifact_write") from None

    def publish(self, result: RunResult) -> None:
        """Publish once; after the atomic link no later interruption changes its status."""
        temporary = self.directory / ".report.tmp"
        final = self.directory / "report.json"
        try:
            self._write(temporary, json_text(asdict(result)).encode("utf-8"))
            os.link(temporary, final)
            self._published = True
        except OSError:
            raise ArtifactError("report_write") from None
        finally:
            # Publication already committed. A cleanup failure must not turn a
            # durable completed report into a contradictory failed CLI result.
            if self.published:
                try:
                    temporary.unlink(missing_ok=True)
                except (OSError, KeyboardInterrupt):
                    pass
