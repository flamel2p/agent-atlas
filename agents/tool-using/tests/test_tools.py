import hashlib
import json
import os
from pathlib import Path
import struct

import pytest

from tool_using.contracts import DATASET_ID, Failure
from tool_using.tools import MAX_DATASET_BYTES, ToolSet, tool_schemas


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "campaigns.csv"
CSV_BYTES = FIXTURE.read_bytes()


def make_case(tmp_path, output_format="table", data=CSV_BYTES, run_id="test-run"):
    root = tmp_path / "case"
    (root / "fixtures").mkdir(parents=True, exist_ok=True)
    (root / "fixtures" / "campaigns.csv").write_bytes(data)
    run_dir = root / "artifacts" / run_id
    run_dir.mkdir(parents=True)
    return root, run_dir, ToolSet(root, run_dir, run_id, output_format)


def sum_metric(tools, metric="revenue_sen"):
    return tools.execute("sum_by_channel", json.dumps({"metric": metric}))


def render(tools, summary):
    return tools.execute("render_bar_chart", json.dumps({"summary_id": summary["summary_id"]}))


@pytest.mark.parametrize("metric,expected", [
    ("revenue_sen", [("Email", 30000, "RM 300.00"), ("Search", 75000, "RM 750.00"), ("Social", 40000, "RM 400.00")]),
    ("spend_sen", [("Email", 5000, "RM 50.00"), ("Search", 25000, "RM 250.00"), ("Social", 20000, "RM 200.00")]),
])
def test_exact_totals_and_provenance(tmp_path, metric, expected):
    _, run_dir, tools = make_case(tmp_path)
    inspection = tools.execute("inspect_dataset", "{}")
    assert inspection["dataset_id"] == DATASET_ID
    assert inspection["dataset_sha256"] == hashlib.sha256(CSV_BYTES).hexdigest()
    assert inspection["row_count"] == 6
    assert inspection["channels"] == ["Email", "Search", "Social"]
    summary = sum_metric(tools, metric)
    assert [(row["channel"], row["total_sen"], row["display"]) for row in summary["totals"]] == expected
    assert summary["metric"] == metric
    assert summary["operation"] == "sum"
    assert summary["unit"] == "sen"
    assert summary["currency"] == "MYR"
    assert summary["dataset_sha256"] == inspection["dataset_sha256"]
    assert tools.finish() == (summary, None)
    assert not list(run_dir.iterdir())


def test_fixture_is_read_once_and_return_values_do_not_mutate_state(tmp_path):
    root, _, tools = make_case(tmp_path)
    (root / "fixtures" / "campaigns.csv").write_text("invalid")
    summary = sum_metric(tools)
    summary["totals"][0]["total_sen"] = 1
    exposed = tools.summary
    exposed["totals"].clear()
    final, _ = tools.finish()
    assert final["totals"][0]["total_sen"] == 30000
    assert final["dataset_sha256"] == hashlib.sha256(CSV_BYTES).hexdigest()


def test_real_chart_is_staged_with_exact_geometry_and_provenance(tmp_path, monkeypatch):
    _, run_dir, tools = make_case(tmp_path, "bar")
    summary = sum_metric(tools)
    monkeypatch.setenv("MPLCONFIGDIR", str(tmp_path / "must-not-be-used"))
    chart = render(tools, summary)
    assert chart["summary_id"] == summary["summary_id"]
    assert chart["path"] == "artifacts/test-run/chart.png"
    assert (chart["width"], chart["height"]) == (960, 540)
    png = (run_dir / "chart.pending.png").read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", png[16:24]) == (960, 540)
    assert not (run_dir / "chart.png").exists()
    assert (run_dir / ".plot-cache").is_dir()
    assert not (tmp_path / "must-not-be-used").exists()
    assert tools.finish() == (summary, chart)


def test_schema_exposes_only_format_permitted_tools_and_required_strict_fields():
    table = tool_schemas("table")
    bar = tool_schemas("bar")
    assert [item["name"] for item in table] == ["inspect_dataset", "sum_by_channel"]
    assert [item["name"] for item in bar] == ["inspect_dataset", "sum_by_channel", "render_bar_chart"]
    for item in bar:
        assert item["strict"] is True
        assert item["type"] == "function"
        assert item["parameters"]["additionalProperties"] is False
        assert set(item["parameters"]["required"]) == set(item["parameters"]["properties"])
    assert bar[1]["parameters"]["properties"]["metric"]["enum"] == ["spend_sen", "revenue_sen"]


