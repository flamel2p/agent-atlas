# Typed Decision Agent

Slug: 31-typed-decision
Status: planned
Runtime: undecided
Library ID: 31

## Purpose and contract

A planned Jev-inspired library/demo for typed categorical predictions with explicit probability provenance, strict validation, and abstention. The first scenario will classify synthetic business messages into caller-defined labels. See [SPEC.md](SPEC.md) for selected scope, proposed behavior, acceptance criteria, and open decisions.

The name describes the learning objective without promising that this case reproduces TypeSafe AI's model or its calibration. **Jev** is the official product spelling. #31 is an Agent Atlas extension beyond the book's numbered list; the supplemental book pattern keeps its existing identity.

## Architecture and flow

Proposed: validate request → make one prediction attempt → validate label probabilities → derive confidence → return a typed decision or abstention. Invalid output, backend failure, timeout, and cancellation stop explicitly. State is request-local and results have no business-system effects.

The planned first implementation covers categorical selection only. Jev's numerical/boolean primitives, shared-state question batches, model training, images, serving, and integrations are deferred. This case emphasizes reusable prediction contracts; it does not duplicate the support-autonomy scenario in #01 or depend on that case's code.

## Setup and run

No runnable implementation is available. Runtime, backend, exact schema, and operational bounds remain undecided. No dependencies or provider credentials are required for this documentation scaffold. Setup, library usage, CLI examples, and case-local test commands will be recorded when implemented.

Next action: select a backend with explicit probability semantics and a labeled evaluation set, then finalize the contract before implementation. An ordinary LLM's self-reported confidence does not establish calibrated probabilities.

## Verification

Not implemented or run. Fixture, mocked-provider, live-model, calibration, and deployment validation remain unverified. The repository structure check can validate documentation metadata and catalogue registration only; it cannot establish runtime readiness.

Documentation verification on 2026-10-18, local macOS: `python3 scripts/check_structure.py` from the repository root passed. A local link-target check also passed for the root README and this case's three Markdown documents. These are documentation/governance checks, not runtime evidence.

## Limitations and references

Inspired by [TypeSafe AI's Jev](https://docs.typesafe.ai/introduction), its [typed primitives](https://docs.typesafe.ai/primitives), and [confidence semantics](https://docs.typesafe.ai/confidence), inspected on 2026-10-18. Source claims and selected original design choices are separated in [SPEC.md](SPEC.md).

The official [System One Adapter](https://github.com/typesafe-ai/system-one-adapter-python) is a possible implementation reference; no code has been copied or dependency selected. There is no claim of API compatibility, empirical calibration, equivalent speed/cost, or production qualification.
