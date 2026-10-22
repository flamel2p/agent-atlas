"""Public boundary. Validation and the finite scope gate run before store creation.

Store injection exists for testing the bypass guarantee. It grants no user-facing
path, tool, model, or composer option. Forget is an explicit administrative action
within one local user namespace and never creates a conversational memory turn.
"""

from typing import Callable

from .dialogue import parse
from .domain import TurnRequest, TurnResult, terminal, valid_label, valid_request
from .store import Store


class Conversation:
    def __init__(self, workspace: str = "demo", *, store_factory: Callable[[], Store] | None = None):
        self.workspace = workspace
        self.store_factory = store_factory or (lambda: Store(workspace))

    def turn(self, request: TurnRequest) -> TurnResult:
        if not valid_label(self.workspace) or not isinstance(request, TurnRequest) or not valid_request(request):
            return terminal("invalid_input", "Course guide: Use valid labels and a nonempty message of at most 500 characters without controls.",
                            "gate:invalid", "compose:skipped", "persistence:not_accessed")
        intent = parse(request.text)
        if intent is None:
            return terminal("out_of_scope", "Course guide: I can help with the synthetic course catalogue. Use help for supported requests.",
                            "gate:blocked", "compose:skipped", "persistence:not_accessed")
        try:
            return self.store_factory().turn(request, intent)
        except Exception:
            return terminal("storage_error", "Course guide: Local state could not be processed. No dialogue changes were committed.",
                            "gate:passed", "context:not_loaded", "compose:skipped", "persistence:rolled_back")

    def forget(self, user_id: str) -> TurnResult:
        if not valid_label(self.workspace) or not valid_label(user_id):
            return terminal("invalid_input", "Course guide: Use valid workspace and user labels.", "persistence:not_accessed")
        try:
            return self.store_factory().forget(user_id)
        except Exception:
            return terminal("storage_error", "Course guide: Local state could not be processed. No dialogue changes were committed.",
                            "persistence:rolled_back")
