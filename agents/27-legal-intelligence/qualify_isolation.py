"""Reproduce fixture qualification in a case-only copy and an installed wheel.

Temporary workspaces are outside this checkout and removed after the run. The
wheel's tests and CLI execute with isolated Python, without source-tree imports.
Only local uv cache/build operations are permitted by the explicit offline flags.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def invoke(command: list[str], cwd: Path, environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, env=environment, capture_output=True,
                            text=True, timeout=90)
    if result.returncode:
        raise RuntimeError(f"Failed command {command!r}\n{result.stdout}\n{result.stderr}")
    return result


def verify_report(command: list[str], cwd: Path, environment: dict[str, str]) -> None:
    result = invoke(command, cwd, environment)
    report = json.loads(result.stdout)
    assert report["outcome"] == "simulated_reviewer_handoff"
    assert report["human_approval"] == "not_granted"
    assert report["uncovered_issues"] == []
    assert [x["authority_id"] for x in report["citation_findings"]] == ["ALD-101", "ALD-201"]
    assert all(x["passed"] for x in report["citation_findings"])


def main() -> None:
    source = Path(__file__).resolve().parent
    environment = dict(os.environ)
    for key in ("PYTHONPATH", "PYTHONHOME", "UV_PROJECT_ENVIRONMENT"):
        environment.pop(key, None)
    environment["UV_CACHE_DIR"] = "/tmp/agent-atlas-uv-cache"
    with tempfile.TemporaryDirectory(prefix="atlas-legal-qualification-") as directory:
        base = Path(directory).resolve()
        copied = base / "case"
        shutil.copytree(source, copied, ignore=shutil.ignore_patterns(
            ".venv", "dist", "__pycache__", "*.pyc", ".pytest_cache"))
        invoke(["uv", "sync", "--locked", "--offline"], copied, environment)
        copy_tests = invoke(["uv", "run", "--locked", "--offline", "python", "-I", "-m",
                             "unittest", "discover", "-s", "tests", "-v"], copied, environment)
        assert "Ran 24 tests" in copy_tests.stderr and "\nOK" in copy_tests.stderr
        verify_report(["uv", "run", "--locked", "--offline", "legal-intelligence"], copied, environment)
        invoke(["uv", "build", "--offline", "--wheel", "--out-dir", str(base / "wheels")], copied, environment)
        wheels = list((base / "wheels").glob("*.whl"))
        assert len(wheels) == 1
        installed = base / "installed"
        invoke(["uv", "venv", "--offline", "--python", sys.executable, str(installed)], base, environment)
        python = str(installed / "bin" / "python")
        invoke(["uv", "pip", "install", "--offline", "--python", python, str(wheels[0])], base, environment)
        outside = base / "outside"
        outside.mkdir()
        shutil.copytree(copied / "tests", outside / "tests")
        # Removing source makes accidental editable/source imports observable.
        shutil.rmtree(copied)
        package_path = invoke([python, "-I", "-c",
            "import legal_intelligence; print(legal_intelligence.__file__)"], outside, environment).stdout.strip()
        assert Path(package_path).is_relative_to(installed)
        installed_tests = invoke([python, "-I", "-m", "unittest", "discover", "-s", "tests", "-v"], outside, environment)
        assert "Ran 24 tests" in installed_tests.stderr and "\nOK" in installed_tests.stderr
        verify_report([python, "-I", "-m", "legal_intelligence"], outside, environment)
        verify_report([str(installed / "bin" / "legal-intelligence")], outside, environment)
        help_result = invoke([str(installed / "bin" / "legal-intelligence"), "--help"], outside, environment)
        assert "fictional" in help_result.stdout
    print("Passed: case-only copy (24 tests + CLI); installed wheel outside checkout (24 tests + module/console/help). Fixture mode only.")


if __name__ == "__main__":
    main()
