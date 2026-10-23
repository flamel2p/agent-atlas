"""Re-run the case in an independent copy and a clean installed-wheel environment.

Only this case is copied. Neither execution uses a sibling installation or root
runtime. Wheel tests run from an empty directory, using installed resources and
the installed console script. All temporary artifacts disappear after the run.
No provider, network, deployment, or model-quality qualification is performed.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def run(arguments, *, cwd, env):
    result = subprocess.run([str(arg) for arg in arguments], cwd=cwd, env=env,
                            capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError(f"Qualification command failed: {arguments!r}\n{result.stdout}\n{result.stderr}")
    return result.stdout + result.stderr


def suite(python, tests, *, cwd, env):
    output = run([python, "-m", "unittest", "discover", "-s", tests, "-v"], cwd=cwd, env=env)
    print("\n".join(line for line in output.splitlines() if line.startswith("Ran ") or line == "OK"))


def main():
    case = Path(__file__).resolve().parent
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("VIRTUAL_ENV", None)
    env["UV_CACHE_DIR"] = "/tmp/agent-atlas-uv-cache"
    env["UV_OFFLINE"] = "1"
    with tempfile.TemporaryDirectory(prefix="typed-decision-qualification-") as temporary:
        root = Path(temporary).resolve()
        copied = root / "case"
        shutil.copytree(case, copied, ignore=shutil.ignore_patterns(".venv", "__pycache__", "dist", "*.pyc"))
        run(["uv", "sync", "--locked", "--offline", "--python", "3.14.8"], cwd=copied, env=env)
        print("Independent case copy")
        suite(copied / ".venv/bin/python", copied / "tests", cwd=copied, env=env)
        run(["uv", "build", "--offline", "--wheel", "--out-dir", root / "wheels"], cwd=copied, env=env)
        wheel = next((root / "wheels").glob("*.whl"))
        wheel_venv = root / "wheel-venv"
        run(["uv", "venv", "--offline", "--python", "3.14.8", wheel_venv], cwd=root, env=env)
        python = wheel_venv / "bin/python"
        run(["uv", "pip", "install", "--offline", "--python", python, wheel], cwd=root, env=env)
        empty = root / "empty"
        empty.mkdir()
        location = run([python, "-c", "import typed_decision; print(typed_decision.__file__)"], cwd=empty, env=env)
        if not Path(location.strip()).is_relative_to(wheel_venv):
            raise RuntimeError("Wheel import did not originate inside the clean environment")
        print("Installed wheel from empty working directory")
        suite(python, copied / "tests", cwd=empty, env=env)
    print("Copy and wheel qualification passed; fixture evidence only.")


if __name__ == "__main__":
    main()
