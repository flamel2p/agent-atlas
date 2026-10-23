"""Rerun source, copied-case, and installed-wheel synthetic qualification.

All staging lives in one temporary directory outside the repository. This script
is development tooling only; the runtime has no subprocess or installation API.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

CASE = Path(__file__).resolve().parents[1]


def run(command: list[str], cwd: Path, env: dict[str, str]) -> None:
    result = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, timeout=120)
    if result.returncode:
        raise RuntimeError(f"command failed: {command!r}\n{result.stdout}\n{result.stderr}")
    print(f"passed: {' '.join(command)}")
    if "unittest" in command:
        print(result.stderr.strip())


def check_cli(command: list[str], cwd: Path, env: dict[str, str]) -> None:
    result = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, timeout=30, check=True)
    report = json.loads(result.stdout)
    assert report["status"] == "completed"
    assert report["hypothesis"]["prediction"] == 10
    assert report["feedback"]["measured_mean"] == 9
    assert report["feedback"]["absolute_error"] == 1
    assert report["novelty"]["global"] == "unverified"
    assert not result.stderr
    print(f"passed CLI: {' '.join(command)}")


def main() -> None:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("VIRTUAL_ENV", None)
    env["UV_CACHE_DIR"] = env.get("UV_CACHE_DIR", "/tmp/agent-atlas-uv-cache")
    tests = ["-m", "unittest", "discover", "-s", "tests", "-v"]
    run([sys.executable, *tests], CASE, env)
    check_cli([sys.executable, "-m", "scientific_discovery"], CASE, env)
    with tempfile.TemporaryDirectory(prefix="atlas25-qualification-") as temporary:
        staging = Path(temporary)
        copied = staging / "case"
        shutil.copytree(CASE, copied, ignore=shutil.ignore_patterns(".venv", "__pycache__", "dist", "*.egg-info"))
        run(["uv", "run", "--offline", "--locked", "python", *tests], copied, env)
        check_cli([str(copied / ".venv/bin/python"), "-m", "scientific_discovery"], staging, env)
        wheels = staging / "wheels"
        run(["uv", "build", "--offline", "--wheel", "--out-dir", str(wheels)], copied, env)
        wheel = next(wheels.glob("*.whl"))
        environment = staging / "installed"
        run(["uv", "venv", "--offline", "--python", sys.executable, str(environment)], staging, env)
        python = environment / "bin/python"
        run(["uv", "pip", "install", "--offline", "--python", str(python), str(wheel)], staging, env)
        check_cli([str(environment / "bin/scientific-discovery")], staging, env)
        check_cli([str(python), "-m", "scientific_discovery"], staging, env)
        run([str(python), "-m", "unittest", "discover", "-s", str(copied / "tests"), "-v"], staging, env)
    print("Qualification passed. Fixture evidence only; temporary copies and environments removed.")


if __name__ == "__main__":
    main()
