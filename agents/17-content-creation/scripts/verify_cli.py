"""Qualify the real CLI with independent JSON and content-contract assertions.

This oracle imports no runtime modules. It exercises installed commands through
subprocesses, computes word counts and source slices itself, and keeps temporary
briefs under the case's ignored artifacts directory. It accepts an alternate
installed command so the same checks qualify a wheel outside the checkout.
"""

from __future__ import annotations

import argparse
import hashlib
from itertools import permutations
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


CASE = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--brief", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    options = parser.parse_args()
    command = options.command
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        command = [sys.executable, "-m", "content_creation"]
    source_bytes = options.fixture.read_bytes()
    source = json.loads(source_bytes)
    source_digest = hashlib.sha256(source_bytes).hexdigest()
    brief = json.loads(options.brief.read_text())
    fact_text = {fact["id"]: fact["text"] for fact in source["facts"]}
    fact_sources = {fact["id"]: fact["source_id"] for fact in source["facts"]}
    count = 0
    child_env = dict(os.environ)
    child_env.pop("PYTHONPATH", None)
    child_env.pop("PYTHONHOME", None)
    child_env["PYTHONNOUSERSITE"] = "1"
    artifacts = CASE / "artifacts"
    artifacts.mkdir(exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="oracle-", dir=artifacts) as directory:
        work = Path(directory)
        brief_path = work / "brief.json"

        def invoke(args: list[str], expected: int | None = None):
            nonlocal count
            completed = subprocess.run(command + args, cwd=work, capture_output=True,
                                       env=child_env, timeout=5, check=False)
            count += 1
            if expected is not None:
                assert completed.returncode == expected, (args, completed.returncode, completed.stderr)
            return completed

        def inspect(completed, request):
            assert completed.returncode in (0, 1), completed.stderr
            assert completed.stderr == b"", completed.stderr
            report = json.loads(completed.stdout)
            assert report["approval"] == "not_granted"
            assert report["fixture_sha256"] == source_digest
            assert [item["kind"] for item in report["artifacts"]] == ["email", "documentation"]
            all_validated = True
            for artifact in report["artifacts"]:
                kind = artifact["kind"]
                limit = request["email_max_words" if kind == "email" else "docs_max_words"]
                attempts = artifact["attempts"]
                assert 1 <= len(attempts) <= 3
                assert [a["number"] for a in attempts] == list(range(1, len(attempts) + 1))
                for index, attempt in enumerate(attempts):
                    text = attempt["text"]
                    assert attempt["word_count"] == len(text.split())
                    observed_ids = []
                    for evidence in sorted(attempt["evidence"], key=lambda item: item["start"]):
                        fid = evidence["fact_id"]
                        assert evidence["fixture_sha256"] == source_digest
                        assert evidence["source_id"] == fact_sources[fid]
                        assert text[evidence["start"]:evidence["end"]] == fact_text[fid]
                        observed_ids.append(fid)
                    assert len(observed_ids) == len(set(observed_ids))
                    assert set(request["required_fact_ids"]) <= set(observed_ids)
                    priority = sorted(source["priorities"][request["audience"]],
                                      key=lambda item: (item["rank"], item["fact_id"]))
                    expected_order = request["required_fact_ids"] + [
                        item["fact_id"] for item in priority
                        if item["fact_id"] in observed_ids and item["fact_id"] not in request["required_fact_ids"]
                    ]
                    assert observed_ids == expected_order
                    if index + 1 < len(attempts):
                        assert attempt["violations"] and attempt["next_changes"]
                        assert text != attempts[index + 1]["text"], "An unchanged retry was recorded"
                    else:
                        assert attempt["next_changes"] == []
                final = attempts[-1]
                passed = artifact["status"] == "validated"
                all_validated = all_validated and passed
                if passed:
                    assert artifact["validated_text"] == final["text"]
                    assert final["violations"] == []
                    assert final["word_count"] <= limit
                    assert source["product"] in final["text"]
                    assert "!" not in final["text"]
                    normalized = " ".join(final["text"].casefold().split())
                    for phrase in request["forbidden_phrases"]:
                        assert " ".join(phrase.casefold().split()) not in normalized
                    headings = ["Subject", "Introduction", "Details", "Next step"] if kind == "email" else ["Title", "Summary", "Changes", "Next step"]
                    positions = [final["text"].index(heading) for heading in headings]
                    assert positions == sorted(positions)
                else:
                    assert artifact["status"] in ("unapproved_limit", "unapproved_no_repair")
                    assert artifact["validated_text"] is None and final["violations"]
                    if artifact["status"] == "unapproved_limit":
                        assert len(attempts) == 3
            assert report["status"] == ("validated" if all_validated else "unapproved")
            assert completed.returncode == (0 if all_validated else 1)
            return report

        def custom(request):
            raw = json.dumps(request).encode()
            brief_path.write_bytes(raw)
            completed = invoke(["--brief", str(brief_path)])
            assert brief_path.read_bytes() == raw
            return inspect(completed, request)

        normal = inspect(invoke([], 0), brief)
        assert any(len(a["attempts"]) > 1 for a in normal["artifacts"])
        assert invoke([], 0).stdout == invoke([], 0).stdout
        for name, exit_code in (("launch", 0), ("relaxed", 0), ("exhausted", 1),
                                ("length-repair", 0), ("impossible-length", 1), ("mixed", 1)):
            scenario_brief = json.loads((options.fixture.parent / "briefs" / f"{name}.json").read_text())
            report = inspect(invoke(["--scenario", name], exit_code), scenario_brief)
            if name == "exhausted":
                assert any(a["status"] == "unapproved_limit" for a in report["artifacts"])
            if name == "mixed":
                assert sum(a["status"] == "validated" for a in report["artifacts"]) == 1
            if name == "length-repair":
                assert any(len(a["attempts"]) > 1 for a in report["artifacts"])
        relaxed = dict(brief, forbidden_phrases=[], email_max_words=500, docs_max_words=500)
        baseline = custom(relaxed)
        assert all(len(a["attempts"]) == 1 for a in baseline["artifacts"])

        # These constraints are derived from observed output, not implementation constants.
        for audience in ("team_leads", "developers"):
            for required in permutations(brief["required_fact_ids"]):
                custom(dict(relaxed, audience=audience, required_fact_ids=list(required)))
            for budget in (1, 15, 30, 45, 60, 80, 120, 500):
                custom(dict(relaxed, audience=audience, email_max_words=budget, docs_max_words=budget))
        for artifact in baseline["artifacts"]:
            size = artifact["attempts"][0]["word_count"]
            for delta in (-1, 0, 1):
                field = "email_max_words" if artifact["kind"] == "email" else "docs_max_words"
                custom(dict(relaxed, **{field: size + delta}))
        for fid in fact_text:
            custom(dict(relaxed, required_fact_ids=[fid]))
        for phrase in ("meet", "  MEET  ", "explore", "next\tstep", "details", "changes"):
            custom(dict(relaxed, forbidden_phrases=[phrase]))

        malformed = [
            b'{"audience":"team_leads","audience":"developers"}',
            b'{}', b'[]', b'null', b'{', b'\xff', b'x' * 16385,
            b'[' * 1200 + b'0' + b']' * 1200,
            b'{"email_max_words":' + b'9' * 5000 + b'}',
            json.dumps(dict(brief, email_max_words=True)).encode(),
            json.dumps(dict(brief, docs_max_words=0)).encode(),
            json.dumps(dict(brief, docs_max_words=501)).encode(),
            json.dumps(dict(brief, audience="unknown")).encode(),
            json.dumps(dict(brief, required_fact_ids=["unknown"])).encode(),
            json.dumps(dict(brief, extra="secret-marker")).encode(),
            json.dumps(dict(brief, forbidden_phrases=["\ud800"])).encode(),
            json.dumps(dict(brief, forbidden_phrases=["\u0000"])).encode(),
            json.dumps(dict(brief, forbidden_phrases=["meet", " MEET "])).encode(),
            json.dumps(dict(brief, forbidden_phrases=["ss", "\u00df"])).encode(),
            json.dumps(dict(brief, forbidden_phrases=[" \n "])).encode(),
        ]
        for raw in malformed:
            brief_path.write_bytes(raw)
            result = invoke(["--brief", str(brief_path)], 2)
            assert result.stdout == b"" and result.stderr and b"Traceback" not in result.stderr
            assert b"secret-marker" not in result.stderr
        brief_path.write_text(json.dumps(brief))
        link = work / "linked.json"
        link.symlink_to(brief_path)
        fifo = work / "pipe.json"
        os.mkfifo(fifo)
        for path in (link, fifo, work, work / "missing.json"):
            result = invoke(["--brief", str(path)], 2)
            assert result.stdout == b"" and b"Traceback" not in result.stderr
        for unbuffered in ("0", "1"):
            read_fd, write_fd = os.pipe()
            os.close(read_fd)
            try:
                result = subprocess.run(command, cwd=work, stdout=write_fd, stderr=subprocess.PIPE,
                                        env=dict(child_env, PYTHONUNBUFFERED=unbuffered), timeout=5)
            finally:
                os.close(write_fd)
            count += 1
            assert result.returncode == 2, result.stderr
            assert b"Traceback" not in result.stderr
    assert options.fixture.read_bytes() == source_bytes
    print(json.dumps({"result": "passed", "cli_invocations": count, "fixture_sha256": source_digest}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
