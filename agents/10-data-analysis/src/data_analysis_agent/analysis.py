"""Turn one constrained question and complete CSV into an auditable result.

``analyze`` is the deep request boundary: grammar, schema, numeric limits,
missingness, and calculation policy stay here. The CLI has no authority to
invent a plan. Nothing in a question or a cell is executable.

All records are validated before filtering. Selected-metric blanks are excluded
with ordinals, while observed zeros participate. Calculations use an independent
Decimal context with precision 40. This domain needs at most 15 significant
digits for a sum, so summation is exact; displayed summaries round half-even to
six fractional places. The report and chart share those computed values.
"""

import calendar
import csv
import hashlib
import io
import re
import statistics
from datetime import date, timedelta
from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext

from .domain import (
    BUILTIN_SOURCE,
    MAX_BYTES,
    MAX_RECORDS,
    ActivityRecord,
    AnalysisPlan,
    Chart,
    ChartDatum,
    Completed,
    Dataset,
    Description,
    DescribePlan,
    Failure,
    InvalidDataset,
    Metric,
    MonthTotal,
    MonthlyPlan,
    MonthlyTrend,
    NeedsClarification,
    NoData,
    Outcome,
    ProductTotal,
    Provenance,
    Quality,
    Ranking,
    RankPlan,
    Report,
)

_DATE = r"[0-9]{4}-[0-9]{2}-[0-9]{2}"
_QUESTION = re.compile(
    rf"(?:(?:top (?P<limit>[0-9]+) products by)|(?P<operation>monthly|describe)) "
    rf"(?P<metric>units|revenue_rm) from (?P<start>{_DATE}) to (?P<end>{_DATE})",
    re.IGNORECASE | re.ASCII,
)
_BUILTIN_SHA256 = "0c0a20a60d2fcb23ca876ff2bb6495c6f20dc38f8f6a09c781021d8553cb6aa9"
_SIX_PLACES = Decimal("0.000001")
_ASSUMPTIONS = (
    "Results describe observed product/date records; absent rows do not imply zero activity or complete coverage.",
    "Only blank selected-metric cells are excluded; no imputation, normalization, or outlier removal is applied.",
    "Dates are inclusive. Revenue is denominated in RM; the dataset does not define tax or accounting treatment.",
    "Sums are exact. Mean, median, and sample standard deviation round to six decimal places using ROUND_HALF_EVEN.",
    "Descriptive results provide no statistical confidence, causal evidence, forecast, or growth-rate inference.",
)


def _date(token: str) -> date:
    if not re.fullmatch(_DATE, token, re.ASCII):
        raise ValueError("Expected an ISO date")
    parsed = date.fromisoformat(token)
    if not 2000 <= parsed.year <= 2100:
        raise ValueError("Date year is outside 2000-2100")
    return parsed


def parse_question(question: str) -> AnalysisPlan | NeedsClarification:
    """Validate intent before I/O; the public analysis boundary repeats this gate.

    Full matching is deliberate. A recognized prefix does not authorize trailing
    instructions, extra filters, paths, or code-like clauses.
    """
    if not isinstance(question, str) or not 1 <= len(question) <= 256:
        return NeedsClarification("Supply a question containing 1-256 characters.")
    match = _QUESTION.fullmatch(question.strip())
    if match is None:
        return NeedsClarification("Use one supported form with metric units or revenue_rm.")
    try:
        start, end = _date(match["start"]), _date(match["end"])
    except ValueError:
        return NeedsClarification("Use valid ISO calendar dates in years 2000-2100.")
    if start > end or (end - start).days + 1 > 366:
        return NeedsClarification("Dates must be ordered and cover at most 366 days inclusive.")
    metric: Metric = match["metric"].lower()
    if match["limit"] is not None:
        limit = int(match["limit"])
        if not 1 <= limit <= 10:
            return NeedsClarification("The product limit must be an ASCII integer from 1 to 10.")
        return RankPlan(metric, start, end, limit)
    if match["operation"].lower() == "monthly":
        return MonthlyPlan(metric, start, end)
    return DescribePlan(metric, start, end)


