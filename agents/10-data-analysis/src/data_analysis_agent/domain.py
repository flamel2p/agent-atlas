"""Immutable vocabulary shared by analysis, presentation, and the CLI.

One observation is one product/date CSV record. A record ordinal counts records
following the header, not physical lines. Provenance connects results to those
ordinals and to the SHA-256 of the exact input bytes; it does not certify that
source data is true or complete. All objects live for one request.

Plans are a closed union: callers cannot supply executable code, arbitrary
aggregations, or chart instructions. Outcome variants distinguish a computed
report from clarification, no observed data, and boundary failures.
"""

from dataclasses import dataclass, field, fields, is_dataclass
from datetime import date
from decimal import Decimal
from typing import Literal


type Metric = Literal["units", "revenue_rm"]
MAX_BYTES = 256 * 1024
MAX_RECORDS = 1000
BUILTIN_SOURCE = "builtin:synthetic-q3-2026"


@dataclass(frozen=True, slots=True)
class ActivityRecord:
    ordinal: int
    date: date
    product: str
    units: int | None
    revenue_rm: Decimal | None


@dataclass(frozen=True, slots=True)
class Dataset:
    records: tuple[ActivityRecord, ...]
    sha256: str
    source_label: str
    source_kind: Literal["built_in_synthetic", "user_supplied"]


@dataclass(frozen=True, slots=True)
class RankPlan:
    metric: Metric
    start: date
    end: date
    limit: int
    operation: Literal["rank"] = field(default="rank", init=False)


@dataclass(frozen=True, slots=True)
class MonthlyPlan:
    metric: Metric
    start: date
    end: date
    operation: Literal["monthly"] = field(default="monthly", init=False)


@dataclass(frozen=True, slots=True)
class DescribePlan:
    metric: Metric
    start: date
    end: date
    operation: Literal["describe"] = field(default="describe", init=False)


type AnalysisPlan = RankPlan | MonthlyPlan | DescribePlan


@dataclass(frozen=True, slots=True)
class Quality:
    """Counts partition the validated dataset and disclose selected-metric gaps.

    Used + missing equals in-period. Outside-period + in-period equals total.
    These counts describe supplied records, not a declared product/date grid.
    """

    total_records: int
    in_period_records: int
    outside_period_records: int
    used_records: int
    missing_metric_records: int
    missing_record_ordinals: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class Provenance:
    dataset_sha256: str
    source_label: str
    source_kind: Literal["built_in_synthetic", "user_supplied"]
    observation_unit: str = "one supplied product/date record"


@dataclass(frozen=True, slots=True)
class ProductTotal:
    product: str
    total: Decimal
    contributing_record_ordinals: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class Ranking:
    products: tuple[ProductTotal, ...]
    observed_product_count: int


@dataclass(frozen=True, slots=True)
class MonthTotal:
    month: str
    interval_start: date
    interval_end: date
    partial_calendar_month: bool
    total: Decimal | None
    used_records: int
    missing_metric_records: int
    missing_record_ordinals: tuple[int, ...]
    contributing_record_ordinals: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class MonthlyTrend:
    months: tuple[MonthTotal, ...]


@dataclass(frozen=True, slots=True)
class Description:
    count: int
    sum: Decimal
    minimum: Decimal
    maximum: Decimal
    mean: Decimal
    median: Decimal
    sample_standard_deviation: Decimal | None
    standard_deviation_note: str
    contributing_record_ordinals: tuple[int, ...]


type Calculation = Ranking | MonthlyTrend | Description


@dataclass(frozen=True, slots=True)
class ChartDatum:
    label: str
    value: Decimal | int | None


@dataclass(frozen=True, slots=True)
class Chart:
    """Host-selected projection of calculated values; null never means zero."""

    kind: Literal["bar", "line", "table"]
    title: str
    x_label: str
    y_label: str
    data: tuple[ChartDatum, ...]
    null_label: str = "No observed value"


@dataclass(frozen=True, slots=True)
class Report:
    plan: AnalysisPlan
    metric: Metric
    unit: Literal["units", "RM"]
    calculation: Calculation
    quality: Quality
    provenance: Provenance
    chart: Chart
    interpretation: tuple[str, ...]
    assumptions: tuple[str, ...]
    backend: str = "deterministic-python-standard-library"


@dataclass(frozen=True, slots=True)
class Completed:
    report: Report
    status: Literal["completed"] = field(default="completed", init=False)


@dataclass(frozen=True, slots=True)
class NeedsClarification:
    message: str
    supported_forms: tuple[str, ...] = (
        "top N products by METRIC from YYYY-MM-DD to YYYY-MM-DD",
        "monthly METRIC from YYYY-MM-DD to YYYY-MM-DD",
        "describe METRIC from YYYY-MM-DD to YYYY-MM-DD",
    )
    status: Literal["needs_clarification"] = field(default="needs_clarification", init=False)


@dataclass(frozen=True, slots=True)
class NoData:
    plan: AnalysisPlan
    quality: Quality
    provenance: Provenance
    message: str
    status: Literal["no_data"] = field(default="no_data", init=False)


@dataclass(frozen=True, slots=True)
class Failure:
    status: Literal["invalid_dataset", "input_error", "output_error", "cancelled"]
    message: str


type Outcome = Completed | NeedsClarification | NoData | Failure


class InvalidDataset(ValueError):
    """An expected input rejection whose message never embeds CSV content."""


def to_wire(value: object) -> object:
    """Convert the domain to JSON primitives without passing Decimal through float."""
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: to_wire(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, (tuple, list)):
        return [to_wire(item) for item in value]
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("Nonfinite calculation cannot be serialized")
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise TypeError(f"Unsupported report type: {type(value).__name__}")
