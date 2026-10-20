"""Policy acceptance checks use public extraction, including retained evidence."""

from copy import deepcopy
from dataclasses import FrozenInstanceError
from decimal import Decimal
import random

import pytest

from document_intelligence import Example, InvoiceError, extract_invoice
from conftest import add_page, set_total


def test_clean_record_and_reconstructible_evidence():
    report = extract_invoice(Example("clean"))
    assert report.record == {"invoice_number": "INV-2026-0042", "invoice_date": "2026-10-20", "total_myr": "1234.50"}
    assert report.status == "extracted"
    assert report.total_myr.value == Decimal("1234.50")
    assert report.document.source_mode == "fixture"
    assert report.document.engine is None
    page = report.document.pages[0]
    ledger = {token.id: token for token in page.tokens}
    candidate = report.total_myr.candidates[0]
    assert candidate.raw_value == "MYR 1,234.50"
    assert candidate.evidence.page == 1
    assert " ".join(ledger[i].text for i in candidate.evidence.cue_token_ids) == "Grand Total:"
    assert " ".join(ledger[i].text for i in candidate.evidence.value_token_ids) == candidate.raw_value
    assert candidate.evidence.value_bbox.left == ledger[candidate.evidence.value_token_ids[0]].bbox.left
    assert candidate.evidence.value_bbox.right == ledger[candidate.evidence.value_token_ids[-1]].bbox.right
    assert candidate.min_ocr_score == 98
    with pytest.raises(FrozenInstanceError):
        page.width = 7


def test_identical_duplicate_values_retain_all_evidence(clean, extract):
    add_page(clean, value="RM 1234.50")
    report = extract(clean)
    assert report.status == "extracted"
    assert [c.evidence.page for c in report.total_myr.candidates] == [1, 2]
    assert [c.raw_value for c in report.total_myr.candidates] == ["MYR 1,234.50", "RM 1234.50"]


def test_conflicting_weak_candidate_is_not_discarded(clean, extract):
    add_page(clean, value="RM 1250.00", score=20)
    report = extract(clean)
    assert report.record is None
    assert report.total_myr.value is None
    assert set(report.total_myr.reasons) == {"conflicting_values", "low_ocr_score"}
    assert [c.normalized_value for c in report.total_myr.candidates] == [Decimal("1234.50"), Decimal("1250.00")]
    assert report.invoice_number.status == report.invoice_date.status == "accepted"


@pytest.mark.parametrize("index,score,reason", [(6, 79, "low_ocr_score"), (9, None, "missing_ocr_score"), (6, None, "missing_ocr_score")])
def test_weak_or_missing_cue_and_value_scores(clean, extract, index, score, reason):
    clean["pages"][0]["tokens"][index]["ocr_score"] = score
    report = extract(clean)
    assert report.total_myr.reasons == (reason,)
    assert len(report.document.pages[0].tokens) == 10
    assert report.total_myr.candidates[0].min_ocr_score == score
    assert report.record is None


def test_missing_score_does_not_hide_another_low_score(clean, extract):
    tokens = clean["pages"][0]["tokens"]
    tokens[6]["ocr_score"], tokens[9]["ocr_score"] = None, 20
    field = extract(clean).total_myr
    assert set(field.reasons) == {"missing_ocr_score", "low_ocr_score"}
    assert field.candidates[0].min_ocr_score is None


@pytest.mark.parametrize("value,expected", [("RM 0.01", "0.01"), ("MYR 999,999,999.99", "999999999.99"), ("RM 1234.50", "1234.50")])
def test_exact_decimal_normalization(clean, extract, value, expected):
    set_total(clean, value)
    assert extract(clean).record["total_myr"] == expected


@pytest.mark.parametrize("value,reason", [
    ("1234.50", "unsupported_currency"), ("USD 1234.50", "unsupported_currency"),
    ("RM 1,23.45", "invalid_amount"), ("RM -1.00", "invalid_amount"),
    ("RM +1.00", "invalid_amount"), ("RM 1.0", "invalid_amount"),
    ("RM 1.00 2.00", "invalid_amount"), ("RM 1.00 paid", "invalid_amount"),
    ("RM 0.00", "amount_out_of_range"), ("RM 1000000000.00", "amount_out_of_range"),
])
def test_invalid_amount_is_retained(clean, extract, value, reason):
    set_total(clean, value)
    report = extract(clean)
    assert report.total_myr.value is None
    assert reason in report.total_myr.reasons
    assert report.total_myr.candidates[0].raw_value == value
    assert report.total_myr.candidates[0].normalized_value is None


