# Scientific Discovery implementation plan

[SPEC.md](SPEC.md) owns the behavior contract. Parent selected this isolated synthetic scope after design passes recorded in the [batch plan](../../docs/AGENTS_22_32_PLAN.md).

## Ownership and sequence

The case directory is the only implementation ownership unit. The parent owns root catalogue changes, independent review, integration, and commits. No sibling code is imported.

1. Completed. Finalized strict field schemas, finite arithmetic, scope/authority, byte/depth/value bounds, and terminal outcomes in SPEC.md before the first acceptance run.
2. Completed. Implemented immutable typed domain records, bounded regular-file/JSON CLI, original packaged corpus, run-local transitions, and explicit policy gates.
3. Completed. Added 37 checks with independently calculated expectations, meaningful incomplete-evidence and constraint failures, zero/negative measurement feedback, input adversaries, process failure boundaries, and isolation.
4. Completed. Ran source CLI and rerunnable `scripts/qualify.py`. All 37 checks passed separately in source, standalone copy, and installed wheel. Packaged fixture runs passed outside repository context through copied module and installed module/console entry points.
5. Completed independent review and fix verification. The parent owns phased commits and root catalogue integration.

## Selected routine decisions

The host models each synthetic paper as a supplied effect assertion for one topic or an unordered tested pair. Citation references retain internal provenance. Missing declared sources, empty sources, dangling citations, or any topic without singleton evidence block proposal generation and mark novelty unverified. Complete coverage refers only to declared synthetic inputs.

At most 28 pairs are enumerated from 8 topics. Lexicographic selection is stable and chooses one candidate. Equal-weight singleton means yield an explicitly unvalidated additive hypothesis. All contributing evidence and ranges remain available; no confidence score is invented. Baseline and two singleton controls plus the combined arm give a 12-run virtual plan costing 24 synthetic credits. Supplied three-value measurements cover only the combined arm. Absolute error avoids zero division. Feedback changes no state outside the report.

The strict parser rejects unknown/duplicate keys and invalid numerics before domain work. It retains valid missing-evidence references for coverage failure rather than inventing evidence. Final input symlinks and nonregular files are blocked. The CLI explicitly writes and flushes help instead of allowing argparse to suppress unbuffered output failures; this was verified against closed pipes in both buffering modes. An injected KeyboardInterrupt at the input boundary verified that early interruption produces no report; an external SIGINT timing test was not run.

## Qualification and limits

Actual evidence and commands are recorded in [README.md](README.md). Runtime is Python 3.14.8 with no dependencies. Case-local packaging pins hatchling 1.32.4. The qualification script creates and removes standalone copies and installed-wheel environments outside the repository. This remains synthetic fixture evidence only. No live provider, real literature, experiment, training, deployment, production readiness, global novelty, or scientific validity is claimed.

## Review reconciliation

Independent review identified unbounded raw argument diagnostics. The new subprocess regression failed before the fix and passes after overriding parser errors into InvalidInput. The parent reran 37 tests per source/copy/wheel environment. Independent fix review passed.