@pytest.mark.parametrize("name,arguments", [
    ("average_by_channel", '{}'),
    ("sum_by_channel", '{"metric":"revenue_sen","operation":"average"}'),
    ("sum_by_channel", '{"metric":"average"}'),
    ("sum_by_channel", '{"metric":true}'),
    ("sum_by_channel", '{"metric":1}'),
    ("sum_by_channel", '{"metric":null}'),
    ("sum_by_channel", '{}'),
    ("sum_by_channel", '[]'),
    ("sum_by_channel", '{broken}'),
    ("sum_by_channel", '{"metric":"revenue_sen","metric":"spend_sen"}'),
    ("sum_by_channel", '{"metric":NaN}'),
    ("inspect_dataset", '{"path":"/etc/passwd"}'),
    ("inspect_dataset", '{} trailing'),
    ("render_bar_chart", '{"summary_id":"invented"}'),
    ("inspect_dataset", " " * 4097),
])
def test_forbidden_or_malformed_calls_reject_without_effects(tmp_path, name, arguments):
    _, run_dir, tools = make_case(tmp_path)
    with pytest.raises(Failure) as caught:
        tools.execute(name, arguments)
    assert caught.value.code == "invalid_tool_call"
    assert caught.value.status == "rejected"
    assert tools.last_arguments == {}
    assert tools.summary is None
    assert not list(run_dir.iterdir())


@pytest.mark.parametrize("data", [
    b"date,channel,spend_sen\n2026-09-01,Email,100\n",
    b"date,channel,spend_sen,revenue_sen,extra\n2026-09-01,Email,100,200,x\n",
    b"date,channel,spend_sen,spend_sen\n2026-09-01,Email,100,200\n",
    b"date,channel,spend_sen,revenue_sen\n",
    CSV_BYTES.replace(b"2026-09-01", b"2026-02-30", 1),
    CSV_BYTES.replace(b"2026-09-01", b"2026-9-1", 1),
    CSV_BYTES.replace(b"Search", b"Unknown", 1),
    CSV_BYTES.replace(b"10000", b"", 1),
    CSV_BYTES.replace(b"10000", b" ", 1),
    CSV_BYTES.replace(b"10000", b"-1", 1),
    CSV_BYTES.replace(b"10000", b"1.5", 1),
    CSV_BYTES.replace(b"10000", b"1e4", 1),
    CSV_BYTES.replace(b"10000", b"100000001", 1),
    CSV_BYTES.replace(b"10000", b" 10000", 1),
    CSV_BYTES + b"2026-09-01,Search,10000,30000\n",
    CSV_BYTES + b"\n",
    CSV_BYTES + b"2026-09-03,Email,1,2,3\n",
    CSV_BYTES + b"\xff",
    b"x" * (MAX_DATASET_BYTES + 1),
])
def test_bad_dataset_is_terminal_before_results(tmp_path, data):
    with pytest.raises(Failure) as caught:
        make_case(tmp_path, data=data)
    assert caught.value.code == "invalid_dataset"


def test_dataset_row_limit(tmp_path):
    from datetime import date, timedelta

    rows = [f"{date(2026, 1, 1) + timedelta(days=index)},Email,1,2" for index in range(101)]
    data = ("date,channel,spend_sen,revenue_sen\n" + "\n".join(rows)).encode()
    with pytest.raises(Failure, match="dataset"):
        make_case(tmp_path, data=data)


@pytest.mark.parametrize("location", ["file", "directory"])
def test_symlinked_fixture_is_rejected(tmp_path, location):
    root, run_dir, _ = make_case(tmp_path)
    fixture = root / "fixtures" / "campaigns.csv"
    if location == "file":
        alternate = root / "real.csv"
        fixture.rename(alternate)
        fixture.symlink_to(alternate)
    else:
        alternate = root / "real-fixtures"
        fixture.parent.rename(alternate)
        (root / "fixtures").symlink_to(alternate, target_is_directory=True)
    with pytest.raises(Failure) as caught:
        ToolSet(root, run_dir, "test-run", "table")
    assert caught.value.code == "invalid_dataset"


def test_missing_fixture(tmp_path):
    root, run_dir, _ = make_case(tmp_path)
    (root / "fixtures" / "campaigns.csv").unlink()
    with pytest.raises(Failure) as caught:
        ToolSet(root, run_dir, "test-run", "table")
    assert caught.value.code == "invalid_dataset"


def test_nonregular_fixture_rejects_without_blocking(tmp_path):
    root, run_dir, _ = make_case(tmp_path)
    fixture = root / "fixtures" / "campaigns.csv"
    fixture.unlink()
    os.mkfifo(fixture)
    with pytest.raises(Failure) as caught:
        ToolSet(root, run_dir, "test-run", "table")
    assert caught.value.code == "invalid_dataset"


@pytest.mark.parametrize("location", ["run", "artifacts"])
def test_symlinked_output_is_rejected(tmp_path, location):
    root, run_dir, _ = make_case(tmp_path)
    original = run_dir if location == "run" else run_dir.parent
    alternate = tmp_path / "real-output"
    original.rename(alternate)
    original.symlink_to(alternate, target_is_directory=True)
    with pytest.raises(Failure) as caught:
        ToolSet(root, run_dir, "test-run", "table")
    assert caught.value.code == "artifact_error"


def test_escaping_output_is_rejected(tmp_path):
    root, _, _ = make_case(tmp_path)
    external = tmp_path / "external"
    external.mkdir()
    with pytest.raises(Failure) as caught:
        ToolSet(root, external, "test-run", "table")
    assert caught.value.code == "artifact_error"


