"""Rerun source, case-copy, and installed-wheel qualification outside the checkout.

The temporary copy contains this case only. The wheel is installed without runtime
dependencies in a fresh environment, then its resources and CLI are exercised from
an unrelated directory. This proves fixture isolation, not live provider behavior.
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
ENV = {key: value for key, value in os.environ.items()
       if key not in {"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT"}}
ENV.setdefault("UV_CACHE_DIR", "/tmp/agent-atlas-uv-cache")


def checked(command: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Keep every local check finite and expose the command on a failed result."""
    process = subprocess.run(command, cwd=cwd, env=ENV, capture_output=True,
                             text=True, timeout=60)
    if process.returncode:
        raise RuntimeError(f"failed {command!r}\n{process.stdout[-2000:]}\n{process.stderr[-4000:]}")
    return process


def tests(command: list[str], cwd: Path) -> int:
    process = checked([*command, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd)
    match = re.search(r"Ran (\d+) tests", process.stderr)
    if match is None or "\nOK\n" not in process.stderr:
        raise RuntimeError("test result did not confirm execution")
    return int(match[1])


def fixtures(command: list[str], cwd: Path) -> list[str]:
    outcomes = []
    for name, expected in (("normal", "completed_simulation"), ("stale", "review_required"),
                           ("missing", "review_required"), ("persistent", "review_required")):
        report = json.loads(checked([*command, "--fixture", name], cwd).stdout)
        if report["status"] != expected or report["authority"]["orders_authorized"]:
            raise RuntimeError(f"unexpected fixture outcome for {name}")
        outcomes.append(f"{name}:{expected}")
    return outcomes


def main() -> None:
    if sys.version_info[:2] != (3, 14):
        raise RuntimeError("qualification requires Python 3.14")
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv is required for isolated package qualification")
    summary = {"mode": "fixture", "python": sys.version.split()[0]}
    summary["source_tests"] = tests([sys.executable], CASE)
    summary["source_fixtures"] = fixtures([sys.executable, "-m", "financial_advisory"], CASE)
    print("Source tests and all four real CLI fixture paths passed.", flush=True)
    with tempfile.TemporaryDirectory(prefix="atlas-financial-26-") as directory:
        temporary = Path(directory)
        copied = temporary / "case"
        shutil.copytree(CASE, copied, ignore=shutil.ignore_patterns(".venv", "dist", "__pycache__", "*.pyc"))
        copied_python = [uv, "run", "--offline", "--locked", "python"]
        summary["case_copy_tests"] = tests(copied_python, copied)
        summary["case_copy_fixtures"] = fixtures([*copied_python, "-m", "financial_advisory"], copied)
        print("Case-only copy tests and all four fixture paths passed outside the repository.", flush=True)
        wheel_directory = temporary / "wheels"
        checked([uv, "build", "--offline", "--wheel", "--out-dir", str(wheel_directory)], copied)
        wheels = list(wheel_directory.glob("*.whl"))
        if len(wheels) != 1:
            raise RuntimeError("build must produce exactly one wheel")
        installed = temporary / "installed"
        checked([uv, "venv", "--offline", "--python", sys.executable, str(installed)], temporary)
        python = installed / "bin" / "python"
        checked([uv, "pip", "install", "--offline", "--python", str(python), "--no-deps", str(wheels[0])], temporary)
        # The installed interpreter discovers tests from the copy, not its src tree.
        summary["installed_wheel_tests"] = tests([str(python), "-I"], copied)
        neutral = temporary / "neutral"
        neutral.mkdir()
        summary["installed_wheel_fixtures"] = fixtures([str(python), "-I", "-m", "financial_advisory"], neutral)
        command = installed / "bin" / "financial-advisory"
        summary["installed_console_fixtures"] = fixtures([str(command)], neutral)
        origin = checked([str(python), "-I", "-c", "import financial_advisory; print(financial_advisory.__file__)"], neutral).stdout.strip()
        if not Path(origin).is_relative_to(installed):
            raise RuntimeError("installed import did not originate in fresh environment")
        summary["installed_origin_verified"] = True
    summary["result"] = "passed"
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
