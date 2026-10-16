# Document Intelligence agents

**Source:** Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026; Chapter 6, “Information Retrieval and Knowledge Agents,” “Document Intelligence agents.” **Reference ID:** 05; singular reference alias: Document Intelligence agent. **Locators:** printed pages and 1-based physical PDF pages. **Status:** Source analysis; no implementation or runtime validation performed.

## Purpose, boundaries, inputs and outputs

This pattern converts visually complex, unstructured business documents into schema-conforming data for operational users. Inputs include scanned PDFs/images, structured files, email content, and a target extraction schema. Outputs should contain field values, confidence, and provenance, with validated records passed to downstream systems or uncertain fields reviewed by humans. The book’s 95% field accuracy and under-8% human-review figures are illustrative lifecycle targets requiring annotated evaluation data; they are not measured results for the example.

## Source architecture

A central cognition core coordinates classification/triage, preprocessing and OCR, layout segmentation, information extraction, and validation/integration. MIME detection and lightweight classification select workflows; OCR supplies words and confidence; layout recovers reading order, blocks, tables, and key/value relationships; extraction maps these into a schema. Validators enforce business rules and confidence routes determine automatic integration versus human review. ERP/CRM connectors are conceptual dependencies. Provenance should retain page, bounding box, and token indices. Intermediate document/token state is implied; persistent memory is not specified.

## Input-to-output flow

1. Detect document type/language and choose a template or processing path; structured inputs can skip OCR.
2. Improve image quality, then OCR image-based pages while retaining uncertainty.
3. Segment layout and reconstruct relevant structural relationships.
4. Extract schema fields with confidence and source locations.
5. Validate values/business constraints; send sufficiently confident results downstream, or use cascading extraction/re-OCR/alternative models and human correction where uncertain.
6. Use review feedback for later improvement.

The source describes these recovery branches conceptually; the sample does not implement the full routing or review loop.

## Source implementation and evidence

Concrete Python examples use pytesseract, pdf2image, Pillow, dataclasses, and rapidfuzz; Tesseract is a system prerequisite. The narrow invoice example extracts invoice number, date, and total through OCR word positions, line grouping, fuzzy cue matching, same-line values, and a next-line fallback. It merges the first nonempty field found across pages. There is no LLM orchestration or production integration in that example. No pinned package/model versions are supplied.

The simpler OCR stub drops low-confidence words while its comment says they are flagged for review; no separate review record is returned. The longer example retains token geometry internally but returns strings without confidence or field provenance. Its next-line fallback does not visibly enforce the same-column restriction described in its commentary. Thus the code is a heuristic exercise, not evidence that the complete architecture is implemented.

## Failures, constraints and recovery

Skew, noise, handwriting, unfamiliar layouts, OCR uncertainty, and invalid fields can break extraction. The chapter recommends representative labeled datasets, cascading methods, hybrid rules/ML validators, HITL from the outset, and full provenance. Exact confidence calibration, conflict resolution across pages, and field-review UI are unspecified.

## Proposed minimal demo — implementation proposal

Extract three fields from synthetic invoices with known values and retained page/bounding-box provenance. **Normal check:** a clean invoice produces the expected fields and source regions. **Limit check:** an ambiguous total or degraded scan routes the affected field for review instead of silently choosing a value. These are proposed acceptance checks only.

## Missing decisions

Choose document family, schema, supported languages/layouts, native-PDF versus OCR handling, confidence policy, fixtures, review interface, and whether to use the book’s heuristic or a stronger extractor later.

## Supporting source locations

- Ch. 6, purpose/five-stage architecture: printed 153–155; PDF 184–186.
- Ch. 6, OCR/layout-aware example: printed 154–158; PDF 185–189.
- Ch. 6, pipeline targets/operations/best practices: printed 159–160; PDF 190–191.
