"""Constrained composition, exact review, and the invocation-local controller.

Facts are complete synthetic sentences. Copy is chosen from a closed vocabulary.
A plan records those choices; a draft records the actual rendered text and spans.
Review checks the draft without changing it. Only the controller may select a
different plan, and every such transition must follow an observed violation.
"""

from dataclasses import dataclass, replace
from typing import Literal
import unicodedata

Channel = Literal["email", "documentation"]
ArtifactStatus = Literal["validated", "unapproved_no_repair", "unapproved_limit"]
COPY_SLOTS = ("title", "opening", "next_step")
CHANNELS: tuple[Channel, ...] = ("email", "documentation")
MAX_ATTEMPTS = 3


class InputError(ValueError):
    """A safe, bounded diagnostic for caller input; never includes raw input."""


class FixtureError(ValueError):
    """The packaged host-owned content cannot support a trusted snapshot."""


def normalized(text: str) -> str:
    """Casefold and collapse whitespace for literal brand matching, not semantics."""
    return " ".join(text.casefold().split())


def safe_text(value: object, *, max_length: int, whitespace: bool = False) -> bool:
    if type(value) is not str or not value.strip() or len(value.strip()) > max_length:
        return False
    return all(
        unicodedata.category(char) not in {"Cc", "Cs"}
        or (whitespace and char in "\t\n\r")
        for char in value
    )


@dataclass(frozen=True, slots=True)
class Brief:
    """Caller constraints, owned by one run and deeply immutable through tuples.

    Fact identities are checked against the frozen fixture at create_content.
    Word ceilings include headings. Approval is never an input a caller can grant.
    """

    audience: str
    required_fact_ids: tuple[str, ...]
    forbidden_phrases: tuple[str, ...]
    email_max_words: int
    docs_max_words: int

    def __post_init__(self) -> None:
        validate_brief(self)


def validate_brief(brief: Brief) -> None:
    """Validate again at the public API boundary, even for an existing Brief."""
    if type(brief) is not Brief:
        raise InputError("Expected an immutable Brief.")
    if type(brief.audience) is not str or brief.audience not in ("team_leads", "developers"):
        raise InputError("Unsupported audience.")
    ids = brief.required_fact_ids
    if type(ids) is not tuple or not 1 <= len(ids) <= 6:
        raise InputError("Required fact IDs must contain one through six identities.")
    if any(not safe_text(item, max_length=40) or item != item.strip() for item in ids):
        raise InputError("Invalid fact identity.")
    if len(set(ids)) != len(ids):
        raise InputError("Required fact identities must be unique.")
    phrases = brief.forbidden_phrases
    if type(phrases) is not tuple or len(phrases) > 16:
        raise InputError("Forbidden phrases must contain at most sixteen entries.")
    if any(not safe_text(item, max_length=80, whitespace=True) for item in phrases):
        raise InputError("Invalid forbidden phrase.")
    if len({normalized(item) for item in phrases}) != len(phrases):
        raise InputError("Forbidden phrases must be unique after normalization.")
    if any(type(limit) is not int or not 1 <= limit <= 500
           for limit in (brief.email_max_words, brief.docs_max_words)):
        raise InputError("Word ceilings must be integers from one through five hundred.")


@dataclass(frozen=True, slots=True)
class Source:
    id: str
    title: str


@dataclass(frozen=True, slots=True)
class Fact:
    """One indivisible, qualified sentence attributed to a synthetic source ID."""

    id: str
    source_id: str
    text: str


@dataclass(frozen=True, slots=True)
class Copy:
    kind: Channel
    variants: tuple[tuple[str, ...], ...]


@dataclass(frozen=True, slots=True)
class AudiencePriority:
    audience: str
    fact_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Snapshot:
    """Validated immutable fixture bytes represented as domain values.

    The SHA-256 identifies those bytes. It neither authenticates the file nor
    proves a fact true. The package, not a caller brief, owns this evidence.
    """

    product: str
    sources: tuple[Source, ...]
    facts: tuple[Fact, ...]
    copy: tuple[Copy, ...]
    priorities: tuple[AudiencePriority, ...]
    sha256: str

    def fact(self, fact_id: str) -> Fact:
        return next(fact for fact in self.facts if fact.id == fact_id)

    def choices(self, kind: Channel) -> tuple[tuple[str, ...], ...]:
        return next(copy.variants for copy in self.copy if copy.kind == kind)


@dataclass(frozen=True, slots=True)
class Plan:
    """Controller-owned choices; rejected alternatives prevent cycling in a run."""

    kind: Channel
    required: tuple[str, ...]
    optional: tuple[str, ...]
    copy_indices: tuple[int, ...] = (0, 0, 0)
    rejected: tuple[tuple[int, ...], ...] = ((), (), ())


