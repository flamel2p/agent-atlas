#!/usr/bin/env python3
"""Check the demo library's maintained structural conventions."""

import argparse
from datetime import date
import re
from pathlib import Path


STATUSES = {"planned", "in-progress", "demo-ready", "archived"}
EVIDENCE_MODES = {"fixture", "mocked-provider", "live-model", "deployment"}
ROOT_DIRS = {"agents", "templates", "docs", "scripts", ".agents", ".codex", ".github", ".git", ".vscode"}
ROOT_FILES = {"LICENSE", ".gitignore", ".gitattributes", ".editorconfig", ".DS_Store"}
GENERATED = {".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".next", "dist", "build", "coverage", "artifacts", "private-data"}


def metadata(text, key):
    match = re.search(rf"^{re.escape(key)}:\s*(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else None


def is_inside(path, directory):
    return path.resolve().is_relative_to(directory.resolve())


def audit(root):
    errors = []
    for name in ("README.md", "AGENTS.md", "CONTRIBUTING.md"):
        if not (root / name).is_file():
            errors.append(f"Missing root document: {name}")

    for path in root.iterdir():
        allowed = path.name in (ROOT_DIRS if path.is_dir() else ROOT_FILES)
        if path.is_file() and path.suffix.lower() == ".md":
            allowed = True
        if not allowed:
            errors.append(f"Unexpected root item: {path.name}; keep application resources inside their case")

    cases_dir = root / "agents"
    if not cases_dir.is_dir():
        return errors + ["Missing agents/ directory"]
    if not is_inside(cases_dir, root):
        return errors + ["agents/ resolves outside the repository"]
    catalogue = (root / "README.md").read_text() if (root / "README.md").is_file() else ""
    cases = []
    for path in sorted(cases_dir.iterdir()):
        if path.name == ".DS_Store":
            continue
        if path.is_dir() and not path.name.startswith(".") and not path.is_symlink():
            cases.append(path)
        else:
            errors.append(f"Unowned agents/ item: {path.name}; use a physical case directory")
    if not cases:
        errors.append("No case directories found")

    for case in cases:
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", case.name):
            errors.append(f"Invalid kebab-case slug: {case.name}")
        if not is_inside(case, cases_dir):
            errors.append(f"Case directory resolves outside agents/: {case.name}")
            continue
        documents = {}
        for name in ("README.md", "AGENTS.md", "SPEC.md"):
            path = case / name
            if not path.is_file():
                errors.append(f"{case.name}: missing {name}")
            elif not is_inside(path, case):
                errors.append(f"{case.name}: {name} resolves outside its case")
            else:
                documents[name] = path.read_text()

        for name in ("README.md", "SPEC.md"):
            if name not in documents:
                continue
            text = documents[name]
            if metadata(text, "Slug") != case.name:
                errors.append(f"{case.name}: {name} Slug must match its directory")
            if metadata(text, "Status") not in STATUSES:
                errors.append(f"{case.name}: {name} has a missing or invalid Status")
            if not metadata(text, "Runtime"):
                errors.append(f"{case.name}: {name} must state its Runtime or undecided")
            if "AGENT_TITLE" in text or "agent-slug" in text:
                errors.append(f"{case.name}: {name} contains template placeholders")

        readme = documents.get("README.md", "")
        spec = documents.get("SPEC.md", "")
        if readme and spec:
            for key in ("Status", "Runtime"):
                if metadata(readme, key) != metadata(spec, key):
                    errors.append(f"{case.name}: README and SPEC {key} disagree")
        if "## Verification" not in readme:
            errors.append(f"{case.name}: README needs a Verification section")
        if "## Acceptance criteria" not in spec:
            errors.append(f"{case.name}: SPEC needs an Acceptance criteria section")
        if f"agents/{case.name}/README.md" not in catalogue:
            errors.append(f"{case.name}: missing README link in root catalogue")

        for path in case.rglob("*"):
            relative = path.relative_to(case)
            if any(part in GENERATED for part in relative.parts):
                continue
            if path.is_symlink() and not is_inside(path, case):
                errors.append(f"{case.name}: resource resolves outside its case: {relative}")

        if metadata(readme, "Status") == "demo-ready":
            if metadata(readme, "Runtime") == "undecided":
                errors.append(f"{case.name}: demo-ready requires a selected Runtime")
            for name in ("src", "tests"):
                directory = case / name
                if not directory.is_dir() or not any(p.is_file() and not p.name.startswith(".") for p in directory.rglob("*")):
                    errors.append(f"{case.name}: demo-ready requires nonempty {name}/")
            if "Not implemented or run" in readme:
                errors.append(f"{case.name}: demo-ready conflicts with initial verification marker")
            try:
                date.fromisoformat(metadata(readme, "Verified on") or "")
            except ValueError:
                errors.append(f"{case.name}: demo-ready requires Verified on in YYYY-MM-DD format")
            command = metadata(readme, "Verification command") or ""
            scope = metadata(readme, "Verified scope") or ""
            if not command or command.lower() in {"undecided", "unverified", "none"}:
                errors.append(f"{case.name}: demo-ready requires a recorded Verification command")
            if metadata(readme, "Verification mode") not in EVIDENCE_MODES:
                errors.append(f"{case.name}: demo-ready requires an explicit Verification mode")
            if metadata(readme, "Verification result") != "passed":
                errors.append(f"{case.name}: demo-ready requires a recorded passed Verification result")
            if not scope or scope.lower() in {"undecided", "unverified", "none"}:
                errors.append(f"{case.name}: demo-ready requires a recorded Verified scope")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    root = parser.parse_args().root.resolve()
    if not root.is_dir():
        parser.error(f"Repository root does not exist: {root}")
    errors = audit(root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("PASS: repository structure and case metadata")
    print("Recorded verification metadata is not proof that checks ran; runtime behavior, dependency isolation, and live-model quality require separate evidence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
