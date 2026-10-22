"""Exercise the installed CLI against independently derived contract examples.

This checker uses only the public process boundary. Expected outcomes were
prepared from SPEC before the completed implementation was integrated. It also
checks exact input provenance, redaction, deterministic replay and no execution.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

PROBES = [['direct',
  'secret: Sensitive = "SYNTHETIC_CANARY_NOT_FOR_REPORTS"\nlogger.info(secret)\n',
  'blocked',
  1],
 ['unused_sensitive',
  'secret: Sensitive = "SYNTHETIC_CANARY_NOT_FOR_REPORTS"\nlogger.info("event")\n',
  'passed',
  0],
 ['uncertain',
  'value: Unclassified = "SYNTHETIC_CANARY_NOT_FOR_REPORTS"\nlogger.info(value)\n',
  'review_required',
  2],
 ['undefined', 'logger.info(unbound)\n', 'review_required', 2],
 ['mixed',
  'secret: Sensitive = "SYNTHETIC_CANARY_NOT_FOR_REPORTS"\nlogger.info(secret + unbound)\n',
  'blocked',
  1],
 ['copy_survives_reassignment',
  'secret: Sensitive = "SYNTHETIC_CANARY_NOT_FOR_REPORTS"\n'
  'copy = secret\n'
  'secret = "event"\n'
  'logger.info(copy)\n',
  'blocked',
  1],
 ['reassigned_public',
  'secret: Sensitive = "SYNTHETIC_CANARY_NOT_FOR_REPORTS"\nsecret = "event"\nlogger.info(secret)\n',
  'passed',
  0],
 ['unicode',
  '秘密: Sensitive = "SYNTHETIC_CANARY_NOT_FOR_REPORTS"\nlogger.info(f"前{秘密}")\n',
  'blocked',
  1],
 ['reserved_receiver', 'logger = "event"\nlogger.info("event")\n', 'review_required', 2],
 ['reserved_marker', 'Sensitive = "event"\nlogger.info("event")\n', 'review_required', 2],
 ['bad_label_value', 'secret: Sensitive = 123\nlogger.info(secret)\n', 'review_required', 2],
 ['comment_waiver',
  'secret: Sensitive = "SYNTHETIC_CANARY_NOT_FOR_REPORTS"\n# allow LSL001\nlogger.info(secret)\n',
  'blocked',
  1],
 ['unknown_sink', 'Logger.info("event")\n', 'review_required', 2],
 ['unsupported_method', 'logger.exception("event")\n', 'review_required', 2],
 ['prior_block',
  'secret: Sensitive = "SYNTHETIC_CANARY_NOT_FOR_REPORTS"\n'
  'logger.info(secret)\n'
  'import os\n'
  'logger.info("event")\n',
  'blocked',
  1],
 ['unsupported_prefix',
  'import os\nsecret: Sensitive = "SYNTHETIC_CANARY_NOT_FOR_REPORTS"\nlogger.info(secret)\n',
  'review_required',
  2],
 ['partial_statement',
  'secret: Sensitive = "SYNTHETIC_CANARY_NOT_FOR_REPORTS"\nlogger.info(secret, mask(secret))\n',
  'review_required',
  2],
 ['conversion',
  'secret: Sensitive = "SYNTHETIC_CANARY_NOT_FOR_REPORTS"\nlogger.info(f"{secret!r}")\n',
  'review_required',
  2],
 ['format_spec',
  'secret: Sensitive = "SYNTHETIC_CANARY_NOT_FOR_REPORTS"\nlogger.info(f"{secret:>10}")\n',
  'review_required',
  2],
 ['template_string', 'logger.info(t"event")\n', 'review_required', 2],
 ['masking',
  'secret: Sensitive = "SYNTHETIC_CANARY_NOT_FOR_REPORTS"\nlogger.info(mask(secret))\n',
  'review_required',
  2],
 ['destructuring', 'first, second = "event"\nlogger.info(first)\n', 'review_required', 2],
 ['chained_assign', 'first = second = "event"\nlogger.info(first)\n', 'review_required', 2],
 ['augmented_assign',
  'first = "event"\nfirst += "next"\nlogger.info(first)\n',
  'review_required',
  2],
 ['deletion', 'first = "event"\ndel first\nlogger.info(first)\n', 'review_required', 2],
 ['eight_arguments',
  'logger.info("event","event","event","event","event","event","event","event")\n',
  'passed',
  0],
 ['nine_arguments',
  'logger.info("event","event","event","event","event","event","event","event","event")\n',
  'review_required',
  2],
 ['empty', '', 'passed', 0],
 ['syntax', 'secret = "SYNTHETIC_CANARY_NOT_FOR_REPORTS"\nlogger.info(\n', 'review_required', 2]]
PROBES.extend([
    ["64_statements", 'x = "event"\n' * 64, "passed", 0],
    ["65_statements", 'x = "event"\n' * 65, "review_required", 2],
    ["max_bytes", "#" + "x" * 16383, "passed", 0],
    ["over_bytes", "#" + "x" * 16384, "review_required", 2],
])

SCENARIOS = {
    "clean": ("passed", 0), "blocked": ("blocked", 1),
    "alias": ("blocked", 1), "ambiguous": ("review_required", 2),
    "mixed": ("blocked", 1), "reassigned": ("blocked", 1),
    "unsupported": ("review_required", 2), "masking": ("review_required", 2),
    "prior-block": ("blocked", 1), "syntax-error": ("review_required", 2),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", type=Path, required=True)
    args = parser.parse_args()
    cli = str(args.cli.resolve(strict=True))
    environment = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        environment.pop(key, None)
    environment["PYTHONWARNINGS"] = "error"
    calls = 0
    with tempfile.TemporaryDirectory(prefix="agent14-cli-probes-") as directory:
        def invoke(arguments, data=b""):
            nonlocal calls
            process = subprocess.run(
                [cli, *arguments], input=data, capture_output=True,
                cwd=directory, env=environment, timeout=10,
            )
            calls += 1
            assert process.stderr == b"", (arguments, process.stderr)
            assert b"SYNTHETIC_CANARY_NOT_FOR_REPORTS" not in process.stdout
            record = json.loads(process.stdout)
            return process, record

        for name, text, status, code in PROBES:
            data = text.encode("utf-8")
            process, record = invoke(["--stdin"], data)
            assert (record["status"], process.returncode) == (status, code), name
            if len(data) <= 16384:
                assert record["source_sha256"] == hashlib.sha256(data).hexdigest(), name
                assert record["input_complete"] is True, name
            else:
                assert record["source_sha256"] is None, name
                assert record["input_complete"] is False, name
            repeated, _ = invoke(["--stdin"], data)
            assert repeated.stdout == process.stdout, name
            if name == "mixed":
                assert {finding["kind"] for finding in record["findings"]} == {"violation", "review"}
            if name == "prior_block":
                assert record["coverage"]["complete"] is False
                assert record["coverage"]["statements_analyzed"] == 2
                assert record["coverage"]["log_calls_analyzed"] == 1
            if name == "partial_statement":
                assert record["coverage"]["statements_analyzed"] == 1
                assert record["coverage"]["log_calls_analyzed"] == 0
                assert all(finding["kind"] != "violation" for finding in record["findings"])

        for data in (b"\xff", b"logger.info(\x00)"):
            process, record = invoke(["--stdin"], data)
            assert (record["status"], process.returncode) == ("review_required", 2)
            assert record["source_sha256"] == hashlib.sha256(data).hexdigest()

        for mode in ("always", "error"):
            environment["PYTHONWARNINGS"] = mode
            process, record = invoke(["--stdin"], b'logger.info("\\qSYNTHETIC_CANARY_NOT_FOR_REPORTS")')
            assert (record["status"], process.returncode) == ("passed", 0)

        sentinel = Path(directory) / "must-not-exist"
        source = f'__import__("pathlib").Path({str(sentinel)!r}).write_text("executed")'.encode()
        process, record = invoke(["--stdin"], source)
        assert (record["status"], process.returncode) == ("review_required", 2)
        assert not sentinel.exists()

        process, listing = invoke(["--list-scenarios"])
        assert process.returncode == 0
        assert set(listing["scenarios"]) == set(SCENARIOS)
        for scenario, outcome in SCENARIOS.items():
            process, record = invoke(["--scenario", scenario])
            assert (record["status"], process.returncode) == outcome, scenario

        for arguments in ([], ["--stdin", "--scenario", "clean"], ["--scenario", "../../missing"], ["SYNTHETIC_CANARY_NOT_FOR_REPORTS"]):
            process, record = invoke(arguments)
            assert (record["status"], process.returncode) == ("failed", 3)

    print(json.dumps({"result": "passed", "stdin_examples": len(PROBES), "cli_invocations": calls, "packaged_scenarios": len(SCENARIOS)}, sort_keys=True))


if __name__ == "__main__":
    main()
