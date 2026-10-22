"""Independently derive retrieval expectations through the experiment interface.

This qualification checks the installed package, paired report counts, lineage
integrity, and selection isolation. It supplies no alternate learning policy.
"""

from dataclasses import asdict, replace
import hashlib
from itertools import combinations
import json

from self_improving import ScenarioName, load_scenario, run_experiment
from self_improving.experiment import Group, LabeledCase, Query


def digest(value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def expected(corpus, query, recency_topic):
    eligible = [document for document in corpus
                if document.topic == query.topic
                and set(document.tokens) & set(query.tokens)]
    if not eligible:
        return None
    largest_overlap = max(len(set(document.tokens) & set(query.tokens))
                          for document in eligible)
    finalists = [document for document in eligible
                 if len(set(document.tokens) & set(query.tokens)) == largest_overlap]
    if query.topic == recency_topic:
        largest_revision = max(document.revision for document in finalists)
        finalists = [document for document in finalists
                     if document.revision == largest_revision]
    return min(document.document_id for document in finalists)


def main():
    expected_statuses = {
        "improvement": "review_required",
        "regression": "rejected_regression",
        "insufficient": "no_proposal_insufficient",
        "poisoned": "no_proposal_insufficient",
        "development-rejection": "rejected_development",
        "no-gain": "rejected_no_gain",
    }
    scenarios_checked = 0
    for name in ScenarioName:
        data = load_scenario(name)
        before = repr(data)
        report = run_experiment(data)
        public = report.to_dict()
        assert public["status"] == expected_statuses[name.value], public["status"]
        assert public["serving_version_id"] == public["baseline"]["version_id"]
        assert public["corpus_digest"] == digest([asdict(doc) for doc in data.selection.corpus])
        assert public["selection_digest"] == digest(asdict(data.selection))
        assert public["holdout_digest"] == digest([asdict(case) for case in data.holdout])
        versions = [public["baseline"]]
        if "proposal" in public:
            versions.append(public["proposal"]["candidate"])
            assert versions[-1]["parent_version_id"] == versions[0]["version_id"]
        for version in versions:
            version_payload = {key: value for key, value in version.items() if key != "version_id"}
            assert version["version_id"] == digest(version_payload)
        assert repr(data) == before
        assert report.to_json() == run_experiment(data).to_json()
        claimed = public.pop("report_digest")
        assert claimed == digest(public)
        for section in ("development", "heldout"):
            if section not in public:
                continue
            result = public[section]
            assert result["baseline_correct"] == sum(
                case["baseline_correct"] for case in result["cases"])
            assert result["candidate_correct"] == sum(
                case["candidate_correct"] for case in result["cases"])
            actual_losses = [case["query"]["query_id"] for case in result["cases"]
                             if case["baseline_correct"] and not case["candidate_correct"]]
            assert actual_losses == result["lost_query_ids"]
        if name.value == "regression":
            result = public["heldout"]
            assert result["candidate_correct"] > result["baseline_correct"]
            assert result["lost_query_ids"]
        if name.value in ("insufficient", "poisoned"):
            assert all(key not in public for key in ("proposal", "development", "heldout"))
        scenarios_checked += 1

    data = load_scenario(ScenarioName.IMPROVEMENT)
    original = run_experiment(data)
    topic = original.proposal.topic
    selection = data.selection
    vocabulary = sorted({token for document in selection.corpus for token in document.tokens})[:8]
    topics = sorted({document.topic for document in selection.corpus}) + ["unknown"]
    queries = []
    for size in range(4):
        for subset in combinations(vocabulary, size):
            for query_topic in topics:
                tokens = tuple(sorted((*subset, "oracleprobe")))
                queries.append(Query(f"oracle_{len(queries)}", query_topic, tokens))
    assertions = 0
    for start in range(0, len(queries), 98):
        batch = queries[start:start + 98]
        labels = tuple(LabeledCase(query, expected(selection.corpus, query, topic),
                                   Group.RECENT if index % 2 == 0 else Group.STABLE)
                       for index, query in enumerate(batch))
        if len(labels) == 1:
            tail_query = replace(labels[0].query, query_id="oracle_tail",
                                 tokens=tuple(sorted((*labels[0].query.tokens, "oracletail"))))
            labels += (replace(labels[0], query=tail_query,
                               group=Group.STABLE),)
        report = run_experiment(replace(data, holdout=labels))
        assert report.proposal == original.proposal
        for case in report.heldout.cases:
            assert case.baseline.selected_document_id == expected(selection.corpus, case.query, None)
            assert case.candidate.selected_document_id == expected(selection.corpus, case.query, topic)
            assertions += 2

    changed_labels = tuple(replace(case, expected_document_id=None) for case in data.holdout)
    changed_report = run_experiment(replace(data, holdout=changed_labels))
    assert changed_report.proposal == original.proposal
    assert changed_report.holdout_digest != original.holdout_digest
    assert changed_report.to_json() != original.to_json()
    print(json.dumps({"scenarios_checked": scenarios_checked,
                      "oracle_queries": len(queries),
                      "oracle_choice_assertions": assertions,
                      "heldout_label_isolation": "passed",
                      "report_digest_and_repeatability": "passed"}, sort_keys=True))


if __name__ == "__main__":
    main()