def test_invented_or_cross_run_handle_is_rejected(tmp_path):
    _, _, tools = make_case(tmp_path, "bar")
    sum_metric(tools)
    with pytest.raises(Failure) as caught:
        render(tools, {"summary_id": "summary-" + "0" * 32})
    assert caught.value.code == "invalid_state"
    assert tools.summary is None


def test_duplicate_summary_cannot_replace_valid_state(tmp_path):
    _, _, tools = make_case(tmp_path)
    sum_metric(tools)
    with pytest.raises(Failure) as caught:
        sum_metric(tools, "spend_sen")
    assert caught.value.code == "invalid_state"
    assert tools.summary is None
    with pytest.raises(Failure):
        tools.finish()


def test_duplicate_chart_rejected_before_second_render(tmp_path, monkeypatch):
    _, _, tools = make_case(tmp_path, "bar")
    summary = sum_metric(tools)
    render(tools, summary)
    monkeypatch.setattr(tools, "_render", lambda: pytest.fail("duplicate render reached executor"))
    with pytest.raises(Failure) as caught:
        render(tools, summary)
    assert caught.value.code == "invalid_state"
    assert tools.chart is None


@pytest.mark.parametrize("change", ["amount", "provenance", "extra", "boolean", "display"])
def test_invalid_result_cannot_enter_state(tmp_path, monkeypatch, change):
    _, _, tools = make_case(tmp_path)
    original = tools._sum

    def invalid_sum(metric):
        result = original(metric)
        if change == "amount":
            result["totals"][0]["total_sen"] += 1
        elif change == "provenance":
            result["dataset_sha256"] = "0" * 64
        elif change == "extra":
            result["unexpected"] = "value"
        elif change == "boolean":
            result["totals"][0]["total_sen"] = True
        else:
            result["totals"][0]["display"] = "RM 0.00"
        return result

    monkeypatch.setattr(tools, "_sum", invalid_sum)
    with pytest.raises(Failure) as caught:
        sum_metric(tools)
    assert caught.value.code == "invalid_tool_result"
    assert tools.summary is None
    assert tools.chart is None


def test_inspection_result_provenance_is_validated(tmp_path, monkeypatch):
    _, _, tools = make_case(tmp_path)
    result = tools._inspect()
    result["dataset_sha256"] = "0" * 64
    monkeypatch.setattr(tools, "_inspect", lambda: result)
    with pytest.raises(Failure) as caught:
        tools.execute("inspect_dataset", "{}")
    assert caught.value.code == "invalid_tool_result"


def test_failed_aggregation_blocks_render_and_sanitizes_exception(tmp_path, monkeypatch):
    _, run_dir, tools = make_case(tmp_path, "bar")

    def broken_sum(_):
        raise RuntimeError("private credentials and source data")

    monkeypatch.setattr(tools, "_sum", broken_sum)
    with pytest.raises(Failure) as caught:
        sum_metric(tools)
    assert "private" not in str(caught.value)
    assert caught.value.code == "invalid_tool_result"
    with pytest.raises(Failure) as caught:
        render(tools, {"summary_id": "invented"})
    assert caught.value.code == "invalid_state"
    assert not list(run_dir.iterdir())
    with pytest.raises(Failure):
        tools.finish()


@pytest.mark.parametrize("location", ["chart.pending.png", ".plot-cache"])
def test_symlinked_chart_or_cache_cannot_write_target(tmp_path, location):
    _, run_dir, tools = make_case(tmp_path, "bar")
    summary = sum_metric(tools)
    target = tmp_path / "protected"
    if location == ".plot-cache":
        target.mkdir()
    else:
        target.write_bytes(b"do not replace")
    (run_dir / location).symlink_to(target, target_is_directory=target.is_dir())
    with pytest.raises(Failure) as caught:
        render(tools, summary)
    assert caught.value.code == "artifact_error"
    if target.is_dir():
        assert list(target.iterdir()) == []
    else:
        assert target.read_bytes() == b"do not replace"
    assert tools.summary is None
    assert tools.chart is None


def test_finish_rejects_corrupted_staged_chart(tmp_path):
    _, run_dir, tools = make_case(tmp_path, "bar")
    summary = sum_metric(tools)
    render(tools, summary)
    (run_dir / "chart.pending.png").write_bytes(b"not a PNG")
    with pytest.raises(Failure) as caught:
        tools.finish()
    assert caught.value.code == "invalid_tool_result"


@pytest.mark.parametrize("output_format", ["table", "bar"])
def test_premature_completion_requires_summary_and_requested_chart(tmp_path, output_format):
    _, _, tools = make_case(tmp_path, output_format)
    with pytest.raises(Failure) as caught:
        tools.finish()
    assert caught.value.code == "incomplete_result"
    if output_format == "bar":
        sum_metric(tools)
        with pytest.raises(Failure) as caught:
            tools.finish()
        assert caught.value.code == "incomplete_result"