@dataclass(frozen=True, slots=True)
class Block:
    """A proposed grammar block with Python character offsets, not byte offsets."""

    section: str
    kind: Literal["fact", "copy"]
    reference: str
    text: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class Evidence:
    """Bidirectional provenance from one complete fact block to its source."""

    fact_id: str
    source_id: str
    fixture_sha256: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class Draft:
    kind: Channel
    text: str
    blocks: tuple[Block, ...]
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True, slots=True)
class Violation:
    """Observed review feedback; block_index is null for a whole-document issue."""

    code: str
    message: str
    block_index: int | None = None
    value: str | None = None


@dataclass(frozen=True, slots=True)
class Change:
    category: Literal["brand", "length"]
    action: str
    target: str
    before: str
    after: str | None


@dataclass(frozen=True, slots=True)
class Attempt:
    number: int
    text: str
    word_count: int
    evidence: tuple[Evidence, ...]
    violations: tuple[Violation, ...]
    next_changes: tuple[Change, ...]


@dataclass(frozen=True, slots=True)
class ArtifactResult:
    kind: Channel
    status: ArtifactStatus
    attempts: tuple[Attempt, ...]
    validated_text: str | None


@dataclass(frozen=True, slots=True)
class RunResult:
    """Terminal reports preserve failures; machine validation never grants approval."""

    status: Literal["validated", "unapproved"]
    approval: Literal["not_granted"]
    fixture_sha256: str
    artifacts: tuple[ArtifactResult, ...]


def headings(kind: Channel) -> tuple[str, ...]:
    return (("Subject", "Introduction", "Details", "Next step") if kind == "email"
            else ("Title", "Summary", "Changes", "Next step"))


def initial_plan(brief: Brief, snapshot: Snapshot, kind: Channel) -> Plan:
    order = next(item.fact_ids for item in snapshot.priorities if item.audience == brief.audience)
    return Plan(kind, brief.required_fact_ids,
                tuple(fact_id for fact_id in order if fact_id not in brief.required_fact_ids))


def render(plan: Plan, snapshot: Snapshot) -> Draft:
    """Render only host-owned facts and copy; evidence spans cover complete sentences."""
    sections = headings(plan.kind)
    choices = snapshot.choices(plan.kind)
    selected = tuple(choices[slot][index] for slot, index in enumerate(plan.copy_indices))
    entries = [(sections[0], "copy", "title", selected[0]),
               (sections[1], "copy", "opening", selected[1])]
    entries.extend((sections[2], "fact", fact_id, snapshot.fact(fact_id).text)
                   for fact_id in plan.required + plan.optional)
    entries.append((sections[3], "copy", "next_step", selected[2]))
    parts: list[str] = []
    blocks: list[Block] = []
    evidence: list[Evidence] = []
    position = 0
    last_section = None
    for section, kind, reference, content in entries:
        prefix = ("\n\n" if parts else "") + section + "\n" if section != last_section else "\n"
        parts.extend((prefix, content))
        position += len(prefix)
        block = Block(section, kind, reference, content, position, position + len(content))
        blocks.append(block)
        if kind == "fact":
            fact = snapshot.fact(reference)
            evidence.append(Evidence(fact.id, fact.source_id, snapshot.sha256, block.start, block.end))
        position = block.end
        last_section = section
    return Draft(plan.kind, "".join(parts), tuple(blocks), tuple(evidence))


def _normalized_spans(text: str) -> tuple[str, tuple[tuple[int, int], ...]]:
    """Map casefold expansions and collapsed whitespace back to original offsets."""
    chars: list[str] = []
    spans: list[tuple[int, int]] = []
    for offset, char in enumerate(text):
        for folded in char.casefold():
            if folded.isspace():
                if chars and chars[-1] != " ":
                    chars.append(" ")
                    spans.append((offset, offset + 1))
                elif chars:
                    spans[-1] = (spans[-1][0], offset + 1)
            else:
                chars.append(folded)
                spans.append((offset, offset + 1))
    if chars and chars[-1] == " ":
        chars.pop()
        spans.pop()
    return "".join(chars), tuple(spans)


