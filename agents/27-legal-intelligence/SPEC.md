# Legal Intelligence Agent specification

Slug: 27-legal-intelligence
Status: demo-ready
Runtime: Python 3.14 (uv CLI)

## Selected scope and source limits

This original deterministic learning demo retrieves, ranks, drafts, and verifies a memorandum in fictional Alder and Brume jurisdictions. No real legal corpus, legal advice, client matters, network, model, filing, messages, persistent state, or human approval exists. The [source brief](../../agent-library-analysis/agents/27-legal-intelligence.md), [inventory](../../agent-library-analysis/agent-inventory.md), and [foundations](../../agent-library-analysis/foundations.md) inform the learning pattern, not evidence of correctness. The book's open helpers and unsafe empty-citation/current-status defaults are not adopted.

Exact structured issue/rule tags replace free-text legal inference. Only host-owned rule sentences appear in the memo. The host checks exact source support, rather than treating a known citation as sufficient. Sample-contract and clause review are deferred by parent scope refinement to keep one coherent memo flow.

## JSON input contract

The CLI accepts `--input PATH`, or no arguments for packaged `matter.json`. No stdin, report-file option, environment configuration, provider, or arbitrary corpus adapter exists. Top-level has required `matter` and optional `draft` only.

`matter` has exactly `matter_id` (ASCII identifier 1–48 characters from letters, digits, underscore, hyphen), `jurisdiction` (`ALDER` or `BRUME`), and `issues` (1–3 unique tags from `notice`, `export`, `retention`). Facts and narrative are intentionally absent.

If present, `draft` is an array of 0–6 claim objects with exactly `issue`, `rule`, and `citations`. `issue` uses those three tags. `rule` is one of `notice_before_pause`, `export_opt_in`, `retention_cap`. Each citations array has 0–4 objects with exactly `authority_id` and `version`, each an ASCII identifier of 1–48 characters. Duplicate claim issues or citation pairs are invalid input. Empty drafts/citation arrays are valid proposals that fail verification. Inapplicable claim tags are blocked, never silently removed.

Objects reject unknown/missing fields. JSON rejects duplicate keys, NaN/Infinity, all numbers, booleans, null, invalid UTF-8, and unpaired surrogates. Only schema strings, arrays, and objects are accepted. Maximum input is 32,768 bytes, nesting eight container levels, and strings 512 Unicode characters before field-specific limits. Depth is scanned before parsing.

Explicit paths are read only. Each component must be a real directory and the leaf a regular file. Symlinks in any component, FIFOs, sockets, and directories are rejected. Descriptor-relative no-follow traversal, nonblocking open, fstat, and bounded read enforce the boundary. Reading the requested file and writing stdout/stderr are the only effects. Packaged corpus data is trusted original fiction, checked against its own strict schema and invariants at load time.

## Corpus, ranking, and applicability

Packaged `corpus.json` is original fiction. Snapshot `alder-brume-2026-10-01` is recorded at `2026-10-01T00:00:00Z`. Each authority has unique `authority_id`, `version`, `jurisdiction`, integer `authority_rank` (1 or 2, lower wins), `status` (`current`, `superseded`, `unknown`), `issue`, `rule`, exact host-owned `holding`, and provenance `original-fiction:<authority_id>`. Missing status is a corpus error, never current. Status refers only to this synthetic snapshot, not real good law or a current external database.

Retrieval scans the finite corpus per requested issue, retains exact issue matches in the requested jurisdiction with explicit current status and host issue-to-rule agreement, and sorts by rank then ID. No semantic score or probabilistic confidence exists. High rank cannot cure inapplicability. Limits are 16 authorities, three issues, six claims, and 24 citations. There is no retry, repair, fallback, persistence, or background task.

Absent `draft`, the host selects the first ranked eligible source per covered issue and constructs one claim with exact issue/rule/citation version. Uncovered issues yield no claim. Supplied structured drafts pass unchanged to verification. Memo sentences come from fixed rule text; user prose cannot manufacture support.

## Verification and terminal states

Every citation yields findings, including source provenance/status when known. A citation passes only if ID exists, version matches, jurisdiction matches, status is explicitly current, source issue/rule match the claim, claim issue belongs to the matter, and claim rule matches host issue policy. All failing conditions are recorded. Empty citations produce `empty_citations`; empty draft produces `empty_draft`. Coverage counts only claims with citations and no failures. Every requested issue must be covered and every claim must pass.

Transitions are `validated → retrieved → drafted → verified → simulated_reviewer_handoff` on success, ending `blocked_review` on failure. `simulated_release` is true only on success. Both set `human_approval: not_granted`, `review_required: true`, and `reviewer: fictional-review-desk`. Simulated handoff is a returned record, never a message or assertion of human review.

Reports include outcome, transitions, matter identity/jurisdiction, corpus snapshot/time, ranked retrieval, tagged memo with host sentences, citation findings, uncovered issues, blockers, and simulated review state. A passing simulated handoff exits 0; blocked verification exits 1. Input/file/corpus errors produce bounded `invalid_input` JSON and exit 2 without a memo or release. Errors do not echo raw input or file contents. Keyboard interruption returns `cancelled`, no release, and exit 130. Closed stdout for help/errors/results stops quietly nonzero in buffered and unbuffered execution. Argument errors use controlled output and exit 2.

## Acceptance criteria

Normal fixture covers notice and export in ALDER using ALD-101 and ALD-201 (rank 1), complete passing findings, original provenance, fixed snapshot metadata, and simulated handoff without human approval. ALD-102 ranks second for notice. Fabricated IDs, stale versions, superseded/unknown status, wrong jurisdiction, incorrect issue/rule applicability, empty citations/drafts, and uncovered retention block release. Existence cannot validate unsupported conclusions. Input cannot alter corpus or policy.

Checks cover those outcomes, repeatability, JSON/schema bounds, file authority, hostile packaged metadata, and actual CLI processes. Qualification includes case-only copy and installed wheel outside checkout. Independent review passed. The parent owns catalogue integration. Fixture evidence does not establish live-model, real-service, deployment, production, or professional qualification.
