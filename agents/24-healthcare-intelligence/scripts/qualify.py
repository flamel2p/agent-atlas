"""Rerunnable local fixture qualification, with no repository-root runtime inputs.

Copy the case alone, run its tests and real CLI, build its wheel, install it into
another environment, then run the same behavioral checks outside the checkout.
Temporary artifacts are deleted when the command exits, including on failure.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


def command(args: list[str], cwd: Path, env: dict[str, str]) -> str:
    result = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {args!r}\n{result.stdout}\n{result.stderr}")
    return result.stdout + result.stderr


def check_cli(args: list[str], cwd: Path, env: dict[str, str]) -> None:
    report = json.loads(command(args, cwd, env))
    assert report["mode"] == "fixture"
    assert report["outcome"] == "review_required"
    assert [item["exact"] for item in report["posterior"]] == ["20/23", "3/46", "3/46"]
    assert report["review"] == {"decision": "pending", "effect": "none", "real_approval": False}
    assert len(report["evidence"]) == 2


def suite_count(output: str) -> int:
    match = re.search(r"Ran (\d+) tests", output)
    assert match is not None and int(match[1]) > 0, output
    return int(match[1])


def main() -> None:
    case = Path(__file__).resolve().parents[1]
    uv = shutil.which("uv")
    if not uv:
        raise RuntimeError("uv is required for local packaging qualification")
    env = os.environ.copy()
    for name in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT"):
        env.pop(name, None)
    env["PYTHONNOUSERSITE"] = "1"
    env.setdefault("UV_CACHE_DIR", "/tmp/agent-atlas-uv-cache")
    with tempfile.TemporaryDirectory(prefix="atlas-healthcare-qualification-") as directory:
        outside = Path(directory)
        copied = outside / "case"
        shutil.copytree(case, copied, ignore=shutil.ignore_patterns(".venv", "__pycache__", "dist", "*.pyc"))
        command([uv, "sync", "--offline", "--locked", "--project", str(copied)], outside, env)
        copy_python = copied / ".venv/bin/python"
        copy_tests = command([str(copy_python), "-I", "-m", "unittest", "discover", "-s", str(copied / "tests")], outside, env)
        copy_count = suite_count(copy_tests)
        check_cli([str(copied / ".venv/bin/healthcare-intelligence")], outside, env)
        print(f"Case-only copy: {copy_count} tests and actual console CLI passed outside the repository.")

        wheels = outside / "wheels"
        command([uv, "build", "--wheel", "--offline", "--out-dir", str(wheels), str(copied)], outside, env)
        wheel_paths = list(wheels.glob("*.whl"))
        assert len(wheel_paths) == 1
        wheel_env = outside / "installed"
        command([uv, "venv", "--python", sys.executable, str(wheel_env)], outside, env)
        wheel_python = wheel_env / "bin/python"
        command([uv, "pip", "install", "--offline", "--python", str(wheel_python), "--no-deps", str(wheel_paths[0])], outside, env)
        imported = command([str(wheel_python), "-I", "-c", "import healthcare_intelligence; print(healthcare_intelligence.__file__)"], outside, env).strip()
        assert str(wheel_env) in imported and str(copied) not in imported, imported
        wheel_tests = command([str(wheel_python), "-I", "-m", "unittest", "discover", "-s", str(copied / "tests")], outside, env)
        wheel_count = suite_count(wheel_tests)
        assert wheel_count == copy_count
        check_cli([str(wheel_env / "bin/healthcare-intelligence")], outside, env)
        command([str(wheel_env / "bin/healthcare-intelligence"), "--help"], outside, env)
        print(f"Installed wheel: {wheel_count} tests, actual console CLI, help, packaged fixture, and import isolation passed.")
        print(f"Fixture qualification passed on Python {sys.version.split()[0]}. No provider or deployment validation.")


if __name__ == "__main__":
    main()