@pytest.mark.parametrize("value", ["2026-02-29", "20/10/2026", "2026-13-01", "2026-1-01", "2026-10-20 trailing"])
def test_invalid_date_routes_review(clean, extract, value):
    clean["pages"][0]["tokens"][5]["text"] = value
    report = extract(clean)
    assert report.invoice_date.reasons == ("invalid_date",)
    assert report.invoice_date.candidates[0].raw_value == value


@pytest.mark.parametrize("value", ["a123", "A", "A" * 33, "INV_123", "INV 123"])
def test_identifier_does_not_apply_ocr_substitutions(clean, extract, value):
    clean["pages"][0]["tokens"][2]["text"] = value
    assert extract(clean).invoice_number.reasons == ("invalid_identifier",)


def test_missing_and_distractor_cues(clean, extract):
    tokens = clean["pages"][0]["tokens"]
    tokens[3]["text"], tokens[4]["text"] = "Due", "Date:"
    tokens[6]["text"], tokens[7]["text"] = "Subtotal", "amount:"
    report = extract(clean)
    assert report.invoice_date.candidates == report.total_myr.candidates == ()
    assert report.invoice_date.reasons == report.total_myr.reasons == ("missing",)
    assert report.record is None


@pytest.mark.parametrize("key", [[1, 1, 4], [2, 1, 3]])
def test_next_line_or_other_block_cannot_supply_value(clean, extract, key):
    for token in clean["pages"][0]["tokens"][-2:]:
        token["line_key"] = key
    field = extract(clean).total_myr
    assert field.reasons == ("missing_value",)
    assert field.candidates[0].evidence.value_token_ids == ()
    assert field.candidates[0].evidence.value_bbox is None


@pytest.mark.parametrize("change,reason", [("overlap", "ambiguous_geometry"), ("distant", "ambiguous_layout"), ("vertical", "ambiguous_layout")])
def test_geometry_prevents_unsupported_association(clean, extract, change, reason):
    tokens = clean["pages"][0]["tokens"]
    if change == "overlap":
        tokens[7]["bbox"][2] = tokens[8]["bbox"][0] + 1
    elif change == "distant":
        for token in tokens[8:]:
            token["bbox"][0] += 400
            token["bbox"][2] += 400
    else:
        for token in tokens[8:]:
            token["bbox"][1] += 40
            token["bbox"][3] += 40
    field = extract(clean).total_myr
    assert reason in field.reasons
    assert field.value is None
    assert field.candidates[0].normalized_value == Decimal("1234.50")


def test_multiple_target_cues_review_both_fields(clean, extract):
    tokens = clean["pages"][0]["tokens"]
    for token in tokens[3:6]:
        token["line_key"] = [1, 1, 1]
        token["bbox"] = [token["bbox"][0] + 450, 90, token["bbox"][2] + 450, 120]
    report = extract(clean)
    for field in (report.invoice_number, report.invoice_date):
        assert field.value is None
        assert "multiple_cues" in field.reasons
        assert len(field.candidates) == 1


def test_labels_are_case_and_punctuation_tolerant(clean, extract):
    tokens = clean["pages"][0]["tokens"]
    tokens[0]["text"], tokens[1]["text"] = "invoice", "NUMBER."
    tokens[6]["text"], tokens[7]["text"] = "aMoUnT", "DuE:"
    assert extract(clean).status == "extracted"


def test_token_permutation_preserves_semantics_and_truthful_fingerprint(clean, extract):
    original = extract(clean).to_dict()
    random.Random(42).shuffle(clean["pages"][0]["tokens"])
    shuffled = extract(clean).to_dict()
    assert original.pop("source_sha256") != shuffled.pop("source_sha256")
    assert original == shuffled


def test_candidate_limit_fails_whole_run(clean, extract):
    page = clean["pages"][0]
    total = deepcopy(page["tokens"][6:])
    page["tokens"] = []
    for line in range(65):
        for original in total:
            token = deepcopy(original)
            token["id"] += f"-{line}"
            token["line_key"] = [1, 1, line + 1]
            page["tokens"].append(token)
    with pytest.raises(InvoiceError, match="^candidate_limit$"):
        extract(clean)
