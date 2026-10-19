from .contracts import Scenario, WORKERS

EXAMPLES = ("normal", "reviewer-unavailable", "no-reviewer", "deadline", "task-failure")


def load_example(name: str) -> Scenario:
    if name not in EXAMPLES:
        raise ValueError("unknown example")
    data = {
        "objective": "Prepare a synthetic documentation release with examples and two reviews.",
        "availability": {worker: True for worker in WORKERS},
        "deadline": 20,
        "events": [],
        "fail_task": None,
    }
    if name == "reviewer-unavailable":
        data["events"] = [{"after_task": "draft", "worker": "reviewer-primary", "available": False}]
    elif name == "no-reviewer":
        data["events"] = [{"after_task": "draft", "worker": worker, "available": False}
                          for worker in ("reviewer-primary", "reviewer-backup")]
    elif name == "deadline":
        data["deadline"] = 4
    elif name == "task-failure":
        data["fail_task"] = "technical-review"
    return Scenario.model_validate(data)
