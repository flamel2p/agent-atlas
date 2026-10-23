"""Prove case isolation using a temporary copy and an independently installed wheel.

All subprocess commands are argument arrays. No network is used. Temporary copies,
build products, and environments are removed when this verification ends.
"""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

CASE = Path(__file__).resolve().parents[1]


def execute(command: list[str], cwd: Path, env: dict[str, str], expected: int = 0) -> str:
    process = subprocess.run(command, cwd=cwd, env=env, capture_output=True,
                             text=True, timeout=120)
    if process.returncode != expected:
        raise RuntimeError(f"command failed: {command!r}\n{process.stdout}\n{process.stderr}")
    return process.stdout + process.stderr


def check_cli(executable: Path, fixture: Path, cwd: Path, env: dict[str, str],
              expected_code: int, expected_status: str, expected_effects: int) -> None:
    output = json.loads(execute([str(executable), str(fixture)], cwd, env, expected_code))
    assert output["status"] == expected_status, output
    assert len(output["effects"]) == expected_effects, output


def check_tests(python: Path, case: Path, cwd: Path, env: dict[str, str], label: str) -> None:
    output = execute([str(python), "-I", "-m", "unittest", "discover", "-s", str(case / "tests"), "-v"], cwd, env)
    count = re.search(r"Ran (\d+) tests?", output)
    assert count and "\nOK\n" in output, output
    print(f"{label}: {count.group(1)} tests passed")


def main() -> None:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("VIRTUAL_ENV", None)
    env.setdefault("UV_CACHE_DIR", "/tmp/agent-atlas-uv-cache")
    with tempfile.TemporaryDirectory(prefix="ethical-reasoning-") as temporary:
        root = Path(temporary)
        copy = root / "case"
        shutil.copytree(CASE, copy, ignore=shutil.ignore_patterns(".venv", "__pycache__", "dist", "*.pyc"))
        execute(["uv", "sync", "--offline", "--locked"], copy, env)
        check_tests(copy / ".venv/bin/python", copy, copy, env, "case-only copy")
        check_cli(copy / ".venv/bin/ethical-reasoning", copy / "fixtures/allowed.json", copy, env, 0, "completed", 1)
        check_cli(copy / ".venv/bin/ethical-reasoning", copy / "fixtures/forbidden.json", copy, env, 3, "review_required", 0)
        wheel_dir = root / "wheels"
        execute(["uv", "build", "--offline", "--wheel", "--out-dir", str(wheel_dir)], copy, env)
        wheels = list(wheel_dir.glob("*.whl"))
        assert len(wheels) == 1, wheels
        installed = root / "installed"
        execute(["uv", "venv", "--python", sys.executable, str(installed)], root, env)
        python = installed / "bin/python"
        execute(["uv", "pip", "install", "--offline", "--python", str(python), str(wheels[0])], root, env)
        location = execute([str(python), "-I", "-c", "import ethical_reasoning; print(ethical_reasoning.__file__)"], root, env)
        assert Path(location.strip()).is_relative_to(installed), location
        check_tests(python, copy, root, env, "installed wheel outside repository")
        check_cli(installed / "bin/ethical-reasoning", copy / "fixtures/redact.json", root, env, 0, "completed", 1)
        check_cli(installed / "bin/ethical-reasoning", copy / "fixtures/disparity.json", root, env, 3, "review_required", 0)
        print("case-copy and installed-wheel CLI outcomes passed; temporary artifacts removed on exit")


if __name__ == "__main__":
    main()
