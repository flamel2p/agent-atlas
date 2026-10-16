from __future__ import annotations

import csv
from copy import deepcopy
from dataclasses import dataclass
from datetime import date
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import struct
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .contracts import DATASET_ID, Failure


COLUMNS = ("date", "channel", "spend_sen", "revenue_sen")
CHANNELS = ("Email", "Search", "Social")
METRICS = ("spend_sen", "revenue_sen")
MAX_DATASET_BYTES = 64 * 1024
MAX_ROWS = 100
PNG_SIZE = (960, 540)
Metric = Literal["spend_sen", "revenue_sen"]
Channel = Literal["Email", "Search", "Social"]


class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class InspectArguments(StrictModel):
    pass


class SumArguments(StrictModel):
    metric: Metric


class ChartArguments(StrictModel):
    summary_id: str = Field(min_length=1, max_length=100)


class Total(StrictModel):
    channel: Channel
    total_sen: int = Field(ge=0, le=MAX_ROWS * 100000000)
    display: str


class Summary(StrictModel):
    summary_id: str = Field(pattern=r"^summary-[a-f0-9]{32}$")
    dataset_id: Literal["campaign-demo-v1"]
    dataset_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    metric: Metric
    group_by: Literal["channel"]
    operation: Literal["sum"]
    unit: Literal["sen"]
    currency: Literal["MYR"]
    totals: list[Total] = Field(min_length=1, max_length=3)


class Inspection(StrictModel):
    dataset_id: Literal["campaign-demo-v1"]
    dataset_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    row_count: int = Field(ge=1, le=MAX_ROWS)
    columns: list[str]
    supported_metrics: list[Metric]
    channels: list[Channel]
    currency: Literal["MYR"]
    unit: Literal["sen"]


class Chart(StrictModel):
    artifact_id: str = Field(pattern=r"^chart-[a-f0-9]{32}$")
    summary_id: str = Field(pattern=r"^summary-[a-f0-9]{32}$")
    path: str
    width: int
    height: int


@dataclass(frozen=True)
class Row:
    date: date
    channel: str
    spend_sen: int
    revenue_sen: int


def tool_schemas(output_format: str) -> list[dict]:
    if output_format not in ("table", "bar"):
        raise Failure("invalid_input", status="rejected", phase="configuration")
    tools = [
        ("inspect_dataset", "Inspect the fixed synthetic campaign dataset and available metrics.", InspectArguments),
        ("sum_by_channel", "Sum one metric by channel over the entire fixed dataset. May run only once.", SumArguments),
    ]
    if output_format == "bar":
        tools.append(("render_bar_chart", "Render the current run's computed summary as a bar chart. May run only once.", ChartArguments))
    schemas = []
    for name, description, model in tools:
        parameters = model.model_json_schema()
        parameters.setdefault("required", [])
        schemas.append({"type": "function", "name": name, "description": description,
                        "strict": True, "parameters": parameters})
    return schemas


def _check_location(path: Path, base: Path) -> None:
    try:
        relative = path.relative_to(base)
        current = base
        if current.is_symlink():
            raise ValueError
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                raise ValueError
        path.resolve(strict=True).relative_to(base.resolve(strict=True))
    except (OSError, ValueError, RuntimeError):
        raise ValueError("Unsafe location") from None


