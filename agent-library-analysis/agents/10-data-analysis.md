# The Data Analysis agent

**Source:** Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026; Chapter 8, “Data Analysis and Reasoning Agents,” “The Data Analysis agent.” **Reference ID:** 10. **Locators:** printed pages; 1-based physical PDF pages. **Status:** Source analysis; no implementation or runtime validation performed.

## Purpose, boundaries, inputs and outputs

The pattern lets a user explore data conversationally, translating analytical questions into reproducible computations and explanations. Inputs are a question, dataset/schema, temporal scope, and follow-up refinements. Outputs are numerical summaries, appropriate charts, statistical interpretation, and uncertainty/anomaly observations. Success requires accurate computation and understandable, evidence-based presentation. The source frames the agent as decision support; reported correlation or fitted-model statistics do not establish causal effects.

## Source architecture

An LLM Reasoning Core interprets intent and plans analysis. A Code Interpreter executes Python/SQL against CSV, database, or warehouse data. A Visualization Engine considers intent and schema; a statistical layer computes descriptive summaries, inference/regression, outliers, and uncertainty. Presentation reconnects to user feedback. RAG and statistical validation are possible contextual safeguards, not mandatory implemented components. User preferences may inform future chart selection; no persistent preference-store schema or learning implementation is supplied.

## Input-to-output flow

1. Parse analytical intent, metric, relevant fields, and temporal filters.
2. Form an explicit computation plan.
3. Generate and execute analytical operations against the dataset.
4. Examine results and variable types; select a line chart for time, bar chart for category comparison, or scatter/table for relationships/other cases.
5. Compute relevant descriptive/inferential statistics and examine anomalies or incomplete/skewed data.
6. Present visuals and a concise interpretation, including confidence where available.
7. Refine through follow-up queries; reactivate the loop with narrower scope or segmentation.

The chapter suggests mitigation such as interpolation, normalization, or robust scaling for problematic data. It does not specify an automatic permission policy for changing data, a complete ambiguity-resolution loop, or a stopping budget beyond the user interaction.

## Source implementation and evidence

The section provides illustrative snippets: keyword-based visualization recommendation, pandas summaries/correlation, Statsmodels OLS regression, and a z-score outlier filter. It is not a standalone end-to-end agent. Python/SQL, pandas, NumPy, and Statsmodels are named computation choices; Altair, Plotly, Matplotlib, AutoViz, and DataPrep.EDA are visualization options. No exact provider/model or pinned package versions are supplied here. Chapter 7’s more concrete CSV plotting assistant is a related tool-use example, not a complete implementation of Chapter 8’s statistical reasoning architecture.

## Failures, constraints and recovery

The source identifies ambiguous queries, expanding chart palettes, incomplete/skewed data, anomalies, and uncertain patterns. It suggests confidence scoring or LLM intent classification and user refinement. The keyword recommendation function accepts a DataFrame but does not inspect it, so it does not demonstrate the schema-aware branching described by the architecture. Example narrative claims such as explained revenue variance are illustrative outputs without a supplied dataset/evaluation. The chapter does not implement an execution sandbox, statistical-assumption checker, or causal-identification procedure.

## Proposed minimal demo — implementation proposal

Analyze synthetic quarterly product activity with fixed supported aggregations and chart choices. **Normal check:** a top-three-products request matches independently calculated totals and outputs the expected category chart. **Limit check:** an absent metric or invalid temporal field asks for clarification instead of running an invented analysis. These acceptance checks are proposals only.

## Missing decisions

Choose allowed computations, execution isolation, schema validation, temporal conventions, chart rules, statistical assumptions, missing-data policy, and response provenance. Decide whether free-form generated code belongs in the first demo.

## Supporting source locations

- Ch. 8, cognitive loop/components: printed 204–206; PDF 235–237.
- Ch. 8, visualization architecture/rule snippet/options: printed 206–209; PDF 237–240.
- Ch. 8, statistical snippets/uncertainty: printed 209–211; PDF 240–242.
- Ch. 8, combined pipeline sketch: printed 231–232; PDF 262–263.