def review(draft: Draft, brief: Brief, snapshot: Snapshot) -> tuple[Violation, ...]:
    """Check actual text, complete grammar, and both directions of provenance.

    A real source ID alone proves nothing. Reconstructing the permitted structure
    prevents uncited extra prose, while exact spans prevent laundering altered
    assertions through plausible citations. This is syntactic fixture agreement.
    """
    violations: list[Violation] = []
    sections = headings(draft.kind)
    expected_layout = [(sections[0], "copy", "title"), (sections[1], "copy", "opening")]
    expected_layout.extend((sections[2], "fact", block.reference)
                           for block in draft.blocks if block.kind == "fact")
    expected_layout.append((sections[3], "copy", "next_step"))
    actual_layout = [(block.section, block.kind, block.reference) for block in draft.blocks]
    if actual_layout != expected_layout or not any(block.kind == "fact" for block in draft.blocks):
        violations.append(Violation("structure", "Sections or block order do not match the grammar."))

    reconstructed = ""
    last_section = None
    fact_ids: list[str] = []
    expected_evidence: list[Evidence] = []
    for index, block in enumerate(draft.blocks):
        prefix = (("\n\n" if reconstructed else "") + block.section + "\n"
                  if block.section != last_section else "\n")
        start = len(reconstructed) + len(prefix)
        reconstructed += prefix + block.text
        if (type(block.start) is not int or type(block.end) is not int
                or block.start != start or block.end != len(reconstructed)
                or draft.text[block.start:block.end] != block.text):
            violations.append(Violation("block_span", "Block offsets do not match actual text.", index))
        last_section = block.section
        if block.kind == "fact":
            fact_ids.append(block.reference)
            fact = next((item for item in snapshot.facts if item.id == block.reference), None)
            if fact is None:
                violations.append(Violation("unknown_fact", "Fact identity is not in the snapshot.", index))
            else:
                if block.text != fact.text:
                    violations.append(Violation("fact_text", "Fact sentence differs from the complete source.", index))
                expected_evidence.append(Evidence(fact.id, fact.source_id, snapshot.sha256, start,
                                                  start + len(fact.text)))
        elif (block.kind != "copy" or block.reference not in COPY_SLOTS
              or block.text not in snapshot.choices(draft.kind)[COPY_SLOTS.index(block.reference)]):
            violations.append(Violation("copy_vocabulary", "Copy is outside the permitted vocabulary.", index))
    if reconstructed != draft.text:
        violations.append(Violation("structure", "Actual text contains missing, altered, or extra structural content."))
    for fact_id in brief.required_fact_ids:
        if fact_ids.count(fact_id) != 1:
            violations.append(Violation("required_coverage", "A required fact must occur exactly once.", value=fact_id))
    if len(set(fact_ids)) != len(fact_ids):
        violations.append(Violation("duplicate_fact", "A fact may occur only once."))
    audience_order = next(item.fact_ids for item in snapshot.priorities if item.audience == brief.audience)
    expected_order = list(brief.required_fact_ids) + [
        fact_id for fact_id in audience_order
        if fact_id in fact_ids and fact_id not in brief.required_fact_ids
    ]
    # Derive order from host policy, even when a draft has valid facts and spans.
    if fact_ids != expected_order:
        violations.append(Violation("fact_order", "Facts do not follow required and audience priority order."))

    # Comparing multisets enforces both directions without trusting citation order.
    remaining = list(expected_evidence)
    for item in draft.evidence:
        valid = (type(item.start) is int and type(item.end) is int
                 and 0 <= item.start < item.end <= len(draft.text))
        if valid and item in remaining:
            fact = snapshot.fact(item.fact_id)
            valid = draft.text[item.start:item.end] == fact.text
        else:
            valid = False
        if valid:
            remaining.remove(item)
        else:
            violations.append(Violation("provenance", "Evidence is extra, duplicated, altered, or mismatched."))
    if remaining:
        violations.append(Violation("provenance", "A complete fact block is missing matching evidence."))

    if snapshot.product not in draft.text:
        violations.append(Violation("product_spelling", "Canonical product spelling is missing."))
    if "!" in draft.text:
        violations.append(Violation("exclamation", "Exclamation marks are forbidden."))
    folded, spans = _normalized_spans(draft.text)
    for phrase in brief.forbidden_phrases:
        needle = normalized(phrase)
        cursor = 0
        affected: set[int | None] = set()
        while (found := folded.find(needle, cursor)) >= 0:
            start, end = spans[found][0], spans[found + len(needle) - 1][1]
            indexes = {index for index, block in enumerate(draft.blocks)
                       if block.start < end and block.end > start}
            affected.update(indexes or {None})
            cursor = found + 1
        for index in sorted(affected, key=lambda item: -1 if item is None else item):
            violations.append(Violation("forbidden_phrase", "Forbidden wording is present.", index, needle))
    limit = brief.email_max_words if draft.kind == "email" else brief.docs_max_words
    if len(draft.text.split()) > limit:
        violations.append(Violation("word_limit", "The rendered word count exceeds the channel ceiling."))
    return tuple(violations)


