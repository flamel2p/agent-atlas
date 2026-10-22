"""Behavior checks for actual revisions, closed grammar, provenance, and bounds."""

from dataclasses import FrozenInstanceError, replace
import hashlib
import unittest
from unittest.mock import patch

from content_creation import Brief, InputError, create_content
from content_creation.boundary import _resource_bytes, load_scenario, load_snapshot
from content_creation.domain import Draft, Evidence, initial_plan, normalized, render, review


def reflow(draft, blocks):
    """Build adversarial drafts without using the production renderer."""
    text = ""
    rewritten = []
    evidence = []
    previous = None
    for block in blocks:
        if block.section != previous:
            text += ("\n\n" if text else "") + block.section + "\n"
        else:
            text += "\n"
        start = len(text)
        text += block.text
        rewritten.append(replace(block, start=start, end=len(text)))
        if block.kind == "fact":
            original = next((item for item in draft.evidence if item.fact_id == block.reference), draft.evidence[0])
            evidence.append(replace(original, fact_id=block.reference, start=start, end=len(text)))
        previous = block.section
    return Draft(draft.kind, text, tuple(rewritten), tuple(evidence))


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = load_snapshot()
        self.relaxed = load_scenario("relaxed")

    def assert_provenance(self, attempt):
        seen = set()
        for record in attempt.evidence:
            fact = self.snapshot.fact(record.fact_id)
            self.assertNotIn(record.fact_id, seen)
            seen.add(record.fact_id)
            self.assertEqual(record.source_id, fact.source_id)
            self.assertEqual(record.fixture_sha256, self.snapshot.sha256)
            self.assertEqual(attempt.text[record.start:record.end], fact.text)

    def test_launch_has_real_feedback_and_passing_revisions(self):
        result = create_content(load_scenario("launch"))
        self.assertEqual(result.status, "validated")
        self.assertEqual(result.approval, "not_granted")
        self.assertEqual(tuple(item.kind for item in result.artifacts), ("email", "documentation"))
        for artifact in result.artifacts:
            self.assertEqual(len(artifact.attempts), 2)
            rejected, passing = artifact.attempts
            self.assertIn("seamless", rejected.text)
            self.assertNotEqual(rejected.text, passing.text)
            self.assertEqual(rejected.violations[0].code, "forbidden_phrase")
            change = rejected.next_changes[0]
            self.assertIn(change.before, rejected.text)
            self.assertIn(change.after, passing.text)
            self.assertNotIn(change.before, passing.text)
            self.assertFalse(passing.violations)
            self.assertFalse(passing.next_changes)
            self.assertEqual(artifact.validated_text, passing.text)
            for attempt in artifact.attempts:
                self.assertEqual(attempt.word_count, len(attempt.text.split()))
                self.assert_provenance(attempt)

    def test_relaxed_and_changed_forbidden_input_change_behavior(self):
        relaxed = create_content(self.relaxed)
        absent = create_content(replace(self.relaxed, forbidden_phrases=("available workflow",)))
        blocked = create_content(replace(self.relaxed, forbidden_phrases=("coordination",)))
        for first, second, third in zip(relaxed.artifacts, absent.artifacts, blocked.artifacts):
            self.assertEqual(len(first.attempts), 1)
            self.assertEqual(first.validated_text, second.validated_text)
            self.assertEqual(len(third.attempts), 2)
            self.assertNotEqual(first.validated_text, third.validated_text)
            self.assertEqual(third.attempts[0].violations[0].value, "coordination")

    def test_all_openings_banned_reaches_exact_retry_limit(self):
        result = create_content(load_scenario("exhausted"))
        self.assertEqual(result.status, "unapproved")
        for artifact in result.artifacts:
            self.assertEqual(artifact.status, "unapproved_limit")
            self.assertIsNone(artifact.validated_text)
            self.assertEqual(len(artifact.attempts), 3)
            self.assertEqual(len({item.text for item in artifact.attempts}), 3)
            self.assertEqual([item.number for item in artifact.attempts], [1, 2, 3])
            self.assertTrue(all(item.violations for item in artifact.attempts))
            self.assertTrue(all(item.next_changes for item in artifact.attempts[:-1]))
            self.assertFalse(artifact.attempts[-1].next_changes)

    def test_length_repair_drops_lowest_priority_optional_fact(self):
        brief = load_scenario("length-repair")
        result = create_content(brief)
        self.assertEqual(result.status, "validated")
        for artifact in result.artifacts:
            self.assertEqual(len(artifact.attempts), 2)
            first, final = artifact.attempts
            expected = initial_plan(brief, self.snapshot, artifact.kind).optional[-1]
            self.assertEqual(first.next_changes[0].target, expected)
            self.assertNotIn(expected, [item.fact_id for item in final.evidence])
            self.assertLess(final.word_count, first.word_count)
            for fact_id in brief.required_fact_ids:
                self.assertEqual(final.text.count(self.snapshot.fact(fact_id).text), 1)
            self.assert_provenance(final)

    def test_length_can_shorten_copy_without_removing_required_facts(self):
        required = tuple(item.id for item in self.snapshot.facts)
        brief = replace(self.relaxed, required_fact_ids=required)
        base = create_content(brief)
        count = base.artifacts[0].attempts[0].word_count
        result = create_content(replace(brief, email_max_words=count - 3, docs_max_words=count - 3))
        for artifact in result.artifacts:
            self.assertEqual(artifact.status, "validated")
            self.assertEqual(artifact.attempts[0].next_changes[0].action, "shorten_copy")
            self.assertEqual(set(item.fact_id for item in artifact.attempts[-1].evidence), set(required))

    def test_brand_repair_precedes_length_when_both_fail(self):
        brief = replace(load_scenario("launch"), email_max_words=65, docs_max_words=65)
        result = create_content(brief)
        for artifact in result.artifacts:
            self.assertEqual(len(artifact.attempts), 3)
            self.assertEqual({item.category for item in artifact.attempts[0].next_changes}, {"brand"})
            self.assertEqual({item.category for item in artifact.attempts[1].next_changes}, {"length"})
            self.assertEqual(artifact.status, "validated")

    def test_required_fact_ban_stops_without_unchanged_retry(self):
        result = create_content(replace(self.relaxed, forbidden_phrases=("available only",)))
        for artifact in result.artifacts:
            self.assertEqual(artifact.status, "unapproved_no_repair")
            self.assertEqual(len(artifact.attempts), 1)
            self.assertIsNone(artifact.validated_text)
            self.assertFalse(artifact.attempts[0].next_changes)

    def test_optional_fact_brand_violation_can_remove_only_optional_content(self):
        result = create_content(replace(self.relaxed, forbidden_phrases=("seven-day",)))
        for artifact in result.artifacts:
            self.assertEqual(artifact.status, "validated")
            self.assertEqual(artifact.attempts[0].next_changes[0].action, "drop_optional_fact")
            self.assertEqual(artifact.attempts[0].next_changes[0].target, "history")

    def test_impossible_length_never_releases_validated_text(self):
        result = create_content(load_scenario("impossible-length"))
        self.assertEqual(result.status, "unapproved")
        for artifact in result.artifacts:
            self.assertIsNone(artifact.validated_text)
            self.assertLessEqual(len(artifact.attempts), 3)
            self.assertTrue(all(item.word_count > 1 for item in artifact.attempts))
            self.assertFalse(artifact.attempts[-1].next_changes)

    def test_passing_channel_is_frozen_during_other_channel_failure(self):
        result = create_content(load_scenario("mixed"))
        self.assertEqual(result.status, "unapproved")
        self.assertEqual(result.artifacts[0].status, "validated")
        self.assertEqual(len(result.artifacts[0].attempts), 1)
        self.assertEqual(result.artifacts[1].status, "unapproved_limit")

    def test_exact_word_boundary_passes_and_one_less_requires_change(self):
        initial = create_content(self.relaxed)
        size = initial.artifacts[0].attempts[0].word_count
        equal = create_content(replace(self.relaxed, email_max_words=size, docs_max_words=size))
        below = create_content(replace(self.relaxed, email_max_words=size - 1, docs_max_words=size - 1))
        for artifact in equal.artifacts:
            self.assertEqual(len(artifact.attempts), 1)
        for artifact in below.artifacts:
            self.assertIn("word_limit", {item.code for item in artifact.attempts[0].violations})
            self.assertNotEqual(artifact.attempts[0].text, artifact.attempts[-1].text)

    def test_audience_ranking_has_stable_id_ties(self):
        team = initial_plan(self.relaxed, self.snapshot, "email")
        dev = initial_plan(replace(self.relaxed, audience="developers"), self.snapshot, "email")
        self.assertEqual(team.optional, ("reminders", "access", "history"))
        self.assertEqual(dev.optional, ("access", "history", "reminders"))

    def test_fixture_read_once_digest_bytes_unchanged_and_runs_independent(self):
        raw = _resource_bytes("content.json")
        with patch("content_creation.boundary._resource_bytes", return_value=raw) as reader:
            first = create_content(self.relaxed)
            reader.assert_called_once_with("content.json")
        create_content(load_scenario("exhausted"))
        second = create_content(self.relaxed)
        self.assertEqual(first, second)
        self.assertEqual(first.fixture_sha256, hashlib.sha256(raw).hexdigest())
        self.assertEqual(raw, _resource_bytes("content.json"))
        with self.assertRaises(FrozenInstanceError):
            first.status = "unapproved"
        with self.assertRaises(FrozenInstanceError):
            self.relaxed.audience = "developers"

    def test_public_api_rejects_wrong_shape_and_unknown_fact_before_drafting(self):
        with patch("content_creation.domain.render") as renderer:
            for value in (None, {}, "launch", replace(self.relaxed, required_fact_ids=("unknown",))):
                with self.subTest(value=type(value)), self.assertRaises(InputError):
                    create_content(value)
            renderer.assert_not_called()
        damaged = replace(self.relaxed)
        object.__setattr__(damaged, "email_max_words", True)
        with self.assertRaises(InputError):
            create_content(damaged)

    def test_reordered_renderer_cannot_release_validated_content(self):
        def reordered(plan, snapshot):
            draft = render(plan, snapshot)
            blocks = list(draft.blocks)
            blocks[2:-1] = reversed(blocks[2:-1])
            return reflow(draft, blocks)

        with patch("content_creation.domain.render", side_effect=reordered):
            result = create_content(self.relaxed)
        self.assertEqual(result.status, "unapproved")
        for artifact in result.artifacts:
            self.assertEqual(artifact.status, "unapproved_no_repair")
            self.assertIsNone(artifact.validated_text)
            self.assertEqual(len(artifact.attempts), 1)
            self.assertEqual({item.code for item in artifact.attempts[0].violations}, {"fact_order"})


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = load_snapshot()
        self.brief = load_scenario("relaxed")
        self.draft = render(initial_plan(self.brief, self.snapshot, "email"), self.snapshot)

    def codes(self, draft):
        return {item.code for item in review(draft, self.brief, self.snapshot)}

    def test_canonical_render_passes(self):
        self.assertEqual(review(self.draft, self.brief, self.snapshot), ())

    def test_required_and_optional_order_are_checked_independently_of_draft(self):
        blocks = list(self.draft.blocks)
        required_end = 2 + len(self.brief.required_fact_ids)
        for start, end in ((2, required_end), (required_end, len(blocks) - 1)):
            reordered = blocks.copy()
            reordered[start:end] = reversed(reordered[start:end])
            with self.subTest(start=start):
                self.assertEqual(self.codes(reflow(self.draft, reordered)), {"fact_order"})
        changed = replace(self.brief, required_fact_ids=tuple(reversed(self.brief.required_fact_ids)))
        valid = render(initial_plan(changed, self.snapshot, "email"), self.snapshot)
        self.assertEqual(review(valid, changed, self.snapshot), ())

    def test_real_id_with_altered_qualified_fact_is_rejected(self):
        blocks = list(self.draft.blocks)
        blocks[2] = replace(blocks[2], text=blocks[2].text.replace("only ", ""))
        counterfeit = reflow(self.draft, blocks)
        self.assertIn("fact_text", self.codes(counterfeit))
        self.assertIn("provenance", self.codes(counterfeit))

    def test_text_only_mutation_and_unaccounted_prose_fail(self):
        self.assertIn("block_span", self.codes(replace(self.draft, text=self.draft.text.replace("only", "also"))))
        self.assertIn("structure", self.codes(replace(self.draft, text=self.draft.text + "\nLumenBoard is unlimited.")))

    def test_forged_missing_extra_duplicate_and_reordered_evidence(self):
        first = self.draft.evidence[0]
        mutations = (
            replace(first, source_id="demo_features"), replace(first, fixture_sha256="0" * 64),
            replace(first, start=first.start + 1), replace(first, end=first.end - 1),
            replace(first, start=True), replace(first, start=-1), replace(first, fact_id="unknown"),
        )
        for forged in mutations:
            with self.subTest(forged=forged):
                self.assertIn("provenance", self.codes(replace(self.draft, evidence=(forged,) + self.draft.evidence[1:])))
        for evidence in (self.draft.evidence[1:], self.draft.evidence + (first,), ()):
            self.assertIn("provenance", self.codes(replace(self.draft, evidence=evidence)))
        self.assertEqual(self.codes(replace(self.draft, evidence=tuple(reversed(self.draft.evidence)))), set())

    def test_valid_citation_cannot_authorize_arbitrary_copy(self):
        blocks = list(self.draft.blocks)
        blocks[1] = replace(blocks[1], text="LumenBoard has unlimited capacity.")
        draft = reflow(self.draft, blocks)
        forged = replace(draft.evidence[0], start=draft.blocks[1].start, end=draft.blocks[1].end)
        draft = replace(draft, evidence=draft.evidence + (forged,))
        self.assertIn("copy_vocabulary", self.codes(draft))
        self.assertIn("provenance", self.codes(draft))

    def test_duplicate_missing_unknown_fact_and_damaged_order_fail(self):
        blocks = list(self.draft.blocks)
        self.assertIn("required_coverage", self.codes(reflow(self.draft, blocks[:2] + blocks[3:])))
        self.assertIn("duplicate_fact", self.codes(reflow(self.draft, blocks[:3] + [blocks[2]] + blocks[3:])))
        blocks[2] = replace(blocks[2], reference="unknown")
        self.assertIn("unknown_fact", self.codes(reflow(self.draft, blocks)))
        blocks = list(self.draft.blocks)
        blocks[0], blocks[1] = blocks[1], blocks[0]
        self.assertIn("structure", self.codes(reflow(self.draft, blocks)))

    def test_wrong_block_offsets_and_fact_outside_details_fail(self):
        blocks = list(self.draft.blocks)
        blocks[2] = replace(blocks[2], end=blocks[2].end + 1)
        self.assertIn("block_span", self.codes(replace(self.draft, blocks=tuple(blocks))))
        blocks[2] = replace(blocks[2], section="Introduction")
        self.assertIn("structure", self.codes(reflow(self.draft, blocks)))

    def test_unicode_casefold_whitespace_and_cross_block_brand_matches(self):
        self.assertEqual(normalized("  STRAẞE\t\n Update  "), "strasse update")
        phrase = "  DISCOVER\t\nSEAMLESS\rCOORDINATION.  "
        findings = review(self.draft, replace(self.brief, forbidden_phrases=(phrase,)), self.snapshot)
        self.assertIn("forbidden_phrase", {item.code for item in findings})
        spanning = replace(self.brief, forbidden_phrases=("coordination. details lumenboard",))
        result = create_content(spanning)
        self.assertEqual(result.status, "validated")
        self.assertEqual(len(result.artifacts[0].attempts), 2)

    def test_exclamation_and_missing_product_are_explicit(self):
        altered = replace(self.draft, text=self.draft.text.replace("LumenBoard", "Lumenboard") + "!")
        self.assertIn("exclamation", self.codes(altered))
        self.assertIn("product_spelling", self.codes(altered))


if __name__ == "__main__":
    unittest.main()
