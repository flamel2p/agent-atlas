#!/usr/bin/env python3
"""Prove copied-case and installed-wheel execution without sibling dependencies.

Copy only case-owned source into a temporary directory. Clear environment
settings that could select the source environment, then qualify both the copy
and a fresh wheel environment. Imported package paths are checked explicitly.
"""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def main() -> int:
    case = Path(__file__).resolve().parents[1]
    uv = shutil.which("uv")
    if uv is None:
        raise SystemExit("uv is required for isolation verification")
    environment = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT", "UV_WORKING_DIRECTORY"):
        environment.pop(key, None)
    environment["UV_CACHE_DIR"] = "/tmp/agent-atlas-uv-cache"

    def run(arguments: list[str], cwd: Path) -> None:
        print("RUN", " ".join(arguments), flush=True)
        subprocess.run(arguments, cwd=cwd, env=environment, check=True, timeout=60)

    with tempfile.TemporaryDirectory(prefix="agent23-isolation-") as directory:
        work = Path(directory)
        copied = work / "case"
        shutil.copytree(case, copied, ignore=shutil.ignore_patterns(
            ".venv", "__pycache__", "*.pyc", "dist", "build", "*.egg-info", "artifacts"))
        run([uv, "sync", "--offline", "--frozen"], copied)
        run([uv, "run", "--offline", "--frozen", "python", "-m", "unittest", "discover", "-s", "tests", "-v"], copied)
        run([uv, "run", "--offline", "--frozen", "python", "scripts/verify_cli.py",
             "--expected-package-root", str(copied / "src")], copied)
        wheels = work / "wheels"
        run([uv, "build", "--offline", "--wheel", "--out-dir", str(wheels)], copied)
        packages = list(wheels.glob("*.whl"))
        assert len(packages) == 1, packages
        wheel_environment = work / "wheel-environment"
        run([uv, "venv", "--python", "3.14", str(wheel_environment)], work)
        python = wheel_environment / "bin/python"
        run([uv, "pip", "install", "--offline", "--python", str(python), str(packages[0])], work)
        run([str(python), "-I", "-m", "unittest", "discover", "-s", str(copied / "tests"), "-v"], work)
        run([str(python), "-I", str(copied / "scripts/verify_cli.py"), "--expected-package-root",
             str(wheel_environment / "lib/python3.14/site-packages")], work)
    print("PASS: case-only copy and fresh installed wheel, behavior and CLI checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