def repair(plan: Plan, draft: Draft, violations: tuple[Violation, ...], snapshot: Snapshot
           ) -> tuple[Plan, tuple[Change, ...]] | None:
    """Select one repair category from feedback; never relax required constraints.

    Integrity failures stop this artifact because this renderer has no legitimate plan
    transition that introduces them. Brand replacements try untried alternatives
    in fixture order. Length drops the least important optional fact before copy.
    """
    brand_codes = {"product_spelling", "exclamation", "forbidden_phrase"}
    if any(item.code not in brand_codes | {"word_limit"} for item in violations):
        return None
    choices = snapshot.choices(plan.kind)
    indices = list(plan.copy_indices)
    rejected = list(plan.rejected)
    if any(item.code in brand_codes for item in violations):
        changes: list[Change] = []
        optional = list(plan.optional)
        affected = sorted({item.block_index for item in violations
                           if item.code in brand_codes and item.block_index is not None})
        for block_index in affected:
            block = draft.blocks[block_index]
            if block.kind == "fact":
                if block.reference in optional:
                    optional.remove(block.reference)
                    changes.append(Change("brand", "drop_optional_fact", block.reference, block.text, None))
                continue
            slot = COPY_SLOTS.index(block.reference)
            old = indices[slot]
            excluded = {*rejected[slot], old}
            candidate = next((i for i in range(len(choices[slot])) if i not in excluded), None)
            if candidate is not None:
                rejected[slot] = tuple(sorted(excluded))
                indices[slot] = candidate
                changes.append(Change("brand", "replace_copy", block.reference,
                                      choices[slot][old], choices[slot][candidate]))
        if changes:
            return replace(plan, optional=tuple(optional), copy_indices=tuple(indices),
                           rejected=tuple(rejected)), tuple(changes)
        return None
    if plan.optional:
        dropped = plan.optional[-1]
        return (replace(plan, optional=plan.optional[:-1]),
                (Change("length", "drop_optional_fact", dropped, snapshot.fact(dropped).text, None),))
    candidates = []
    for slot, variants in enumerate(choices):
        current = indices[slot]
        for index, variant in enumerate(variants):
            savings = len(variants[current].split()) - len(variant.split())
            if savings > 0 and index not in rejected[slot]:
                candidates.append((-savings, slot, index))
    if not candidates:
        return None
    _, slot, candidate = min(candidates)
    old = indices[slot]
    rejected[slot] = tuple(sorted({*rejected[slot], old}))
    indices[slot] = candidate
    return (replace(plan, copy_indices=tuple(indices), rejected=tuple(rejected)),
            (Change("length", "shorten_copy", COPY_SLOTS[slot], choices[slot][old], choices[slot][candidate]),))


def _compose(brief: Brief, snapshot: Snapshot, kind: Channel) -> ArtifactResult:
    plan = initial_plan(brief, snapshot, kind)
    attempts: list[Attempt] = []
    for number in range(1, MAX_ATTEMPTS + 1):
        draft = render(plan, snapshot)
        violations = review(draft, brief, snapshot)
        changes: tuple[Change, ...] = ()
        next_plan = None
        if not violations:
            status = "validated"
        elif number == MAX_ATTEMPTS:
            status = "unapproved_limit"
        else:
            transition = repair(plan, draft, violations, snapshot)
            if transition is not None:
                proposed, changes = transition
                if (proposed.required, proposed.optional, proposed.copy_indices) != (
                        plan.required, plan.optional, plan.copy_indices):
                    next_plan = proposed
                else:
                    changes = ()
            status = "unapproved_no_repair"
        attempts.append(Attempt(number, draft.text, len(draft.text.split()), draft.evidence,
                                violations, changes))
        if next_plan is None:
            return ArtifactResult(kind, status, tuple(attempts), draft.text if not violations else None)
        plan = next_plan
    raise AssertionError("The bounded controller must return a terminal report.")


def create_content(brief: Brief) -> RunResult:
    """Validate one brief, freeze one fixture snapshot, and finish both artifacts.

    The only read is the fixed packaged content fixture. No model, network,
    filesystem write, subprocess, or cross-invocation mutable state is involved.
    """
    from .boundary import load_snapshot

    validate_brief(brief)
    snapshot = load_snapshot()
    if any(fact_id not in {fact.id for fact in snapshot.facts} for fact_id in brief.required_fact_ids):
        raise InputError("Required fact identity is not present in the fixture.")
    artifacts = tuple(_compose(brief, snapshot, kind) for kind in CHANNELS)
    status = "validated" if all(item.status == "validated" for item in artifacts) else "unapproved"
    return RunResult(status, "not_granted", snapshot.sha256, artifacts)