def _numeric(token: str, metric: Metric, ordinal: int) -> int | Decimal | None:
    if token == "":
        return None
    pattern = r"[0-9]+" if metric == "units" else r"[0-9]+(?:\.[0-9]{1,2})?"
    if len(token) > 13 or re.fullmatch(pattern, token, re.ASCII) is None:
        raise InvalidDataset(f"Record {ordinal} has an invalid {metric} token.")
    value = int(token) if metric == "units" else Decimal(token)
    if value > 1_000_000_000:
        raise InvalidDataset(f"Record {ordinal} exceeds the {metric} maximum.")
    return value


def _dataset(dataset_bytes: bytes, source_label: str) -> Dataset:
    if not isinstance(dataset_bytes, bytes) or len(dataset_bytes) > MAX_BYTES:
        raise InvalidDataset("Dataset must be UTF-8 bytes no larger than 256 KiB.")
    try:
        text = dataset_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise InvalidDataset("Dataset must be valid UTF-8.") from None
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    records: list[ActivityRecord] = []
    seen: set[tuple[date, str]] = set()
    products: set[str] = set()
    try:
        if next(reader, None) != ["date", "product", "units", "revenue_rm"]:
            raise InvalidDataset("CSV requires exactly the ordered headers date,product,units,revenue_rm.")
        for ordinal, row in enumerate(reader, 1):
            if ordinal > MAX_RECORDS:
                raise InvalidDataset("Dataset exceeds 1000 records.")
            if len(row) != 4:
                raise InvalidDataset(f"Record {ordinal} must have exactly four fields.")
            day_token, product, units, revenue = row
            try:
                day = _date(day_token)
            except ValueError:
                raise InvalidDataset(f"Record {ordinal} has an invalid date.") from None
            if re.fullmatch(r"[ -~]{1,40}", product, re.ASCII) is None or product != product.strip():
                raise InvalidDataset(f"Record {ordinal} has an invalid product label.")
            key = day, product
            if key in seen:
                raise InvalidDataset(f"Record {ordinal} repeats a date/product pair.")
            seen.add(key)
            products.add(product)
            if len(products) > 20:
                raise InvalidDataset("Dataset exceeds 20 distinct products.")
            records.append(ActivityRecord(ordinal, day, product, _numeric(units, "units", ordinal), _numeric(revenue, "revenue_rm", ordinal)))
    except csv.Error:
        raise InvalidDataset("Dataset has malformed CSV syntax or an oversized field.") from None
    if not records:
        raise InvalidDataset("Dataset must contain at least one record.")
    digest = hashlib.sha256(dataset_bytes).hexdigest()
    # A label alone cannot make arbitrary API bytes a claimed synthetic fixture.
    kind = "built_in_synthetic" if source_label == BUILTIN_SOURCE and digest == _BUILTIN_SHA256 else "user_supplied"
    return Dataset(tuple(records), digest, source_label, kind)


def _value(record: ActivityRecord, metric: Metric) -> Decimal | None:
    number = record.units if metric == "units" else record.revenue_rm
    return Decimal(number) if number is not None else None


def _total(values: list[Decimal], metric: Metric) -> Decimal:
    return sum(values, Decimal(0)).quantize(Decimal("1") if metric == "units" else Decimal("0.01"))


