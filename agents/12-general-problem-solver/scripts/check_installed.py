"""Check an installed CLI against independent scheduling witnesses.

The oracle calculates feasibility directly from each input, without importing
the solver or trusting its reported constraint score. It also checks the
relationship between selected proposals, trigger evidence, and work budgets.
"""

import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import subprocess
import tempfile


def oracle(puzzle, starts):
    tasks = sorted(puzzle["tasks"], key=lambda task: task["id"])
    assert len(starts) == len(tasks)
    by_id = {task["id"]: (task, start) for task, start in zip(tasks, starts)}
    score = 0
    for task, start in zip(tasks, starts):
        assert type(start) is int
        assert 0 <= start <= puzzle["horizon"] - task["duration"]
        score += max(0, task["earliest_start"] - start)
        score += max(0, start + task["duration"] - task["latest_finish"])
        for predecessor in task["after"]:
            parent, parent_start = by_id[predecessor]
            score += max(0, parent_start + parent["duration"] - start)
    for resource in puzzle["resources"]:
        for tick in range(puzzle["horizon"]):
            demand = sum(
                task["requires"].get(resource["id"], 0)
                for task, start in zip(tasks, starts)
                if start <= tick < start + task["duration"]
            )
            score += max(0, demand - resource["capacity"])
    return score


