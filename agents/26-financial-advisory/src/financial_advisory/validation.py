"""Strict transport and schema boundary for fictional portfolio input.

Reject unsupported JSON before constructing immutable domain values. Missing price
coverage is a review condition, while malformed records are invalid input. Decimal
numbers enforce an exact allocation sum; bounded floats then keep analysis finite.
"""

from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
import json
import re

from .domain import (AllocationProposal, Observation, PriceSeries, Request,
                     RiskBand, SyntheticProfile)

MAX_BYTES = 65536
MAX_DEPTH = 12
ASSET = re.compile(r"SYN_[A-Z]{1,12}\Z", re.ASCII)
PROFILE = re.compile(r"invented_[a-z]{1,20}\Z", re.ASCII)
DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z", re.ASCII)


class InvalidInput(ValueError):
    """A host-authored, bounded error safe to include without echoing input data."""


def _number(token: str) -> Decimal:
    if len(token) > 32:
        raise InvalidInput("numeric token exceeds 32 characters")
    try:
        value = Decimal(token)
    except InvalidOperation:
        raise InvalidInput("number has unsupported exponent") from None
    if not value.is_finite() or not -12 <= value.as_tuple().exponent <= 6:
        raise InvalidInput("number has unsupported precision or exponent")
    return value


def _constant(token: str):
    raise InvalidInput("nonfinite JSON number")


def _pairs(items: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in items:
        if key in result:
            raise InvalidInput("duplicate object key")
        result[key] = value
    return result


def _depth(text: str) -> None:
    # Scan before json.loads: even tiny deeply nested inputs must not hit recursion.
    depth, quoted, escaped = 0, False, False
    for character in text:
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
        elif character == '"':
            quoted = True
        elif character in "[{":
            depth += 1
            if depth > MAX_DEPTH:
                raise InvalidInput("JSON nesting exceeds 12 levels")
        elif character in "]}":
            depth -= 1


def _object(value: object, keys: set[str], where: str) -> dict:
    if type(value) is not dict or set(value) != keys:
        raise InvalidInput(f"{where} has missing or unknown fields")
    return value


def _array(value: object, minimum: int, maximum: int, where: str) -> list:
    if type(value) is not list or not minimum <= len(value) <= maximum:
        raise InvalidInput(f"{where} has unsupported type or length")
    return value


def _identifier(value: object, pattern: re.Pattern, where: str) -> str:
    if type(value) is not str or not pattern.fullmatch(value):
        raise InvalidInput(f"{where} has unsupported identifier")
    return value


def _date(value: object) -> date:
    if type(value) is not str or not DATE.fullmatch(value):
        raise InvalidInput("date must be YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise InvalidInput("invalid calendar date") from None


def _bounded(value: object, lower: Decimal, upper: Decimal, where: str) -> Decimal:
    # bool is a Python number subclass but has no authority as a price or weight.
    if type(value) is not Decimal or not value.is_finite() or not lower <= value <= upper:
        raise InvalidInput(f"{where} is outside numeric bounds")
    return value


def parse(raw: bytes) -> Request:
    """Parse at most 64 KiB and validate exact schema; never read a user file path."""
    if len(raw) > MAX_BYTES:
        raise InvalidInput("input exceeds 65536 bytes")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise InvalidInput("input must be UTF-8") from None
    _depth(text)
    try:
        data = json.loads(text, parse_int=_number, parse_float=_number,
                          parse_constant=_constant, object_pairs_hook=_pairs)
    except (json.JSONDecodeError, RecursionError):
        raise InvalidInput("malformed JSON") from None
    root = _object(data, {"fictional", "as_of", "profile", "required_assets", "series", "proposal"}, "root")
    if root["fictional"] is not True:
        raise InvalidInput("fictional must be true")
    as_of = _date(root["as_of"])
    profile = _object(root["profile"], {"id", "risk_band"}, "profile")
    profile_id = _identifier(profile["id"], PROFILE, "profile")
    if type(profile["risk_band"]) is not str:
        raise InvalidInput("unsupported fictional risk band")
    try:
        band = RiskBand(profile["risk_band"])
    except ValueError:
        raise InvalidInput("unsupported fictional risk band") from None
    assets = tuple(_identifier(item, ASSET, "asset")
                   for item in _array(root["required_assets"], 2, 8, "required_assets"))
    if len(set(assets)) != len(assets):
        raise InvalidInput("duplicate required asset")
    series_values, seen = [], set()
    for item in _array(root["series"], 0, 8, "series"):
        record = _object(item, {"asset", "unit", "observations"}, "series record")
        asset = _identifier(record["asset"], ASSET, "asset")
        if asset not in assets or asset in seen:
            raise InvalidInput("unknown or duplicate series asset")
        seen.add(asset)
        if record["unit"] != "synthetic_price_units":
            raise InvalidInput("unsupported price unit")
        observations = []
        prior_price = None
        for item in _array(record["observations"], 0, 64, "observations"):
            point = _object(item, {"date", "price"}, "observation")
            day = _date(point["date"])
            price = _bounded(point["price"], Decimal("0.000001"), Decimal("1000000"), "price")
            if day > as_of:
                raise InvalidInput("observation is after as_of")
            if observations:
                if (day - observations[-1].day).days != 1:
                    raise InvalidInput("observations must be consecutive increasing calendar days")
                # Compare products exactly rather than round a decimal division.
                if not prior_price / 2 <= price <= prior_price * 2:
                    raise InvalidInput("adjacent price ratio is outside [0.5, 2]")
            observations.append(Observation(day, float(price)))
            prior_price = price
        series_values.append(PriceSeries(asset, tuple(observations)))
    proposal = _object(root["proposal"], {"weights"}, "proposal")
    weights = _object(proposal["weights"], set(assets), "weights")
    decimal_weights = tuple(_bounded(weights[asset], Decimal(0), Decimal(1), "weight")
                            for asset in assets)
    # At most 8 weights with 12 fractional digits; precision 40 preserves the sum.
    with localcontext() as context:
        context.prec = 40
        if sum(decimal_weights) != Decimal(1):
            raise InvalidInput("weights must sum exactly to one")
    return Request(as_of, SyntheticProfile(profile_id, band), assets,
                   tuple(series_values), AllocationProposal(tuple(map(float, decimal_weights))))
