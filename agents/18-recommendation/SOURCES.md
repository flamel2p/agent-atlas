# Source evidence and implementation provenance

Reviewed on 2026-10-23. This is an independent project extension for reference 18. The retained [inventory](../../agent-library-analysis/agent-inventory.md), [foundations](../../agent-library-analysis/foundations.md), and [source brief](../../agent-library-analysis/agents/18-recommendation.md) inform scope. They are source analysis, not runtime evidence.

## Book boundary

The retained analysis of Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026 records a recommendation synopsis in the Preface at printed xxiii / PDF 24 and a teaser at printed 283 / PDF 314. It records no developed standalone recommendation section in the Chapter 10 body at printed 281-306 / PDF 312-337. Those are retained-analysis locators. The purchased book was not re-audited during this build.

The implementation therefore makes no claim to reproduce a book architecture, hybrid recommender, dedicated code sample, or measured source result. The synthetic exercise scenario, ranking equation, constraints, baseline, and checks are selected project decisions.

## Independently verified primary guidance

- [Google content-based filtering](https://developers.google.com/machine-learning/recommendation/content-based/basics) supports hand-engineered item features, explicit user preferences in the same feature space, and dot-product similarity. It does not require other-user data. The demo uses weighted topic overlap as its own small instance of this approach.
- [Google recommendation architecture overview](https://developers.google.com/machine-learning/recommendation/overview/types) describes candidate generation, scoring, and re-ranking as a common architecture. This small catalogue can inspect every item and enforce constraints before scoring.
- [Google re-ranking](https://developers.google.com/machine-learning/recommendation/dnn/re-ranking) discusses metadata filtering and policy adjustments. The exact constraints selected here remain project decisions.
- [Google content-based limitations](https://developers.google.com/machine-learning/recommendation/content-based/summary) describes feature-engineering dependence and limited expansion beyond existing interests. Passing synthetic checks cannot establish learning outcomes or recommendation quality for real learners.
- [Google collaborative filtering](https://developers.google.com/machine-learning/recommendation/collaborative/basics) uses cross-user preference structure. This demo has none and does not claim collaborative or hybrid recommendation.
- [Hatch build configuration](https://hatch.pypa.io/latest/config/build/) documents build-system and package selection. The selected case-local build backend is pinned Hatchling 1.32.4, verified available in the local build cache. No runtime dependency is needed.

No third-party sample code or dataset is copied. Exercise records are original synthetic fixtures. The repository MIT notice is preserved in the case distribution.

## Evidence limits

Topic scores express the selected similarity rule. They are not confidence, probability, predicted completion, or user satisfaction. Explicit preference changes are input personalization, not model training. Fixture checks, standalone installation, wheel execution, and code review will be recorded separately from any live-model, CI, or deployment evidence.
