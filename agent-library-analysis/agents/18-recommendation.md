# Recommendation agent — source gap for reference 18

**Source checked:** Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026; Chapter 10, “Conversational and Content Creation Agents,” its full chapter body, contents, Preface, and full-text mentions. **Reference ID:** 18 (reference inventory identifier, not a proven PDF ordering). **Title status:** “Recommendation agent” is a reference alias; there is no verified standalone chapter-body heading for this pattern in this PDF. **Locators:** printed pages; physical PDF pages are 1-based. **Status:** Source analysis; no implementation or runtime validation performed.

## Purpose, boundaries, inputs and outputs

The Preface says Chapter 10 covers recommendation agents using hybrid recommender architectures. Chapter 10 briefly foreshadows recommendation agents, but its introduction, actual sections, and summary cover Conversational and Content Creation agents. No standalone recommendation purpose, intended user, input/output contract, or success criteria can therefore be attributed to a substantive agent treatment in this edition.

The Data Analysis agent’s visualization recommendation subsystem is a different, narrower concept. Generic mentions of personalized recommendations and the later Financial Advisory agent also do not establish the missing independent pattern.

## Source architecture

**Text-supported:** the Preface supplies the phrase “hybrid recommender architectures” as a chapter synopsis; the conversational discussion supplies a future-section teaser.

**Unspecified:** recommendation components, candidate retrieval/ranking, personalization method, feedback/memory, cold-start behavior, external dependencies, and evaluation. It would be inference to fill these with a conventional recommendation-system architecture and present that as book content. This brief deliberately leaves that source boundary visible.

## Input-to-output flow

No independently supported recommendation-agent sequence is provided. A flow cannot be reconstructed from the synopsis alone. Visualization-type selection in Chapter 8 remains documented within reference 10, rather than being reassigned here to make the reference count match.

## Source implementation and evidence

No dedicated recommendation-agent code, model, framework, prerequisite, or evaluation was located in the chapter body. Chapter 10’s technical requirements support its two demonstrated patterns; they should not be treated as proven prerequisites for an absent third pattern. The separately labeled official-repository reference can motivate a future comparison, but it cannot replace missing PDF content or prove an implementation exists here.

## Failures, constraints and recovery

The key constraint is missing substantive source coverage. The PDF does not establish this pattern’s failure modes or recovery. The discrepancy should remain explicit in a future public collection so users can distinguish book-derived demos from additions.

## Proposed minimal demo — implementation proposal

**Optional independent extension requiring later review:** recommend synthetic learning exercises from explicit topic preferences and item tags, with an inspectable scoring explanation. **Normal check:** preferred-topic items rank above unrelated items. **Limit check:** a new user receives a labeled non-personalized baseline or is asked for preferences. This proposal is not extracted from the book, approved implementation scope, or validation performed. An independently sourced design would be needed before describing it as a hybrid recommender.

## Missing decisions

Decide whether to keep reference 18 as an unresolved slot, request corrected/additional source material, or authorize a separately sourced independent demo. Choose the recommendation goal, users, data/license, personalization/evaluation policy, and provenance labeling only after that decision.

## Supporting source locations

- Preface, Chapter 10 synopsis: printed xxiii; PDF 24.
- Table of Contents, Chapter 10 sections: printed xvi; PDF 17.
- Ch. 10, introduction/two-pattern topic list: printed 281; PDF 312.
- Ch. 10, recommendation teaser: printed 283; PDF 314.
- Ch. 10, actual Content Creation section and two-pattern summary: printed 293 and 305–306; PDF 324 and 336–337.
- Ch. 8, distinct visualization recommendation subsystem: printed 206–209; PDF 237–240.
