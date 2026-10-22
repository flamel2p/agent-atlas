"""Verify the copied case and installed wheel without repository context.

This development check uses a temporary directory, strips credentials and
PYTHONPATH from child environments, and runs independently constructed requests
against the installed console command. It requires a populated uv cache and
the pinned Python interpreter. It does not prove an operating-system sandbox.
"""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def run(command, cwd, env, expected=0):
    result = subprocess.run(
        [str(item) for item in command], cwd=cwd, env=env,
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != expected:
        raise AssertionError(
            f"Command {command[0]} returned {result.returncode}, expected {expected}\n"
            f"{result.stdout}\n{result.stderr}"
        )
    return result


def fixture_hashes(case):
    paths = list((case / "fixtures").rglob("*.json"))
    paths += list((case / "src").rglob("*.json"))
    return {str(path.relative_to(case)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths}


def main():
    case = Path(__file__).resolve().parents[1]
    uv = shutil.which("uv")
    if uv is None:
        raise SystemExit("uv is required")
    env = {key: os.environ[key] for key in ("PATH", "HOME", "TMPDIR") if key in os.environ}
    env.update({
        "UV_CACHE_DIR": os.environ.get("UV_CACHE_DIR", "/tmp/agent-atlas-uv-cache"),
        "UV_PYTHON_DOWNLOADS": "never",
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    with tempfile.TemporaryDirectory(prefix="agent11-isolation-") as temporary:
        root = Path(temporary)
        copied = root / "case"
        shutil.copytree(case, copied, ignore=shutil.ignore_patterns(
            ".venv", "__pycache__", ".pytest_cache", "artifacts", "dist", "build",
        ))
        before = fixture_hashes(copied)
        run([uv, "sync", "--locked", "--offline"], copied, env)
        suite = run([uv, "run", "--locked", "--offline", "python", "-m", "unittest",
                     "discover", "-s", "tests", "-v"], copied, env)
        print(suite.stderr.strip())
        run([uv, "run", "--locked", "--offline", "verification-agent", "fixtures/claims.json"],
            copied, env)
        run([uv, "build", "--offline", "--wheel", "--out-dir", root / "wheels"], copied, env)
        wheels = list((root / "wheels").glob("*.whl"))
        assert len(wheels) == 1, "Exactly one built wheel is required"
        installed = root / "installed"
        run([uv, "venv", "--python", "3.14.8", installed], root, env)
        run([uv, "pip", "install", "--offline", "--no-index", "--python",
             installed / "bin/python", wheels[0]], root, env)
        empty = root / "outside-checkout"
        empty.mkdir()
        cli = installed / "bin/verification-agent"
        snapshot_digest = hashlib.sha256(
            (copied / "src/verification_agent/data/truth-v1.json").read_bytes()
        ).hexdigest()
        base = {
            "id": "check", "entity": "atlas", "metric": "latency_change",
            "period": "2026-Q3", "baseline_period": "2026-Q2",
            "value": "-5", "unit": "relative_percent",
        }
        scenarios = [
            ("exact", {}, "confirmed", "exact_match"),
            ("reversal", {"value": "5"}, "contradicted", "direction_reversed"),
            ("tolerance", {"value": "-4.5"}, "mostly_true", "within_tolerance"),
            ("outside", {"value": "-4.499999"}, "contradicted", "outside_tolerance"),
            ("unit", {"unit": "percentage_point"}, "unverified", "unit_mismatch"),
            ("entity", {"entity": "missing"}, "unverified", "missing_evidence"),
            ("period", {"period": "2026-Q4"}, "unverified", "missing_evidence"),
            ("baseline", {"baseline_period": "2026-Q1"}, "unverified", "missing_evidence"),
            ("metric", {"metric": "unknown"}, "unverified", "unknown_metric"),
            ("conflict", {"entity": "fork"}, "unverified", "conflicting_evidence"),
            ("expired", {"entity": "archive"}, "unverified", "no_current_evidence"),
            ("future", {"entity": "preview"}, "unverified", "no_current_evidence"),
            ("small-reversal", {"entity": "tiny", "value": "0.1"},
             "contradicted", "direction_reversed"),
            ("zero", {"entity": "quiet", "value": "0"}, "confirmed", "exact_match"),
        ]
        for name, changes, verdict, reason in scenarios:
            request = {"as_of": "2026-10-21", "claims": [dict(base, **changes)]}
            path = empty / f"{name}.json"
            path.write_text(json.dumps(request))
            result = run([cli, path], empty, env)
            report = json.loads(result.stdout)
            assert report["snapshot_sha256"] == snapshot_digest, name
            finding = report["results"][0]
            assert (finding["verdict"], finding["reason"]) == (verdict, reason), name
            assert report["review_required"] == (verdict != "confirmed"), name
            repeated = run([cli, path], empty, env)
            assert repeated.stdout == result.stdout, f"Nondeterministic report for {name}"
        invalid = empty / "invalid.json"
        invalid.write_text('{"as_of":"2026-10-21","claims":[]}')
        rejected = run([cli, invalid], empty, env, expected=2)
        assert not rejected.stdout, "Invalid input must not emit a partial report"
        oversized = empty / "oversized.json"
        oversized.write_bytes(b" " * 65_537)
        rejected = run([cli, oversized], empty, env, expected=2)
        assert not rejected.stdout, "Oversized input must not emit a report"
        assert fixture_hashes(copied) == before, "Input or evidence bytes changed"
        print("PASS: copied-case suite and CLI; installed wheel; 30 CLI invocations "
              "across 16 independent scenarios; evidence digest; repeatability; unchanged fixtures.")


if __name__ == "__main__":
    main()
