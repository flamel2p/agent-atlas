# 26 - The Financial Advisory agent

- **Source:** Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026; Chapter 14, "Financial and Legal Domain Agents."
- **Reference ID:** 26 from the official publisher repository inventory; exact PDF heading "The Financial Advisory agent."
- **Page convention:** printed page / 1-based physical PDF page.
- **Status:** Source analysis; no implementation or runtime validation performed.

## Purpose and contract

**Explicitly stated:** Structure supervised financial decision support by combining market signals, analysis, client context, risk, and policy checks. The stated aim is to preserve human judgment while automating data-intensive work. Inputs are queries, symbols/market observations, durable client profiles, history, tolerance, horizon, and constraints; outputs are analysis, risk reports, recommendations, compliance findings, and audit traces (pp. 392–407 / PDF 423–438).

**Inference:** Intended users are advisory professionals and supervised clients. Success is traceable analysis with an enforced release gate. **Not specified:** Independently validated investment performance, suitability rules for a particular jurisdiction, or authorization to trade. No proposed demo gives investment advice or executes orders.

## Architecture and documented flow

The initial LangGraph team has market-data, analysis, and news agents around a structured-output supervisor. Later sections add risk assessment, client memory, and a separate compliance/revision graph. The retail case describes five additional roles; these are variants, not one fully wired implementation. Figure 14.1 shows a risk specialist and post-audit finish, whereas the initial routing schema names News and has no risk/compliance node (pp. 393–398 / PDF 424–429, figure visually checked).

1. Append query to message state; supervisor selects a specialist or FINISH.
2. Specialist uses scoped tools, adds its result, and returns control to supervisor.
3. Continue routing until FINISH; no explicit iteration limit is shown.
4. Compute market metrics/risk. The simple quote tool classifies absolute percentage change; a separate `RiskScorer` calculates annualized volatility, drawdown, percentile return, and weighted risk score.
5. Retrieve semantic profile and episodic history; filter accessible profile data and contextualize tolerance/horizon.
6. Generate a recommendation; check risk tolerance and asset concentration.
7. If compliant, deliver/end; otherwise revise and revalidate. This revision loop also has no bound. The retail narrative adds persistent JSON messages and audit reconstruction (pp. 394–407 / PDF 425–438).

Source dependencies are Python 3.10+, LangChain 0.2.16, langgraph 0.2.28, OpenAI 1.40.0, yfinance 0.2.41, finnhub-python 2.4.19, tavily-python 0.3.3, NumPy 1.26.4, Pydantic 2.8.2, python-dotenv 1.0.1, and `gpt-4o-mini-2024-07-18`; API keys are prerequisites (pp. 392–394 / PDF 423–425). These are historical source choices.

## Implementation evidence and constraints

Displayed tools and graph construction are code evidence, but analysis/news wrappers, recommendation/revision functions, policies, persistence, and review operations are incomplete. Exception handlers return ordinary error strings; stale/empty quotes or histories lack typed handling. Defaulting a missing quote change to zero can falsely produce LOW risk. A tool called `portfolio_analysis` merely fetches one symbol's basic metrics; the advertised beta/Sharpe/correlation calculations are not shown (pp. 395–401 / PDF 426–432).

**Inference:** The profile helper filters one object yet returns some fields from the original profile and unfiltered episodes; an access boundary requires redesign. Compliance passes in a sketch do not establish full regulatory compliance. yfinance's production limitations are explicitly discussed; numerical business improvements and retail allocation/return estimates are source-reported illustrations, not independent evidence (pp. 398, 403–408 / PDF 429, 434–439).

## Proposed minimal learning demo - unexecuted

Use fictional symbols, synthetic prices, and an invented profile. Demonstrate graph routing, deterministic risk calculations, and a bounded simulated revision/review gate. All results are educational fixtures.

- **Normal-path acceptance:** A fixture query produces the expected metrics, trace, and policy-passing simulated report.
- **Failure/limit acceptance:** Missing data or persistent policy violation stops at an explicit unresolved/review status; no LOW-risk default, released recommendation, or trade.

**Missing decisions:** Data freshness, risk methodology/units, budget and loop limits, profile permissions, policy authority, review ownership, reproducibility, and audit storage.
