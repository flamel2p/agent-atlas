import json
import os
from pathlib import Path
import shutil
import signal
import socket
import sys
import threading
import time

import pytest

from tool_using.cli import main, parse_config
from tool_using.contracts import Decision, Failure, RunConfig, ToolCall
from tool_using.controller import exit_code, run


CASE = Path(__file__).resolve().parents[1]


@pytest.fixture
def case(tmp_path):
    (tmp_path / "fixtures").mkdir()
    shutil.copyfile(CASE / "fixtures/campaigns.csv", tmp_path / "fixtures/campaigns.csv")
    return tmp_path


class ScenarioBackend:
    def __init__(self, config):
        self.config = config
        self.step = 0

    def next(self, result):
        self.step += 1
        scenario = self.config.task
        if scenario == "hang":
            time.sleep(20)
        if scenario == "repeat":
            return Decision((ToolCall("inspect_dataset", "{}", str(self.step)),))
        if scenario == "multi":
            return Decision((ToolCall("sum_by_channel", '{"metric":"revenue_sen"}', "1"), ToolCall("sum_by_channel", '{"metric":"spend_sen"}', "2")))
        if scenario == "premature":
            return Decision()
        if scenario == "exception":
            raise RuntimeError("sk-synthetic-secret-that-must-not-be-logged")
        if scenario == "billable-refusal":
            self.last_metadata = {"reported_model": "gpt-6-luna", "usage": {"input_tokens": 20, "output_tokens": 5, "total_tokens": 25}}
            raise Failure("provider_refusal", phase="provider")
        if self.step == 1:
            return Decision((ToolCall("sum_by_channel", '{"metric":"revenue_sen"}', "1"),))
        if self.step == 2:
            return Decision((ToolCall("render_bar_chart", json.dumps({"summary_id": result["summary_id"]}), "2"),))
        if scenario == "fail-after-chart":
            raise Failure("provider_error", phase="provider")
        if scenario == "hang-after-chart":
            time.sleep(20)
        return Decision()

    def close(self):
        pass


def scenario_backend(config):
    return ScenarioBackend(config)


def blocked_renderer_backend(config):
    from tool_using.tools import ToolSet

    def blocked(self):
        time.sleep(20)

    ToolSet._render = blocked
    return ScenarioBackend(config)


def offline_backend(config):
    from tool_using.backends import ReplayBackend
    assert "openai" not in sys.modules

    def blocked(*args, **kwargs):
        raise AssertionError("Replay attempted outbound network")

    socket.socket.connect = blocked
    socket.create_connection = blocked
    return ReplayBackend(config)


def report_files(root, result):
    return root / "artifacts" / result["run_id"]


@pytest.mark.parametrize("example,output_format,metric,totals", [
    ("spend-by-channel-table", "table", "spend_sen", [5000, 25000, 20000]),
    ("revenue-by-channel-bar", "bar", "revenue_sen", [30000, 75000, 40000]),
])
def test_replay_complete_and_offline(case, monkeypatch, example, output_format, metric, totals):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    config = RunConfig(example=example, output_format=output_format)
    result = run(config, root=case, backend_factory=offline_backend)
    assert result["status"] == "completed", result
    assert result["summary"]["metric"] == metric
    assert [row["total_sen"] for row in result["summary"]["totals"]] == totals
    assert result["provider"] is None
    assert result["intent_validation"] == "not_performed"
    directory = report_files(case, result)
    assert json.loads((directory / "report.json").read_text()) == result
    assert (directory / "chart.png").exists() == (output_format == "bar")
    assert not (directory / "chart.pending.png").exists()
    if result["chart"]:
        assert result["chart"]["summary_id"] == result["summary"]["summary_id"]
    events = [json.loads(line) for line in (directory / "trace.jsonl").read_text().splitlines()]
    assert events[-1]["status"] == "completed"


def test_invalid_replay_is_rejected_without_chart(case):
    result = run(RunConfig(example="invalid-tool-call", output_format="table"), root=case)
    assert result["status"] == "rejected"
    assert exit_code(result) == 2
    assert result["summary"] is result["chart"] is None
    assert not (report_files(case, result) / "chart.png").exists()


@pytest.mark.parametrize("scenario,code", [
    ("premature", "incomplete_result"),
    ("repeat", "limit_reached"),
    ("multi", "invalid_tool_call"),
    ("exception", "invalid_tool_result"),
    ("fail-after-chart", "provider_error"),
])
def test_terminal_failures_never_publish(case, scenario, code):
    result = run(RunConfig(task=scenario), root=case, backend_factory=scenario_backend)
    assert result["status"] != "completed"
    assert result["error"]["code"] == code, result
    assert result["summary"] is result["chart"] is None
    directory = report_files(case, result)
    assert not (directory / "chart.png").exists()
    assert not (directory / "chart.pending.png").exists()
    assert "sk-synthetic-secret" not in (directory / "trace.jsonl").read_text()
    assert "sk-synthetic-secret" not in json.dumps(result)
    if scenario == "multi":
        assert "tool_result" not in (directory / "trace.jsonl").read_text()


