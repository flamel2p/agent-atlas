# Agents 22–32 implementation plan

The selected scope is eleven independently runnable learning demos. Each case owns its specification, implementation, dependencies, fixtures, checks, and evidence. This document coordinates delivery; each case's `SPEC.md` owns behavior.

## Selected architecture

Use a small case-local Python package and CLI. Typed records define input, evidence, state transitions, and terminal results. Pure functions implement numerical rules. Host-owned gates control every simulated effect. No shared application runtime or sibling imports are introduced.

Two independent design passes compared a pure-function CLI design with explicit state machines around immutable evidence records. The synthesis uses pure functions for calculations and state transitions where proposal, review, simulation, or revision is the lesson. A generic object-oriented agent framework adds no necessary capability here.

The first implementations of 22–31 use original synthetic fixtures and deterministic adapters. These establish behavior contracts, not model quality, calibration, professional advice, scientific novelty, or hardware safety. Case 32 preserves its existing OpenAPI-first generator contract and requires actual generated-server protocol and fixture-service evidence.

## Case contracts

| Case | Selected scenario and behavior | Required failure or limit evidence |
| --- | --- | --- |
| [22 Ethical Reasoning](../agents/22-ethical-reasoning/SPEC.md) | Versioned policy checks, one mitigation, audit, guarded simulated dispatch | Forbidden disclosure or unresolved disparity executes no effect |
| [23 Explainable](../agents/23-explainable/SPEC.md) | Synthetic priority rules and audience explanations from one actual trace | Missing evidence or explanation failure prevents fabricated justification |
| [24 Healthcare Intelligence](../agents/24-healthcare-intelligence/SPEC.md) | Fictional conditions, normalized observations, provenance, Bayesian update, simulated review | Invalid likelihood mass or conflicting knowledge stays unresolved |
| [25 Scientific Discovery](../agents/25-scientific-discovery/SPEC.md) | Planted corpus gap, falsifiable hypothesis, virtual experiment, measurement feedback | Missing corpus coverage cannot establish novelty; zero measurements are valid |
| [26 Financial Advisory](../agents/26-financial-advisory/SPEC.md) | Fictional prices/profile, risk metrics, one simulated revision, review gate | Missing/stale data cannot default to low risk or release a proposal |
| [27 Legal Intelligence](../agents/27-legal-intelligence/SPEC.md) | Fictional authority retrieval, memo, citation and applicability verification | Missing, superseded, wrong-jurisdiction, or empty citations prevent release |
| [28 Education Intelligence](../agents/28-education-intelligence/SPEC.md) | Prerequisite graph, Bayesian Knowledge Tracing, hints, injected review clock | Missing evidence leaves mastery unchanged; cycles and impossible updates fail |
| [29 Collective Intelligence](../agents/29-collective-intelligence/SPEC.md) | Independent initial proposals, cross-review, bounded synthesis with dissent | Missing reviews, ties, or exhausted budget cannot become claimed consensus |
| [30 Embodied Intelligence](../agents/30-embodied-intelligence/SPEC.md) | One-dimensional cart, guarded commands, observed state, bounded replanning | Unsafe or stale commands cannot mutate state; emergency stop overrides work |
| [31 Typed Decision](../agents/31-typed-decision/SPEC.md) | Synthetic categorical probabilities, strict typed decisions, concentration and abstention | Malformed distributions, ties, timeout, and cancellation never become accepted decisions |
| [32 MCP Server Builder](../agents/32-mcp-server-builder/SPEC.md) | Existing restricted OpenAPI contract, constrained proposal, standalone stdio server, gated publication | Invalid mappings, protocol failures, denied egress, and failed verification prevent publication |

## Throughput and ownership

Blocking work is source grounding, contract selection, and the MCP SDK/isolation feasibility gate. The initial checkout contains cases 01–21 and planned cases 31–32; 22–30 are additions based on retained briefs.

Up to three builders work concurrently, each in one exclusively assigned case directory. The parent alone edits the catalogue and this batch document. Reviewers inspect completed, stable case code. Each implementation unit ends with its own checks before readiness is recorded.

Case 32's local feasibility investigation confirmed that the operating system sandbox can permit a fixture port while denying another loopback destination. Running that sandbox requires execution outside the enclosing Codex sandbox. Dependency and protocol compatibility still require actual installed-package checks.

## Qualification

For every case, run its documented tests and actual CLI, then check a case-only copy and installed package where applicable. Independent review checks contracts, authority, source explanations, failure behavior, and evidence. Resolve actionable findings before `demo-ready`. Run `python3 scripts/check_structure.py` and `git diff --check` after catalogue integration.

Record exact successful commands, date, evidence mode, and limits in each README or linked verification record. Fixture, mocked-provider, live-model, real-service, hosted CI, deployment, and production outcomes remain distinct. No live-provider call, real-service connection, deployment, or publication is needed for this selected local scope.

## Delivery record

Implementation and review are in progress. Final per-case status and evidence will be reconciled here and in the root catalogue after qualification.