def check_report(puzzle, payload, report):
    history = report["history"]
    assert history
    assert report["input_sha256"] == hashlib.sha256(payload).hexdigest()
    assert report["iterations"] == len(history) <= puzzle["budget"]["iterations"]
    assert 1 <= report["evaluations"] <= puzzle["budget"]["evaluations"]
    assert sum(item["evaluations_consumed"] for item in history) <= report["evaluations"]
    expected_windows = [
        {"task_id": task["id"], "duration": task["duration"],
         "earliest_start": task["earliest_start"], "latest_finish": task["latest_finish"]}
        for task in sorted(puzzle["tasks"], key=lambda task: task["id"])
    ]
    assert report["decomposition"]["windows"] == expected_windows
    previous = None
    for item in history:
        evaluation = item["evaluation"]
        score = oracle(puzzle, evaluation["candidate"]["starts"])
        assert evaluation["score"] == score
        assert bool(evaluation["violations"]) == (score > 0)
        assert sum(v["excess"] for v in evaluation["violations"]) == score
        assert all(v["excess"] > 0 for v in evaluation["violations"])
        assert item["analogy_kind"] == "illustrative_heuristic"
        if previous is None:
            assert item["triggering_violations"] == []
        else:
            assert item["triggering_violations"] == previous["violations"]
            assert evaluation["score"] < previous["score"]
            changed = [i for i, (before, after) in enumerate(zip(
                previous["candidate"]["starts"], evaluation["candidate"]["starts"]
            )) if before != after]
            assert len(changed) == 1
            implicated = {task for v in previous["violations"] for task in v["task_ids"]}
            assert expected_windows[changed[0]]["task_id"] in implicated
        previous = evaluation
    assert report["best"] == previous
    assert (report["status"] == "solved") == (oracle(puzzle, report["best"]["candidate"]["starts"]) == 0)
    assert (report["stop_reason"] == "feasible") == (report["status"] == "solved")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", required=True, type=Path)
    parser.add_argument("--cases", required=True, type=Path)
    args = parser.parse_args()
    executable = args.executable.resolve()
    cases = json.loads(args.cases.read_text())["cases"]
    environment = {key: value for key, value in os.environ.items()
                   if key not in {"PYTHONPATH", "PYTHONHOME"}}
    invocations = 0
    enumerated = 0
    with tempfile.TemporaryDirectory(prefix="agent12-cli-") as directory:
        work = Path(directory)

        def run(*arguments):
            nonlocal invocations
            invocations += 1
            return subprocess.run([str(executable), *arguments], cwd=work,
                                  env=environment, capture_output=True, timeout=15)

        for case in cases:
            payload = json.dumps(case["input"], sort_keys=True).encode()
            path = work / (case["name"] + ".json")
            path.write_bytes(payload)
            result = run("--input", str(path))
            assert not result.stderr, (case["name"], result.stderr)
            report = json.loads(result.stdout)
            assert result.returncode == (0 if report["status"] == "solved" else 1)
            check_report(case["input"], payload, report)
            expected = case["independent_expected"]
            for key, expected_key in (("status", "outcome"), ("stop_reason", "termination"),
                                      ("iterations", "proposal_count"),
                                      ("evaluations", "evaluated_candidate_count")):
                assert report[key] == expected[expected_key], (
                    case["name"], key, report[key], expected[expected_key])
            task_ids = sorted(task["id"] for task in case["input"]["tasks"])
            assignments = [dict(zip(task_ids, item["evaluation"]["candidate"]["starts"]))
                           for item in report["history"]]
            assert assignments == expected["selected_start_assignments"], case["name"]
            assert [item["evaluation"]["score"] for item in report["history"]] == expected["selected_scores"]

            for facts_key, evaluation in (("initial_violation_facts", report["history"][0]["evaluation"]),
                                          ("final_violation_facts", report["best"])):
                if facts_key not in expected:
                    continue
                actual = [{"kind": "window" if v["kind"].startswith("window_") else v["kind"],
                           "affected": sorted(v["task_ids"]),
                           "excess": v["excess"], **({"resource": v["resource_id"], "tick": v["tick"]}
                            if v["kind"] == "capacity" else {})}
                          for v in evaluation["violations"]]
                wanted = [{key: value for key, value in fact.items() if key != "cause"}
                          for fact in expected[facts_key]]
                assert sorted(map(lambda x: json.dumps(x, sort_keys=True), actual)) == sorted(
                    map(lambda x: json.dumps(x, sort_keys=True), wanted)), case["name"]

            tasks = sorted(case["input"]["tasks"], key=lambda task: task["id"])
            feasible = []
            for starts in itertools.product(*(range(case["input"]["horizon"] - task["duration"] + 1)
                                               for task in tasks)):
                enumerated += 1
                if oracle(case["input"], starts) == 0:
                    feasible.append(dict(zip(task_ids, starts)))
            if "feasible_assignments" in expected:
                assert feasible == expected["feasible_assignments"], case["name"]
            if "feasible_witness" in expected:
                assert expected["feasible_witness"] in feasible, case["name"]
            repeated = run("--input", str(path))
            assert (result.returncode, result.stdout, result.stderr) == (
                repeated.returncode, repeated.stdout, repeated.stderr
            ), case["name"]
            assert path.read_bytes() == payload

        for name in ("revision", "already-valid", "impossible", "dependency",
                     "iteration-limit", "evaluation-limit", "local-minimum"):
            result = run("--example", name)
            report = json.loads(result.stdout)
            assert not result.stderr
            assert result.returncode == (0 if report["status"] == "solved" else 1)
            assert report["status"] == ("solved" if name in {
                "revision", "already-valid", "dependency"} else "unsolved")

        for index, payload in enumerate((b"{", b'{"horizon":1,"horizon":2}',
                                         b'{"horizon":NaN}', b" " * 65537)):
            path = work / f"invalid-{index}.json"
            path.write_bytes(payload)
            result = run("--input", str(path))
            assert result.returncode == 2 and not result.stdout and result.stderr
            assert b"Traceback" not in result.stderr
        fifo = work / "pipe"
        os.mkfifo(fifo)
        result = run("--input", str(fifo))
        assert result.returncode == 2 and not result.stdout
        missing = run("--input", str(work / "missing.json"))
        assert missing.returncode == 2 and not missing.stdout
        help_result = run("--help")
        assert help_result.returncode == 0 and help_result.stdout
        output_cases = (("--example", "already-valid"), ("--example", "revision"),
                        ("--example", "impossible"), ("--help",))
        for arguments in output_cases:
            invocations += 1
            reader, writer = os.pipe()
            os.close(reader)
            try:
                process = subprocess.Popen([str(executable), *arguments], cwd=work,
                                           env=environment, stdout=writer,
                                           stderr=subprocess.PIPE)
            finally:
                os.close(writer)
            _, diagnostic = process.communicate(timeout=15)
            assert process.returncode == 2, (arguments, process.returncode, diagnostic)
            assert diagnostic.startswith(b"I/O error:")
            assert b"Traceback" not in diagnostic and b"Exception ignored" not in diagnostic
        readonly_path = work / "readonly-output"
        readonly_path.write_bytes(b"unchanged output descriptor target")
        for arguments in output_cases:
            invocations += 1
            with readonly_path.open("rb") as destination:
                result = subprocess.run([str(executable), *arguments], cwd=work,
                                        env=environment, stdout=destination,
                                        stderr=subprocess.PIPE, timeout=15)
            assert result.returncode == 2, (arguments, result.returncode, result.stderr)
            assert result.stderr.startswith(b"I/O error:")
            assert b"Traceback" not in result.stderr and b"Exception ignored" not in result.stderr
            assert readonly_path.read_bytes() == b"unchanged output descriptor target"
    print(f"PASS: {len(cases)} independent puzzles; {enumerated} enumerated schedules; "
          f"{invocations} installed CLI invocations")


if __name__ == "__main__":
    main()
