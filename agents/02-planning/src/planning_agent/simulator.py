from .contracts import WorkerResult


def evidence_id(run_id: str, task_id: str) -> str:
    return f"ev-{run_id}-{task_id}"


class Simulator:
    def finish(self, task_id: str, worker: str, run_id: str, fail_task: str | None) -> WorkerResult:
        failed = task_id == fail_task
        return WorkerResult(task=task_id, worker=worker, status="failed" if failed else "succeeded",
                            evidence=None if failed else evidence_id(run_id, task_id))
