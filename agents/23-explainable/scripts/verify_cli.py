#!/usr/bin/env python3
"""Exercise the real CLI without imports from a sibling or repository root.

Run with the case environment or an isolated installed-wheel interpreter.
The optional package-root assertion proves where the child imports its code.
Every process has a five-second timeout, including the FIFO rejection probe.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-package-root", type=Path)
    args = parser.parse_args()
    checks = 0

    def run(command, data=None):
        return subprocess.run(command, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=5, check=False)

    def check(arguments, exit_code, decision=None, issue=None, data=None, console=False):
        nonlocal checks
        prefix = [entrypoint] if console else [sys.executable, "-m", "explainable"]
        result = run([*prefix, *arguments], data)
        assert result.returncode == exit_code, (arguments, result.returncode, result.stderr.decode(errors="replace"))
        assert not result.stderr, (arguments, result.stderr)
        outcome = json.loads(result.stdout)
        assert outcome["decision"] == decision, (arguments, outcome)
        assert "Traceback" not in result.stdout.decode(), arguments
        if issue:
            assert outcome["issues"] == [issue], (arguments, outcome)
            assert outcome["status"] == "needs_review", (arguments, outcome)
        else:
            assert outcome["status"] == "completed", (arguments, outcome)
            assert outcome["explanation_status"] == "complete", (arguments, outcome)
            assert len(outcome["explanations"]) == 3, arguments
            assert {view["decision"] for view in outcome["explanations"]} == {decision}, arguments
            ids = {event["event_id"] for event in outcome["trace"]["events"]}
            assert all(claim["event_ids"] and set(claim["event_ids"]).issubset(ids)
                       for view in outcome["explanations"] for claim in view["claims"]), arguments
        checks += 1
        return outcome

    entrypoint = str(Path(sys.executable).parent / "explainable")
    assert Path(entrypoint).is_file(), "Installed console entry point is required"
    if args.expected_package_root:
        imported = run([sys.executable, "-c", "import explainable; print(explainable.__file__)"])
        assert imported.returncode == 0 and not imported.stderr, imported.stderr
        module_path = Path(imported.stdout.decode().strip()).resolve()
        assert module_path.is_relative_to(args.expected_package_root.resolve()), module_path
        checks += 1

    case = Path(__file__).resolve().parents[1]
    urgent = check(["classify", str(case / "fixtures/urgent.json")], 0, "urgent", console=True)
    check(["classify", str(case / "fixtures/high.json")], 0, "high")
    check(["classify", str(case / "fixtures/routine.json")], 0, "routine")
    missing = check(["classify", str(case / "fixtures/missing-evidence.json")], 2, issue="evidence_missing")
    assert missing["explanation_status"] == "incomplete"
    assert len(missing["trace"]["events"]) == 4
    assert len(missing["explanations"]) == 3
    payload = (case / "fixtures/urgent.json").read_bytes()
    check(["classify", "-"], 0, "urgent", data=payload)

    with tempfile.TemporaryDirectory(prefix="explainable-cli-") as directory:
        work = Path(directory)
        trace = work / "trace.json"
        trace.write_text(json.dumps(urgent["trace"]))
        replay = check(["explain", str(trace)], 0, "urgent")
        assert replay == urgent
        trace.write_text(json.dumps(missing["trace"]))
        check(["explain", str(trace)], 2, issue="evidence_missing")
        corrupted = urgent["trace"]
        corrupted["events"][-1]["decision"] = "routine"
        trace.write_text(json.dumps(corrupted))
        check(["explain", str(trace)], 2, issue="trace_invalid")
        invalid_inputs = (
            (b'{"task_id":"x","task_id":"y","evidence":{}}', "json_invalid"),
            (b'{"task_id":"x","evidence":{"outage":true,"outage":false}}', "json_invalid"),
            (b'{"task_id":"x","evidence":{"due_hours":NaN}}', "json_invalid"),
            (b'{"task_id":"x","evidence":{"due_hours":Infinity}}', "json_invalid"),
            (b'{"task_id":"x","evidence":{"due_hours":1e999}}', "json_invalid"),
            (b'\xff', "json_invalid"),
            (b'{} {}', "json_invalid"),
            (b'', "json_invalid"),
            (b' ' * 32769, "input_too_large"),
            (b'{"task_id":"x","evidence":{"blocked_users":true}}', "input_invalid"),
            (b'{"task_id":"x","evidence":{"due_hours":721}}', "input_invalid"),
            (b'{"task_id":"x","evidence":{},"system":"untrusted-marker"}', "input_invalid"),
            (b'{"task_id":"x","evidence":{"instruction":"untrusted-marker"}}', "input_invalid"),
            (b'[]', "input_invalid"),
            (b'[' * 2000 + b']' * 2000, "json_invalid"),
        )
        for content, issue in invalid_inputs:
            result = check(["classify", "-"], 2, issue=issue, data=content)
            assert "untrusted-marker" not in json.dumps(result)
        regular = work / "regular.json"
        regular.write_bytes(payload)
        link = work / "link.json"
        link.symlink_to(regular)
        check(["classify", str(link)], 2, issue="input_unreadable")
        fifo = work / "pipe"
        os.mkfifo(fifo)
        check(["classify", str(fifo)], 2, issue="input_unreadable")
        check(["classify", str(work)], 2, issue="input_unreadable")
        check(["classify", str(work / "absent")], 2, issue="input_unreadable")
        check(["untrusted-marker", "-"], 2, issue="command_invalid")
        check([], 2, issue="command_invalid")

    print(f"PASS: {checks} CLI checks, real console/module processes, fixtures and failure boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