def _calculate(plan: AnalysisPlan, rows: tuple[ActivityRecord, ...], quality: Quality, provenance: Provenance) -> Report:
    """Execute one host-approved operation inside the caller's Decimal context."""
    observed = [(row, value) for row in rows if (value := _value(row, plan.metric)) is not None]
    unit = "RM" if plan.metric == "revenue_rm" else "units"
    title = f"{plan.operation.capitalize()} {plan.metric}: {plan.start} to {plan.end}"
    interpretations = [f"Used {quality.used_records} observed records in the inclusive interval; excluded {quality.missing_metric_records} blank selected-metric records."]
    if quality.missing_metric_records:
        interpretations.append("Incomplete observed subtotals: in-period selected-metric values are missing. Results exclude these records and cannot establish complete product totals or rankings.")
    match plan:
        case RankPlan():
            groups: dict[str, list[tuple[ActivityRecord, Decimal]]] = {}
            for row, value in observed:
                groups.setdefault(row.product, []).append((row, value))
            products = tuple(sorted(
                (ProductTotal(label, _total([value for _, value in group], plan.metric), tuple(row.ordinal for row, _ in group)) for label, group in groups.items()),
                key=lambda item: (-item.total, item.product),
            )[:plan.limit])
            calculation = Ranking(products, len(groups))
            chart = Chart("bar", title, "Product", unit, tuple(ChartDatum(item.product, item.total) for item in products))
            interpretations.append(f"{products[0].product} has the largest observed subtotal, {products[0].total} {unit}; ties are ordered by exact product label.")
        case MonthlyPlan():
            buckets: list[MonthTotal] = []
            first = plan.start.replace(day=1)
            while first <= plan.end:
                last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
                clipped_start, clipped_end = max(first, plan.start), min(last, plan.end)
                month_rows = [row for row in rows if clipped_start <= row.date <= clipped_end]
                month_observed = [(row, value) for row in month_rows if (value := _value(row, plan.metric)) is not None]
                missing = tuple(row.ordinal for row in month_rows if _value(row, plan.metric) is None)
                total = _total([value for _, value in month_observed], plan.metric) if month_observed else None
                buckets.append(MonthTotal(first.strftime("%Y-%m"), clipped_start, clipped_end, clipped_start != first or clipped_end != last, total, len(month_observed), len(missing), missing, tuple(row.ordinal for row, _ in month_observed)))
                first = last + timedelta(days=1)
            calculation = MonthlyTrend(tuple(buckets))
            chart_kind = "line" if sum(item.total is not None for item in buckets) >= 2 else "table"
            chart = Chart(chart_kind, title, "Month", unit, tuple(ChartDatum(item.month, item.total) for item in buckets))
            interpretations.append("Monthly values are observed subtotals. Null months have no observed selected value; line gaps are not interpolated. Partial months use only the clipped interval.")
        case DescribePlan():
            values = [value for _, value in observed]
            count = len(values)
            total = _total(values, plan.metric)
            deviation = statistics.stdev(values).quantize(_SIX_PLACES) if count >= 2 else None
            note = "Sample standard deviation uses denominator n-1." if count >= 2 else "Sample standard deviation is undefined for one observation because n-1 is zero."
            calculation = Description(count, total, _total([min(values)], plan.metric), _total([max(values)], plan.metric), statistics.mean(values).quantize(_SIX_PLACES), statistics.median(values).quantize(_SIX_PLACES), deviation, note, tuple(row.ordinal for row, _ in observed))
            chart = Chart("table", title, "Statistic", f"{unit}, except count", tuple(ChartDatum(label, getattr(calculation, label)) for label in ("count", "sum", "minimum", "maximum", "mean", "median", "sample_standard_deviation")), "Undefined for one observation")
            interpretations.extend(("Statistics summarize individual product/date records, not transactions, product totals, or monthly totals.", note))
    return Report(plan, plan.metric, unit, calculation, quality, provenance, chart, tuple(interpretations), _ASSUMPTIONS)


def analyze(question: str, dataset_bytes: bytes, source_label: str) -> Outcome:
    """Analyze once without I/O, mutation, retries, or hidden conversational state.

    ``source_label`` is a caller-provided identifier, never a path to open.
    Only the bundled label plus its exact byte hash identifies synthetic data.
    User CSV remains user-supplied even when it copies the fixture's contents.
    Expected question/dataset rejections are terminal typed outcomes. Unexpected
    programming errors propagate, so they cannot be mislabeled as completion.
    """
    plan = parse_question(question)
    if isinstance(plan, NeedsClarification):
        return plan
    if not isinstance(source_label, str):
        return Failure("input_error", "The source label must be text.")
    try:
        dataset = _dataset(dataset_bytes, source_label)
    except InvalidDataset as error:
        return Failure("invalid_dataset", str(error))
    rows = tuple(row for row in dataset.records if plan.start <= row.date <= plan.end)
    missing = tuple(row.ordinal for row in rows if _value(row, plan.metric) is None)
    quality = Quality(len(dataset.records), len(rows), len(dataset.records) - len(rows), len(rows) - len(missing), len(missing), missing)
    provenance = Provenance(dataset.sha256, dataset.source_label, dataset.source_kind)
    if not quality.used_records:
        return NoData(plan, quality, provenance, "No observed selected-metric values in the requested interval; no chart or artifacts are produced.")
    # Construct a new context, not an inherited caller context with changed traps.
    with localcontext(Context(prec=40, rounding=ROUND_HALF_EVEN)):
        return Completed(_calculate(plan, rows, quality, provenance))
