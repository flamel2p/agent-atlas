"""Synthetic worker results; no documents, external workers, or publication.

The controller decides when a task may finish. This module creates its bounded
result, which the controller validates before recording successful evidence.
"""

from .contracts import WorkerResult


def evidence_id(run_id: str, task_id: str) -> str:
    """Bind simulated evidence to one run/task; this is not cryptographic proof."""

    return f"ev-{run_id}-{task_id}"


class Simulator:
    """The case's only execution capability, limited to simulated task outcomes."""

    def finish(self, task_id: str, worker: str, run_id: str, fail_task: str | None) -> WorkerResult:
        """Apply the scenario's optional failure without fabricating success evidence."""

        failed = task_id == fail_task
        return WorkerResult(task=task_id, worker=worker, status="failed" if failed else "succeeded",
                            evidence=None if failed else evidence_id(run_id, task_id))
