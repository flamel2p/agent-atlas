# Compliance-Driven agents

**Source:** Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026; Chapter 9, “Software Development Agents,” exact heading “Compliance-Driven agents.” **Reference ID:** 14. **Alias discrepancy:** the reference list/Preface uses Security-Hardened language; the chapter body teaches compliance enforcement. The filename preserves the assigned reference path and does not imply equivalence. **Locators:** printed pages; 1-based physical PDF pages. **Status:** Source analysis; no implementation or runtime validation performed.

## Purpose, boundaries, inputs and outputs

This pattern helps engineering/security teams assess source and infrastructure changes against organizational or regulatory policy. Inputs are code diffs/configuration, formal rules, retrieved policy context, and reviewer judgments. Outputs are findings, remediation suggestions/patches, CI decisions, and audit records. Success means permissible handling according to defined policies with justified exceptions; this is distinct from functional correctness. The section does not constitute a complete prompt-injection defense architecture or legal compliance certification.

## Source architecture

A policy engine evaluates declarative rules; code/infrastructure analyzers provide AST, configuration, and sensitive-data-flow facts; an LLM interprets ambiguous context and explains/proposes remediation. CI/CD integrates hard/soft outcomes, while HITL handles uncertain findings or exceptions. Versioned policy repositories and external policy-update feeds support evolution; immutable audit records retain findings, interventions, overrides, and policy versions. OPA/Rego, Terraform, Helm, SAST, and GitHub Actions are named mechanisms. The detailed implementation of distributed data-flow tracking, log immutability, and model confidence is unspecified.

## Input-to-output flow

1. Trigger on a pull request or updated change and scan affected artifacts.
2. Evaluate against the active policy version and contextual evidence.
3. Distinguish clear violations from potential false positives; assess severity/certainty.
4. Hard findings fail the CI gate and require remediation; softer ambiguous findings request human clarification.
5. Generate actionable guidance or a candidate patch; rerun relevant checks if a fix is applied.
6. Record decisions and justified overrides in an audit trail.
7. Review new policy information, update versioned rules, and rescan affected changes where required.

The source describes optional automatic fixes based on severity/confidence and human approval alternatives. It does not define a universal automatic-remediation policy or stopping budget.

## Source implementation and evidence

The section provides short Python examples of unsafe logging/hashing and a narrow Rego rule for added lines containing card/log terms without a masking marker. The fintech case describes OPA, static scanning, retrieved compliance context, and GitHub PR integration; it does not supply a complete runnable agent/CI pipeline. No exact model or package versions are specified, and the PCI DSS rule numbering is not tied to an edition. Book-era policy examples need authoritative version review before practical use. The claimed 85% reduction in violations is case-study reporting, not independently verified evidence.

## Failures, constraints and recovery

The source addresses policy ambiguity, contextual violations beyond keyword patterns, sensitive information crossing services, stale regulations, false positives, and unjustified overrides. Proposed remedies include semantic analysis, data-flow tracing, human exceptions with justification, policy versioning/rollback, and reviewed updates. The sample Rego rule is string matching, which does not demonstrate the broader AST/data-flow capabilities. An LLM-generated rule or suggested patch must still be validated; the text leaves that implementation incomplete.

## Proposed minimal demo — implementation proposal

Scan synthetic Python changes against an explicitly local rule forbidding a marked sensitive value in logs. Return evidence and a suggested masking patch without applying it. **Normal check:** a known violation is blocked with the correct line/policy identifier. **Limit check:** an ambiguous field becomes a review item rather than an asserted legal violation. Proposals only.

## Missing decisions

Resolve whether ref14 should demonstrate chapter compliance or a separately sourced security-hardening pattern. Choose policy authority/version, analyzers, model role, override rules, and local-only audit storage.

## Supporting source locations

- Preface, chapter synopsis: printed xxiii; PDF 24.
- Ch. 9, compliance purpose/capabilities: printed 255–258; PDF 286–289.
- Ch. 9, components/policy evolution: printed 259–262; PDF 290–293.
- Ch. 9, fintech case/Rego/CI/outcomes: printed 262–265; PDF 293–296.
