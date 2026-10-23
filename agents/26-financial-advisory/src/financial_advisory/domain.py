"""Immutable run-local domain and deterministic host policy.

The boundary parser constructs Request values. Analysis uses daily constant-weight
rebalancing, with descriptive fractional returns rather than forecasts. Data
readiness precedes calculations; host code alone creates one revision and decides
whether the result contains a simulated allocation. Nothing executes an order.
"""

from dataclasses import asdict, dataclass
from datetime import date
from enum import StrEnum
import math
from types import MappingProxyType


class RiskBand(StrEnum):
    CAUTIOUS = "cautious"
    MODERATE = "moderate"
    EXPLORATORY = "exploratory"


@dataclass(frozen=True)
class Observation:
    day: date
    price: float


@dataclass(frozen=True)
class PriceSeries:
    """One fictional asset's consecutive calendar-day prices in synthetic units."""

    asset: str
    observations: tuple[Observation, ...]


@dataclass(frozen=True)
class SyntheticProfile:
    """An invented identifier and selection from the host's educational policy table."""

    id: str
    risk_band: RiskBand


@dataclass(frozen=True)
class AllocationProposal:
    """Weights aligned with Request.assets, never an order or account mutation."""

    weights: tuple[float, ...]


@dataclass(frozen=True)
class Request:
    """Validated per-run inputs; series may be incomplete and require review."""

    as_of: date
    profile: SyntheticProfile
    assets: tuple[str, ...]
    series: tuple[PriceSeries, ...]
    proposal: AllocationProposal


@dataclass(frozen=True)
class Policy:
    concentration: float
    volatility: float
    drawdown: float


POLICIES = MappingProxyType({
    RiskBand.CAUTIOUS: Policy(0.5, 0.03, 0.10),
    RiskBand.MODERATE: Policy(0.6, 0.08, 0.25),
    RiskBand.EXPLORATORY: Policy(0.8, 0.20, 0.50),
})


@dataclass(frozen=True)
class PolicyFinding:
    """Host-authored reason that data or an allocation cannot pass simulation."""

    code: str
    asset: str | None = None


@dataclass(frozen=True)
class RiskReport:
    """Fractional, nonannualized statistics for the supplied observation window.

    Sample volatility uses n-1 return observations. Drawdown includes initial
    wealth 1 as a peak. Neither quantity estimates future loss or suitability.
    """

    asset_returns: dict[str, tuple[float, ...]]
    portfolio_returns: tuple[float, ...]
    terminal_wealth: float
    volatility: float
    drawdown: float
    concentration: float
    period_count: int
    start_date: str
    end_date: str
    freshness_days: dict[str, int]
    units: str = "fraction_per_calendar_day; wealth_relative_to_1"


@dataclass(frozen=True)
class Evaluation:
    weights: dict[str, float]
    metrics: RiskReport
    findings: tuple[PolicyFinding, ...]


@dataclass(frozen=True)
class AdvisoryResult:
    """Terminal evidence. Review never contains a released simulated allocation."""

    status: str
    as_of: str
    profile_id: str
    risk_band: str
    policy: Policy
    evaluations: tuple[Evaluation, ...]
    revision_count: int
    findings: tuple[PolicyFinding, ...]
    simulated_allocation: dict[str, float] | None
    trace: tuple[str, ...]
    mode: str = "fixture"

    def to_dict(self) -> dict:
        result = asdict(self)
        result["authority"] = {
            "orders_authorized": False,
            "professional_approval": False,
        }
        return result


def data_findings(request: Request) -> tuple[PolicyFinding, ...]:
    """Check every required asset, even at zero weight, before computing risk."""
    available = {series.asset: series for series in request.series}
    findings = []
    grid = None
    for asset in request.assets:
        series = available.get(asset)
        if series is None or len(series.observations) < 3:
            findings.append(PolicyFinding("incomplete_history", asset))
            continue
        days = tuple(item.day for item in series.observations)
        if grid is None:
            grid = days
        elif days != grid:
            findings.append(PolicyFinding("incompatible_date_grid", asset))
        if (request.as_of - days[-1]).days > 3:
            findings.append(PolicyFinding("stale_history", asset))
    return tuple(findings)


def calculate(request: Request, proposal: AllocationProposal) -> RiskReport:
    """Calculate only after data readiness, with bounded ratios from the parser."""
    available = {series.asset: series for series in request.series}
    asset_returns = {}
    freshness = {}
    for asset in request.assets:
        observations = available[asset].observations
        asset_returns[asset] = tuple(
            later.price / earlier.price - 1.0
            for earlier, later in zip(observations, observations[1:])
        )
        freshness[asset] = (request.as_of - observations[-1].day).days
    periods = len(asset_returns[request.assets[0]])
    returns = tuple(
        math.fsum(weight * asset_returns[asset][period]
                  for asset, weight in zip(request.assets, proposal.weights))
        for period in range(periods)
    )
    mean = math.fsum(returns) / periods
    volatility = math.sqrt(math.fsum((value - mean) ** 2 for value in returns)
                           / (periods - 1))
    wealth, peak, drawdown = 1.0, 1.0, 0.0
    for value in returns:
        wealth *= 1.0 + value
        peak = max(peak, wealth)
        drawdown = max(drawdown, 1.0 - wealth / peak)
    observations = available[request.assets[0]].observations
    return RiskReport(asset_returns, returns, wealth, volatility, drawdown,
                      max(proposal.weights), periods,
                      observations[0].day.isoformat(), observations[-1].day.isoformat(),
                      freshness)


def evaluate(request: Request, proposal: AllocationProposal, policy: Policy) -> Evaluation:
    metrics = calculate(request, proposal)
    findings = tuple(PolicyFinding(f"{name}_exceeded")
                     for name in ("concentration", "volatility", "drawdown")
                     if getattr(metrics, name) > getattr(policy, name))
    return Evaluation(dict(zip(request.assets, proposal.weights)), metrics, findings)


def run(request: Request) -> AdvisoryResult:
    """Run the finite host state machine: readiness, initial check, at most one revision."""
    policy = POLICIES[request.profile.risk_band]
    trace = ["input_validated", "data_checked"]
    findings = data_findings(request)
    evaluations = []
    revisions = 0
    allocation = None
    if not findings:
        first = evaluate(request, request.proposal, policy)
        evaluations.append(first)
        trace.append("initial_evaluated")
        if first.findings:
            # Only the host may revise. Equal weights cannot repair stale/missing data.
            revised = AllocationProposal((1.0 / len(request.assets),) * len(request.assets))
            revisions = 1
            trace.append("host_equal_weight_revision")
            evaluations.append(evaluate(request, revised, policy))
            trace.append("revision_fully_rechecked")
        findings = evaluations[-1].findings
        if not findings:
            allocation = evaluations[-1].weights
    status = "review_required" if findings else "completed_simulation"
    trace.append(status)
    return AdvisoryResult(status, request.as_of.isoformat(), request.profile.id,
                          request.profile.risk_band.value, policy, tuple(evaluations),
                          revisions, findings, allocation, tuple(trace))