def _read_bounded(path: Path, limit: int) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(descriptor, "rb") as source:
        metadata = os.fstat(source.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > limit:
            raise ValueError("Invalid file")
        data = source.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Oversized file")
    return data


def _load_dataset(case_root: Path) -> tuple[tuple[Row, ...], str]:
    path = case_root / "fixtures" / "campaigns.csv"
    try:
        _check_location(path, case_root)
        data = _read_bounded(path, MAX_DATASET_BYTES)
        reader = csv.reader(io.StringIO(data.decode("utf-8"), newline=""), strict=True)
        columns = next(reader)
        if len(columns) != len(COLUMNS) or set(columns) != set(COLUMNS):
            raise ValueError
        rows = []
        seen = set()
        for cells in reader:
            if len(rows) >= MAX_ROWS or len(cells) != len(COLUMNS) or any(not cell.strip() for cell in cells):
                raise ValueError
            values = dict(zip(columns, cells, strict=True))
            if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", values["date"]):
                raise ValueError
            row_date = date.fromisoformat(values["date"])
            channel = values["channel"]
            if channel not in CHANNELS or (row_date, channel) in seen:
                raise ValueError
            amounts = []
            for metric in METRICS:
                if not re.fullmatch(r"[0-9]{1,9}", values[metric]):
                    raise ValueError
                amount = int(values[metric])
                if amount > 100000000:
                    raise ValueError
                amounts.append(amount)
            rows.append(Row(row_date, channel, *amounts))
            seen.add((row_date, channel))
        if not rows:
            raise ValueError
        return tuple(rows), hashlib.sha256(data).hexdigest()
    except (OSError, ValueError, UnicodeError, csv.Error, StopIteration, RuntimeError):
        raise Failure("invalid_dataset", phase="dataset") from None


def _json_object(arguments: str) -> dict:
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError
            result[key] = value
        return result

    def invalid_constant(_):
        raise ValueError

    if not isinstance(arguments, str) or len(arguments) > 4096:
        raise ValueError
    result = json.loads(arguments, object_pairs_hook=unique_pairs, parse_constant=invalid_constant)
    if not isinstance(result, dict):
        raise ValueError
    return result


def _display(sen: int) -> str:
    return f"RM {sen // 100}.{sen % 100:02d}"


class ToolSet:
    def __init__(self, case_root: Path, run_dir: Path, run_id: str, output_format: str):
        self._summary: dict | None = None
        self._chart: dict | None = None
        self._failed = False
        self.last_arguments: dict = {}
        if output_format not in ("table", "bar"):
            raise Failure("invalid_input", status="rejected", phase="configuration")
        self.output_format = output_format
        try:
            if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", run_id):
                raise ValueError
            case_root = Path(case_root)
            if case_root.is_symlink() or not case_root.is_dir():
                raise ValueError
            self.case_root = case_root.resolve(strict=True)
            self.run_id = run_id
            self.run_dir = Path(run_dir).absolute()
            expected = self.case_root / "artifacts" / run_id
            _check_location(self.run_dir, self.case_root)
            if self.run_dir.resolve(strict=True) != expected or not self.run_dir.is_dir():
                raise ValueError
        except (OSError, ValueError, RuntimeError):
            raise Failure("artifact_error", phase="artifacts") from None
        self._rows, self.dataset_sha256 = _load_dataset(self.case_root)

    @property
    def summary(self) -> dict | None:
        return deepcopy(self._summary)

    @property
    def chart(self) -> dict | None:
        return deepcopy(self._chart)

    def execute(self, name: str, arguments: str) -> dict:
        self.last_arguments = {}
        try:
            if self._failed:
                raise Failure("invalid_state", status="rejected", phase="tool")
            models = {"inspect_dataset": InspectArguments, "sum_by_channel": SumArguments}
            if self.output_format == "bar":
                models["render_bar_chart"] = ChartArguments
            if not isinstance(name, str) or name not in models:
                raise Failure("invalid_tool_call", status="rejected", phase="tool")
            try:
                validated = models[name].model_validate(_json_object(arguments)).model_dump()
            except (ValueError, TypeError, RecursionError, ValidationError):
                raise Failure("invalid_tool_call", status="rejected", phase="tool") from None
            self.last_arguments = deepcopy(validated)
            if name == "inspect_dataset":
                result = self._inspect()
            elif name == "sum_by_channel":
                if self._summary is not None:
                    raise Failure("invalid_state", status="rejected", phase="tool")
                result = self._sum(validated["metric"])
            else:
                if self._summary is None or self._chart is not None or validated["summary_id"] != self._summary["summary_id"]:
                    raise Failure("invalid_state", status="rejected", phase="tool")
                result = self._render()
            result = self._validate_result(name, result, validated)
            if name == "sum_by_channel":
                self._summary = deepcopy(result)
            elif name == "render_bar_chart":
                self._chart = deepcopy(result)
            return deepcopy(result)
        except Failure:
            self._failed = True
            self._summary = self._chart = None
            raise
        except Exception:
            self._failed = True
            self._summary = self._chart = None
            raise Failure("invalid_tool_result", phase="tool") from None

    def _expected_inspection(self) -> dict:
        return {
            "dataset_id": DATASET_ID, "dataset_sha256": self.dataset_sha256,
            "row_count": len(self._rows), "columns": list(COLUMNS),
            "supported_metrics": list(METRICS), "channels": sorted({row.channel for row in self._rows}),
            "currency": "MYR", "unit": "sen",
        }

    def _inspect(self) -> dict:
        return self._expected_inspection()

    def _computed_summary(self, metric: str, summary_id: str) -> dict:
        totals = {}
        for row in self._rows:
            totals[row.channel] = totals.get(row.channel, 0) + getattr(row, metric)
        return {
            "summary_id": summary_id, "dataset_id": DATASET_ID,
            "dataset_sha256": self.dataset_sha256, "metric": metric,
            "group_by": "channel", "operation": "sum", "unit": "sen", "currency": "MYR",
            "totals": [{"channel": channel, "total_sen": total, "display": _display(total)}
                       for channel, total in sorted(totals.items())],
        }

    def _sum(self, metric: str) -> dict:
        return self._computed_summary(metric, f"summary-{uuid.uuid4().hex}")

    def _chart_dimensions(self) -> tuple[int, int]:
        path = self.run_dir / "chart.pending.png"
        _check_location(path, self.case_root)
        data = _read_bounded(path, 2 * 1024 * 1024)
        if (len(data) < 45 or data[:8] != b"\x89PNG\r\n\x1a\n"
                or data[8:16] != b"\x00\x00\x00\rIHDR"
                or data[-12:] != b"\x00\x00\x00\x00IEND\xaeB`\x82"):
            raise ValueError
        dimensions = struct.unpack(">II", data[16:24])
        if dimensions != PNG_SIZE:
            raise ValueError
        return dimensions

    def _render(self) -> dict:
        try:
            _check_location(self.run_dir, self.case_root)
            cache = self.run_dir / ".plot-cache"
            cache.mkdir(mode=0o700, exist_ok=False)
            _check_location(cache, self.case_root)
            os.environ["MPLCONFIGDIR"] = str(cache)
            import matplotlib
            matplotlib.use("Agg", force=True)
            from matplotlib.backends.backend_agg import FigureCanvasAgg
            from matplotlib.figure import Figure

            summary = self._summary
            figure = Figure(figsize=(9.6, 5.4), dpi=100, layout="constrained")
            FigureCanvasAgg(figure)
            axis = figure.subplots()
            totals = summary["totals"]
            bars = axis.bar([row["channel"] for row in totals], [row["total_sen"] / 100 for row in totals])
            axis.bar_label(bars, labels=[row["display"] for row in totals], padding=4)
            axis.set_title(f"Total {'revenue' if summary['metric'] == 'revenue_sen' else 'spend'} by channel")
            axis.set_ylabel("RM")
            axis.set_ylim(bottom=0, top=max(1, max(row["total_sen"] for row in totals) / 100 * 1.15))
            path = self.run_dir / "chart.pending.png"
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
            with os.fdopen(descriptor, "wb") as target:
                figure.savefig(target, format="png", dpi=100)
            figure.clear()
            self._chart_dimensions()
            return {
                "artifact_id": f"chart-{uuid.uuid4().hex}", "summary_id": summary["summary_id"],
                "path": f"artifacts/{self.run_id}/chart.png", "width": PNG_SIZE[0], "height": PNG_SIZE[1],
            }
        except Exception:
            raise Failure("artifact_error", phase="tool") from None

    def _validate_result(self, name: str, result: dict, arguments: dict) -> dict:
        try:
            model = {"inspect_dataset": Inspection, "sum_by_channel": Summary, "render_bar_chart": Chart}[name]
            validated = model.model_validate(result).model_dump()
            if name == "inspect_dataset":
                if validated != self._expected_inspection():
                    raise ValueError
            elif name == "sum_by_channel":
                if validated != self._computed_summary(arguments["metric"], validated["summary_id"]):
                    raise ValueError
            else:
                if (self._summary is None or validated["summary_id"] != self._summary["summary_id"]
                        or validated["path"] != f"artifacts/{self.run_id}/chart.png"
                        or (validated["width"], validated["height"]) != self._chart_dimensions()):
                    raise ValueError
            return validated
        except (ValidationError, ValueError, TypeError, KeyError, OSError, RuntimeError):
            raise Failure("invalid_tool_result", phase="tool") from None

    def finish(self) -> tuple[dict, dict | None]:
        if self._failed or self._summary is None or (self.output_format == "bar" and self._chart is None):
            raise Failure("incomplete_result", phase="completion")
        summary = self._validate_result("sum_by_channel", self._summary, {"metric": self._summary["metric"]})
        chart = None
        if self._chart is not None:
            if self.output_format != "bar":
                raise Failure("invalid_tool_result", phase="completion")
            chart = self._validate_result("render_bar_chart", self._chart, {})
        return deepcopy(summary), deepcopy(chart)
