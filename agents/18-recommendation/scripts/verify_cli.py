#!/usr/bin/env python3
"""Qualify real CLI reports using raw fixtures and an independent vector oracle.

This script never imports runtime ranking, validation, or report helpers. It
constructs a topic feature vector for every exercise, computes expected gates
and dot products, and compares the complete emitted report. Child processes run
from a fresh case-owned directory with Python import overrides removed. The
same check can target a checkout, case-only copy, or installed wheel command.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import tempfile


LEVELS = ("beginner", "intermediate", "advanced")
CASE = Path(__file__).resolve().parents[1]
DATA = CASE / "src" / "recommendation" / "data"


def strict_output(data: bytes) -> dict:
    """Reject duplicate output fields and nonstandard JSON numbers."""
    def unique(pairs: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in pairs:
            assert key not in result, "duplicate output key"
            result[key] = value
        return result

    def invalid_constant(value: str) -> None:
        raise AssertionError(f"nonstandard output number {value}")

    result = json.loads(data, object_pairs_hook=unique, parse_constant=invalid_constant)
    assert type(result) is dict, "output must be an object"
    return result


def assert_report(actual: dict, expected: dict, context: object) -> None:
    # Python equality merges booleans, integers, and floats. Canonical JSON
    # preserves those distinctions while ignoring irrelevant key order.
    def canonical(value: dict) -> str:
        return json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":"))
    assert canonical(actual) == canonical(expected), {
        "context": context, "expected": expected, "actual": actual,
    }


def expected_report(request: dict, catalogue: dict) -> dict:
    """Derive the public contract independently, including all exclusions."""
    vocabulary = sorted(catalogue["topics"])
    interests = tuple(request["topic_weights"].get(topic, 0) for topic in vocabulary)
    eligible, rejected = [], []
    for exercise in catalogue["exercises"]:
        missing = sorted(set(exercise["required_skills"]) - set(request["completed_skills"]))
        failures = (
            ("excluded", exercise["id"] in request["excluded_exercise_ids"]),
            ("duration", exercise["duration_minutes"] > request["max_duration_minutes"]),
            ("difficulty", LEVELS.index(exercise["difficulty"]) > LEVELS.index(request["max_difficulty"])),
            ("missing_skills", bool(missing)),
        )
        reasons = [name for name, failed in failures if failed]
        if reasons:
            rejected.append({"id": exercise["id"], "reasons": reasons, "missing_skills": missing})
            continue
        features = tuple(int(topic in exercise["topics"]) for topic in vocabulary)
        score = sum(left * right for left, right in zip(interests, features, strict=True))
        contributions = [
            {"topic": topic, "weight": weight}
            for topic, weight, present in zip(vocabulary, interests, features, strict=True)
            if present and weight
        ]
        eligible.append({
            "id": exercise["id"], "title": exercise["title"],
            "duration_minutes": exercise["duration_minutes"], "difficulty": exercise["difficulty"],
            "score": score, "matched_topics": contributions,
        })

    matching = [entry for entry in eligible if entry["score"] > 0]
    if not eligible:
        status, reason, selected = "empty", "no_eligible_exercises", []
    elif not request["topic_weights"]:
        status, reason, selected = "cold_start", "non_personalized_baseline", eligible
    elif not matching:
        status, reason, selected = "no_match", "no_positive_topic_overlap", []
    else:
        status, reason, selected = "personalized", "positive_topic_overlap", matching
    ordered = sorted(selected, key=lambda item: (-item["score"], item["duration_minutes"], item["id"]))
    returned = ordered[:request["limit"]]
    normalized = deepcopy(request)
    normalized["topic_weights"] = dict(sorted(request["topic_weights"].items()))
    normalized["completed_skills"] = sorted(request["completed_skills"])
    normalized["excluded_exercise_ids"] = sorted(request["excluded_exercise_ids"])
    return {
        "policy_version": "1", "catalogue_version": catalogue["version"],
        "provenance": "independent_project_extension", "status": status, "reason": reason,
        "request": normalized,
        "counts": {"catalogue": len(catalogue["exercises"]), "eligible": len(eligible),
                   "matching": len(matching), "returned": len(returned), "rejected": len(rejected)},
        "recommendations": returned,
        "rejected": sorted(rejected, key=lambda item: item["id"]),
        "unmatched_eligible_ids": sorted(item["id"] for item in eligible if item["score"] == 0),
        "score_meaning": "sum_of_matching_topic_weights_not_confidence",
        "ordering_policy": ["score_desc", "duration_minutes_asc", "id_asc"],
    }


def generated_requests(catalogue: dict) -> list[dict]:
    """Exercise actual fixture boundaries, changed interests, and every gate."""
    topics = sorted(catalogue["topics"])
    base = {
        "topic_weights": {topic: index + 1 for index, topic in enumerate(topics)},
        "max_duration_minutes": 480, "max_difficulty": "advanced",
        "completed_skills": sorted(catalogue["skills"]),
        "excluded_exercise_ids": [], "limit": 20,
    }
    requests = [deepcopy(base)]
    for weights in ({}, {topics[0]: 1}, {topics[-1]: 100}, {topics[0]: 100, topics[-1]: 1}):
        for limit in (1, 3, 20):
            request = deepcopy(base)
            request.update(topic_weights=weights, limit=limit)
            requests.append(request)
    for exercise in catalogue["exercises"]:
        request = deepcopy(base)
        request.update(max_duration_minutes=exercise["duration_minutes"], max_difficulty=exercise["difficulty"])
        requests.append(request)
        excluded = deepcopy(base)
        excluded["excluded_exercise_ids"] = [exercise["id"]]
        requests.append(excluded)
        if exercise["duration_minutes"] > 1:
            duration = deepcopy(request)
            duration["max_duration_minutes"] -= 1
            requests.append(duration)
        if LEVELS.index(exercise["difficulty"]) > 0:
            difficulty = deepcopy(base)
            difficulty["max_difficulty"] = LEVELS[LEVELS.index(exercise["difficulty"]) - 1]
            requests.append(difficulty)
        for skill in exercise["required_skills"]:
            prerequisite = deepcopy(base)
            prerequisite["completed_skills"].remove(skill)
            requests.append(prerequisite)
    simultaneous = deepcopy(base)
    simultaneous.update(max_duration_minutes=1, max_difficulty="beginner", completed_skills=[],
                        excluded_exercise_ids=sorted(item["id"] for item in catalogue["exercises"]))
    requests.append(simultaneous)
    requests.append(deepcopy(base))
    # Deduplicate equal requests without importing any runtime canonicalization.
    return [json.loads(serialized) for serialized in dict.fromkeys(
        json.dumps(request, sort_keys=True) for request in requests
    )]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--command", type=Path, default=CASE / ".venv" / "bin" / "recommendation")
    options = parser.parse_args()
    command = str(options.command.resolve(strict=True))
    catalogue = json.loads((DATA / "catalogue.json").read_text(encoding="utf-8"))
    environment = os.environ.copy()
    for variable in ("PYTHONPATH", "PYTHONHOME"):
        environment.pop(variable, None)
    environment["PYTHONNOUSERSITE"] = "1"
    artifacts = CASE / "artifacts"
    artifacts.mkdir(exist_ok=True)
    invocations = 0
    statuses = set()
    with tempfile.TemporaryDirectory(prefix="cli-oracle-", dir=artifacts) as temporary:
        working = Path(temporary)

        def invoke(arguments: list[str], *, expect_error: bool = False) -> dict | None:
            nonlocal invocations
            completed = subprocess.run([command, *arguments], cwd=working, env=environment,
                                       capture_output=True, timeout=8)
            invocations += 1
            if expect_error:
                assert completed.returncode == 2, (arguments, completed.returncode, completed.stderr)
                assert not completed.stdout, (arguments, completed.stdout)
                failure = strict_output(completed.stderr)
                assert failure, arguments
                assert b"PRIVATE_SENTINEL" not in completed.stderr, completed.stderr
                assert b"Traceback" not in completed.stderr, completed.stderr
                return None
            assert completed.returncode == 0, (arguments, completed.returncode, completed.stderr)
            assert not completed.stderr, (arguments, completed.stderr)
            report = strict_output(completed.stdout)
            statuses.add(report["status"])
            return report

        for scenario in ("normal", "cold-start", "no-match", "constrained", "no-eligible"):
            request = json.loads((DATA / "scenarios" / f"{scenario}.json").read_text(encoding="utf-8"))
            expected = expected_report(request, catalogue)
            assert_report(invoke(["--scenario", scenario]), expected, scenario)
            if scenario == "normal":
                assert_report(invoke([]), expected, "default scenario")

        for index, request in enumerate(generated_requests(catalogue)):
            request_file = working / f"request-{index}.json"
            request_file.write_text(json.dumps(request), encoding="utf-8")
            actual = invoke(["--request", str(request_file)])
            expected = expected_report(request, catalogue)
            assert_report(actual, expected, request)
            # Reordering caller collections cannot change normalization or decisions.
            if index < 3:
                permuted = {key: request[key] for key in reversed(request)}
                permuted["topic_weights"] = dict(reversed(list(request["topic_weights"].items())))
                permuted["completed_skills"] = list(reversed(request["completed_skills"]))
                request_file.write_text(json.dumps(permuted), encoding="utf-8")
                assert_report(invoke(["--request", str(request_file)]), expected, "request permutation")

        valid = json.loads((DATA / "scenarios" / "normal.json").read_text(encoding="utf-8"))
        invalid = []
        for field, value in (("limit", True), ("limit", 0), ("limit", 21),
                             ("topic_weights", {"PRIVATE_SENTINEL": 1}),
                             ("topic_weights", {catalogue["topics"][0]: False}),
                             ("max_difficulty", "PRIVATE_SENTINEL"),
                             ("completed_skills", ["PRIVATE_SENTINEL"]),
                             ("excluded_exercise_ids", ["PRIVATE_SENTINEL"])):
            request = deepcopy(valid)
            request[field] = value
            invalid.append(json.dumps(request).encode())
        valid_bytes = json.dumps(valid, separators=(",", ":")).encode()
        duplicate_key = valid_bytes[:-1] + b',"limit":' + str(valid["limit"]).encode() + b"}"
        oversized = valid_bytes + b" " * (256 * 1024 + 1 - len(valid_bytes))
        exact_file = working / "exact-limit.json"
        exact_file.write_bytes(oversized[:-1])
        assert_report(invoke(["--request", str(exact_file)]), expected_report(valid, catalogue), "exact size limit")
        invalid.extend((b'{"PRIVATE_SENTINEL":', duplicate_key, b'{"x":NaN}', oversized,
                        b"[" * 2000 + b"]" * 2000, b"\xff"))
        for index, payload in enumerate(invalid):
            request_file = working / f"PRIVATE_SENTINEL-invalid-{index}.json"
            request_file.write_bytes(payload)
            invoke(["--request", str(request_file)], expect_error=True)
        invoke(["--request", str(working / "PRIVATE_SENTINEL-missing")], expect_error=True)
        invoke(["--request", str(working)], expect_error=True)
        symlink = working / "PRIVATE_SENTINEL-link.json"
        symlink.symlink_to(DATA / "scenarios" / "normal.json")
        invoke(["--request", str(symlink)], expect_error=True)
        fifo = working / "PRIVATE_SENTINEL-fifo"
        os.mkfifo(fifo)
        invoke(["--request", str(fifo)], expect_error=True)
        for unbuffered in (False, True):
            pipe_environment = environment.copy()
            if unbuffered:
                pipe_environment["PYTHONUNBUFFERED"] = "1"
            else:
                pipe_environment.pop("PYTHONUNBUFFERED", None)
            with subprocess.Popen([command], cwd=working, env=pipe_environment,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE) as child:
                assert child.stdout is not None
                child.stdout.close()
                child.stdout = None
                try:
                    _, error = child.communicate(timeout=8)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.communicate()
                    raise AssertionError("closed stdout process failed to terminate") from None
                finally:
                    if child.poll() is None:
                        child.kill()
                        child.communicate()
                assert child.returncode != 0, "closed stdout must not report success"
            assert b"Traceback" not in error, error
            invocations += 1
        for arguments in ([], ["--help"]):
            closed = subprocess.run([command, *arguments], cwd=working, env=environment,
                                    preexec_fn=lambda: os.close(1), capture_output=True, timeout=8)
            invocations += 1
            assert closed.returncode == 1 and not closed.stdout, closed
            assert strict_output(closed.stderr)["error"]["code"] == "output_unavailable", closed.stderr
        closed_error = subprocess.run([command, "--PRIVATE_SENTINEL"], cwd=working, env=environment,
                                      preexec_fn=lambda: os.close(2), capture_output=True, timeout=8)
        invocations += 1
        assert closed_error.returncode == 2, closed_error
        assert closed_error.stdout == closed_error.stderr == b"", closed_error
    assert statuses == {"personalized", "cold_start", "no_match", "empty"}, statuses
    print(json.dumps({"result": "passed", "cli_invocations": invocations,
                      "statuses": sorted(statuses), "oracle": "independent_feature_vectors"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
