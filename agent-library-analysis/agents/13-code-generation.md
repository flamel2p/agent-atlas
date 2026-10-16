# Code-Generation agents

**Source:** Imran Ahmad, *30 Agents Every AI Engineer Must Build*, Packt, March 2026; Chapter 9, “Software Development Agents,” “Code-Generation agents.” **Reference ID:** 13; singular reference alias: Code Generation agent. **Locators:** printed pages; 1-based physical PDF pages. **Status:** Source analysis; no implementation or runtime validation performed.

## Purpose, boundaries, inputs and outputs

The pattern turns a feature specification and repository context into implementation artifacts verified against executable tests. Intended users are developers/teams seeking bounded code generation. Inputs include requirements, conventions, existing APIs, tests, and failure output. Outputs are source/tests, iteration traces, and a completion report. Success is passing the required checks while respecting project context; tests establish checked behavior, not universal correctness or production readiness. The chapter’s conditional-autonomy definition reserves production-branch merging for human approval.

## Source architecture

An orchestrator delegates to tester, developer, and refactoring roles. TDG describes red → green → refactor, using failing tests as specification and test output as feedback. A sandbox/Docker environment executes artifacts. LangGraph state holds tasks, dependencies, code/test snapshots, results, messages, and iterations; Pydantic Task plus TypedDict AgentState provide structure. Redis/PostgreSQL are proposed durable backends. The full-stack extension adds Python/Flask and TypeScript/React specialists, pytest/Jest testing, integration, and RAG for conventions. These are source-supported components; several node implementations and adapters are omitted.

## Input-to-output flow

1. Interpret the feature, define task contracts, and decompose dependencies.
2. Generate tests and demonstrate the missing behavior under the stated TDG pattern.
3. Generate minimal code using repository context.
4. Execute tests in isolation and capture failures/artifacts.
5. Feed original specification, current code, test output, and prior attempts back to the developer until checks pass or a limit is reached.
6. Refactor and rerun checks; integrate component contracts and report results.
7. Seek human review at consequential integration/deployment boundaries.

The shipping walkthrough actually generates code before tests, differing from the earlier test-first description. The full-stack graph uses a three-attempt limit; exhausted failure advances in the shown routing rather than entering an explicit failed state.

## Source implementation and evidence

Python function/tests, state models, a backend-node snippet, and a partial LangGraph workflow illustrate the architecture. Named tools include LangGraph/LangChain, pytest, Jest, Pydantic, Docker, Flask/SQLAlchemy, marshmallow, React/TypeScript, and React Testing Library. CrewAI/AutoGen are alternatives. No exact LLM/model version or complete setup is supplied for this pattern. Reported iteration averages, code quantity, and coverage are book claims without independent execution evidence. Passing a test suite does not imply 100% coverage.

## Failures, constraints and recovery

The source addresses invented APIs, runtime errors, convention violations, lost iteration context, and nonconvergence. Failure traces, context retrieval, bounded loops, sandboxing, checkpoints, and human review are remedies. Important discrepancies remain: the cart-total-100 test expects a discount inconsistent with the supplied `>100` condition; adding negative-weight validation does not fix that boundary. The full-stack graph is sequential despite parallelism claims, the supplied code node does not visibly execute/update test results, and its bare graph compilation supplies no checkpointer despite durability claims. These are unresolved sample limitations, not runtime findings.

## Proposed minimal demo — implementation proposal

Generate one pure synthetic shipping-rule function from an explicit boundary specification, keeping independently reviewed tests fixed during refinement. **Normal check:** one failed implementation is repaired and all boundary assertions pass. **Limit check:** repeated failure reaches the iteration ceiling with artifacts retained and no success label. Proposed checks only.

## Missing decisions

Choose an authoritative specification/test owner, sandbox permissions, provider/version, actual test nodes, failure terminal state, artifact persistence, and human review boundary.

## Supporting source locations

- Ch. 9, autonomy/TDG: printed 238–242; PDF 269–273.
- Ch. 9, shipping walkthrough/state: printed 244–248; PDF 275–279.
- Ch. 9, full-stack nodes/graph/outcome claims: printed 249–255; PDF 280–286.
