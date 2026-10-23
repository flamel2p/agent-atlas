"""Re-run fixture qualification in an isolated case copy and installed wheel.

Temporary directories are outside the checkout and removed on completion. uv
runs offline with the selected interpreter/build backend, so this establishes
local package isolation rather than live-provider or deployment readiness.
"""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


CASE = Path(__file__).resolve().parent


def execute(command: list[str], cwd: Path, env: dict[str, str], raw: bytes | None = None) -> bytes:
    completed = subprocess.run(command, input=raw, cwd=cwd, env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    if completed.returncode:
        raise RuntimeError(f"Qualification command failed: {command[0:3]}\n"
                           + completed.stderr.decode(errors="replace")[-2000:])
    return completed.stdout + completed.stderr


def test_suite(python: Path, cwd: Path, tests: Path, env: dict[str, str]) -> int:
    output = execute([str(python), "-m", "unittest", "discover", "-s", str(tests), "-v"], cwd, env)
    match = re.search(rb"Ran (\d+) tests", output)
    if match is None or int(match[1]) == 0 or not output.rstrip().endswith(b"OK"):
        raise RuntimeError("Qualification did not execute a passing test suite")
    return int(match[1])


def console(executable: Path, cwd: Path, fixtures: Path, env: dict[str, str]) -> dict[str, str]:
    statuses = {}
    for name in ("baseline", "replay", "missing-reviewer", "conflicting-scores", "threshold-tie"):
        output = execute([str(executable)], cwd, env, (fixtures / f"{name}.json").read_bytes())
        report = json.loads(output)
        expected = "converged" if name in ("baseline", "replay") else "unresolved"
        if report["status"] != expected or report["correctness_claim"] is not False:
            raise RuntimeError("Unexpected fixture result")
        statuses[name] = report["status"]
    return statuses


def main() -> None:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["UV_CACHE_DIR"] = "/tmp/agent-atlas-uv-cache"
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv is required")
    with tempfile.TemporaryDirectory(prefix="atlas29-qualification-") as directory:
        outside = Path(directory)
        copied = outside / "case"
        shutil.copytree(CASE, copied, ignore=shutil.ignore_patterns(".venv", "__pycache__", "dist", "*.pyc"))
        execute([uv, "sync", "--offline", "--frozen", "--python", "3.14.8"], copied, env)
        copy_tests = test_suite(copied / ".venv/bin/python", outside, copied / "tests", env)
        copy_cli = console(copied / ".venv/bin/collective-intelligence", outside, copied / "fixtures", env)
        wheels = outside / "wheels"
        execute([uv, "build", "--offline", "--python", "3.14.8", "--wheel", "--out-dir", str(wheels)], copied, env)
        wheel = next(wheels.glob("*.whl"))
        wheel_env = outside / "installed"
        execute([uv, "venv", "--offline", "--python", "3.14.8", str(wheel_env)], outside, env)
        python = wheel_env / "bin/python"
        execute([uv, "pip", "install", "--offline", "--python", str(python), "--no-deps", str(wheel)], outside, env)
        imported = execute([str(python), "-c", "import collective_intelligence; print(collective_intelligence.__file__)"], outside, env)
        if not Path(imported.decode().strip()).is_relative_to(wheel_env):
            raise RuntimeError("Import escaped installed wheel environment")
        wheel_tests = test_suite(python, outside, copied / "tests", env)
        wheel_cli = console(wheel_env / "bin/collective-intelligence", outside, copied / "fixtures", env)
        version = execute([str(python), "--version"], outside, env).decode().strip()
        print(json.dumps({"mode": "fixture", "python": version, "case_copy_tests": copy_tests,
                          "case_copy_cli": copy_cli, "wheel_tests": wheel_tests,
                          "wheel_cli": wheel_cli, "wheel_import_isolated": True}, indent=2))


if __name__ == "__main__":
    main()
