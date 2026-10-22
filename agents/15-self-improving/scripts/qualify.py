"""Qualify an isolated case copy and wheel using offline local tooling.

This development check keeps temporary copies under case-local artifacts and
removes them afterward. It clears Python path overrides, checks installed CLI
behavior from an empty directory, and never contacts a model or provider.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


def run(command: list[str], directory: Path, environment: dict[str, str]) -> str:
    result = subprocess.run(command, cwd=directory, env=environment,
                            capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(command)}\n{result.stdout}\n{result.stderr}")
    return result.stdout + result.stderr


def main() -> None:
    case = Path(__file__).resolve().parents[1]
    artifacts = case / "artifacts"
    artifacts.mkdir(exist_ok=True)
    environment = {key: value for key, value in os.environ.items()
                   if key not in {"PYTHONPATH", "PYTHONHOME", "UV_PROJECT_ENVIRONMENT"}}
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment.setdefault("UV_CACHE_DIR", "/tmp/agent-atlas-uv-cache")
    with tempfile.TemporaryDirectory(prefix="qualification-", dir=artifacts) as temporary:
        scratch = Path(temporary)
        copied = scratch / "standalone-case"
        shutil.copytree(case, copied, ignore=shutil.ignore_patterns(
            ".venv", "artifacts", "dist", "__pycache__", "*.pyc"))
        output = run(["uv", "run", "--locked", "--offline", "python", "-m", "unittest",
                      "discover", "-s", "tests", "-v"], copied, environment)
        count = re.search(r"Ran (\d+) tests", output)
        if count is None or "\nOK\n" not in output:
            raise RuntimeError("Standalone suite did not report successful unittest completion")
        print(f"Copied standalone case: {count.group(1)} tests passed")
        wheels = scratch / "wheels"
        run(["uv", "build", "--wheel", "--offline", "--out-dir", str(wheels)], copied, environment)
        wheel, = wheels.glob("*.whl")
        installed = scratch / "installed"
        run(["uv", "venv", "--offline", "--python", sys.executable, str(installed)], scratch, environment)
        python = installed / "bin" / "python"
        run(["uv", "pip", "install", "--offline", "--python", str(python), str(wheel)], scratch, environment)
        empty = scratch / "empty"
        empty.mkdir()
        location = run([str(python), "-I", "-c", "import self_improving; print(self_improving.__file__)"],
                       empty, environment).strip()
        if not Path(location).is_relative_to(installed):
            raise RuntimeError(f"Import did not resolve inside installed wheel: {location}")
        expected = {"improvement": "review_required", "regression": "rejected_regression",
                    "insufficient": "no_proposal_insufficient", "poisoned": "no_proposal_insufficient",
                    "development-rejection": "rejected_development", "no-gain": "rejected_no_gain"}
        executable = installed / "bin" / "self-improving-agent"
        for scenario, status in expected.items():
            command = [str(executable), "--scenario", scenario]
            output = run(command, empty, environment)
            report = json.loads(output)
            if report["status"] != status or report["serving_version_id"] != report["baseline"]["version_id"]:
                raise RuntimeError(f"Wrong installed behavior for {scenario}")
            digest = report.pop("report_digest")
            canonical = json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            if hashlib.sha256(canonical.encode()).hexdigest() != digest:
                raise RuntimeError(f"Invalid installed report digest for {scenario}")
            if scenario == "improvement":
                if (report["heldout"]["baseline_correct"], report["heldout"]["candidate_correct"]) != (4, 7):
                    raise RuntimeError("Installed improvement oracle failed")
                if run(command, empty, environment) != output:
                    raise RuntimeError("Installed report is not byte-deterministic")
            if scenario == "regression":
                evaluation = report["heldout"]
                if ((evaluation["baseline_correct"], evaluation["candidate_correct"]) != (5, 7)
                        or evaluation["lost_query_ids"] != ["stable-legacy-window"]):
                    raise RuntimeError("Installed regression oracle failed")
        run([str(python), "-I", "-m", "self_improving", "--scenario", "improvement"], empty, environment)
        independent = run([str(python), "-I", str(case / "scripts" / "verify_independent.py")],
                          empty, environment)
        if list(empty.iterdir()):
            raise RuntimeError("CLI persisted unexpected files in its working directory")
        print("Installed wheel: six scenario outcomes, exact-ID oracles, digest, determinism, module CLI passed")
        print(f"Independent installed-wheel checks: {independent.strip()}")


if __name__ == "__main__":
    main()