def test_hard_request_deadline_interrupts_blocked_backend(case):
    started = time.monotonic()
    result = run(RunConfig(mode="live", task="hang", example=None), root=case, api_key="synthetic-test-key", backend_factory=scenario_backend, request_seconds=0.25, run_seconds=5)
    assert result["error"]["code"] == "provider_timeout", result
    assert time.monotonic() - started < 4
    assert result["chart"] is None


def test_hard_run_deadline_interrupts_blocked_operation(case):
    started = time.monotonic()
    result = run(RunConfig(task="hang"), root=case, backend_factory=scenario_backend, run_seconds=0.75)
    assert result["status"] == "limit_reached"
    assert time.monotonic() - started < 3
    assert result["chart"] is None


def test_hard_run_deadline_interrupts_renderer(case):
    result = run(RunConfig(task="render"), root=case, backend_factory=blocked_renderer_backend, run_seconds=1.5)
    assert result["status"] == "limit_reached"
    directory = report_files(case, result)
    assert not (directory / "chart.png").exists()
    assert '"tool": "sum_by_channel"' in (directory / "trace.jsonl").read_text()


def test_usage_is_retained_on_provider_refusal(case):
    result = run(RunConfig(mode="live", task="billable-refusal", example=None), root=case, api_key="synthetic-test-key", backend_factory=scenario_backend)
    assert result["error"]["code"] == "provider_refusal"
    assert result["provider"]["usage"] == {"input_tokens": 20, "output_tokens": 5, "total_tokens": 25}
    assert result["provider"]["responses"] == 1


def test_cancellation_is_reported_and_worker_stopped(case):
    interrupt = threading.Timer(0.75, lambda: os.kill(os.getpid(), signal.SIGINT))
    interrupt.start()
    try:
        result = run(RunConfig(task="hang"), root=case, backend_factory=scenario_backend, run_seconds=5)
    finally:
        interrupt.cancel()
    assert result["status"] == "cancelled", result
    assert exit_code(result) == 130
    assert result["chart"] is None


def test_missing_credentials_has_no_artifact_effect(case):
    result = run(RunConfig(mode="live", example=None), root=case)
    assert result["error"]["code"] == "missing_credentials"
    assert exit_code(result) == 2
    assert not (case / "artifacts").exists()


def test_symlink_artifacts_rejected(case, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (case / "artifacts").symlink_to(outside, target_is_directory=True)
    result = run(RunConfig(), root=case)
    assert result["error"]["code"] == "artifact_error"
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize("swapped_parent", ["run", "artifacts"])
def test_publication_rollback_does_not_follow_swapped_directory(case, tmp_path, monkeypatch, swapped_parent):
    import tool_using.controller as controller

    outside = tmp_path / "outside"
    outside.mkdir()
    publish = controller._publish
    protected = []

    def swap_then_publish(run_dir, root, report):
        target = run_dir if swapped_parent == "run" else run_dir.parent
        target.rename(target.with_name(target.name + "-original"))
        target.symlink_to(outside, target_is_directory=True)
        external_run = outside if swapped_parent == "run" else outside / run_dir.name
        external_run.mkdir(exist_ok=True)
        for name in ("chart.png", "chart.pending.png", "report.pending.json"):
            path = external_run / name
            path.write_text("unrelated file")
            protected.append(path)
        publish(run_dir, root, report)

    monkeypatch.setattr(controller, "_publish", swap_then_publish)
    result = run(RunConfig(example="spend-by-channel-table", output_format="table"), root=case)
    assert result["error"]["code"] == "artifact_error", result
    assert all(path.read_text() == "unrelated file" for path in protected)


def test_cancellation_during_publication_rolls_back_chart(case, monkeypatch):
    import tool_using.controller as controller

    open_new = controller._open_new
    interrupted = False

    def interrupt_once(path):
        nonlocal interrupted
        if path.name == "report.pending.json" and not interrupted:
            interrupted = True
            assert (path.parent / "chart.png").exists()
            raise KeyboardInterrupt
        return open_new(path)

    monkeypatch.setattr(controller, "_open_new", interrupt_once)
    result = run(RunConfig(), root=case)
    assert result["status"] == "cancelled", result
    assert exit_code(result) == 130
    assert result["summary"] is result["chart"] is None
    directory = report_files(case, result)
    assert not (directory / "chart.png").exists()
    assert not (directory / "chart.pending.png").exists()
    assert json.loads((directory / "report.json").read_text()) == result
    assert json.loads((directory / "trace.jsonl").read_text().splitlines()[-1])["status"] == "cancelled"


@pytest.mark.parametrize("argv", [
    ["--task", "secret text"], ["--format", "bar"],
    ["--mode", "live"], ["--mode", "live", "--task", " "],
    ["--mode", "live", "--task", "a" * 501],
    ["--mode", "live", "--task", "x", "--example", "invalid-tool-call"],
    ["--output-dir", "/tmp"], ["--model", "different-model"],
])
def test_cli_rejects_invalid_contract(argv, capsys):
    assert main(argv) == 2
    output = capsys.readouterr().out
    result = json.loads(output)
    assert result["error"]["code"] == "invalid_input"
    assert "secret text" not in output


def test_cli_defaults_and_live_normalization():
    assert parse_config([]) == RunConfig()
    config = parse_config(["--mode", "live", "--task", " Spend by channel "])
    assert config == RunConfig(mode="live", task="Spend by channel", output_format="table", example=None)
