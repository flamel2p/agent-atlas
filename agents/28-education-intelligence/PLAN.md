# Education Intelligence implementation plan

[SPEC.md](SPEC.md) owns the approved behavior contract. The parent selected this scope after two independent design passes in the [batch plan](../../docs/AGENTS_22_32_PLAN.md). This case owns only `agents/28-education-intelligence/`. The parent alone updates the root catalogue and makes phased commits.

## Selected implementation

Frozen ObjectiveGraph, LearnerState, AnswerEvidence, BKTParameters, ReviewSchedule, and LearningResult records organize a standard-library domain core. Strict boundary parsing precedes deterministic assessment, observation-then-learning arithmetic, eligibility gates, hint progression, review scheduling, and one terminal report. State is run-scoped and explicitly returned. JSON file reads and stdout writes are the only runtime I/O.

Routine choices are finalized in SPEC.md. The host catalog has count, add, and multiply objectives. One inclusive 0.8 threshold serves mastery and prerequisite gates. Limits are 3 graph nodes, 12 answers, 3 hints, 128 answer characters, 10000 objective attempts, 32768 input bytes, and depth 12. Three consecutive failures stop as teacher_review. Invalid dynamic transitions discard partial run state. A supplied null answer changes no mastery or schedule.

## Implementation sequence and evidence

1. Complete. Finalized exact schema, arithmetic, time semantics, host authority, and stopping rules before code.
2. Complete. Implemented domain records, strict parser, bounded CLI, original packaged fixtures, manifest, and uv lock.
3. Complete. Independently checked rational BKT results and meaningful prerequisites, state, time, limit, failure, and actual CLI process behavior.
4. Complete. Qualification executed 31 tests in each of the source checkout, isolated case-only copy, and installed wheel. Real console and module fixture execution passed outside the repository.
5. Complete. Independent substantive review passed 10,648 rational BKT probes. A real read-only-stdout regression exposed interpreter shutdown exit 120; cleanup now preserves the specified exit 2. Independent fix review, 31-test source/copy/wheel qualification, and readiness reconciliation passed. The parent owns catalogue integration and phased commits.

## Decisions and remaining limits

A deterministic host comparison keeps submitted learner code inert. Supplied state is untrusted history and is never a credential. Illustrative BKT values and fixed review intervals do not demonstrate course efficacy or calibration. No model, network, teacher delivery, database, placement test, persistent learning, or deployment is implemented or required. Cancellation output is covered by an injected boundary interrupt; actual OS signal timing is not qualified.

The qualification script reports actual test counts and runs from temporary directories outside this repository. The parent owns final integration checks. No material contract decision is outstanding.
