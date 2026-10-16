from dataclasses import dataclass, field
import re
from typing import Any, Literal


MODEL = "gpt-6-luna"
DATASET_ID = "campaign-demo-v1"
MAX_RESPONSES = 6
MAX_TOOL_ATTEMPTS = 5
REQUEST_SECONDS = 30.0
RUN_SECONDS = 120.0


@dataclass(frozen=True)
class RunConfig:
    mode: Literal["replay", "live"] = "replay"
    task: str = "Compare total revenue by channel"
    output_format: Literal["table", "bar"] = "bar"
    example: str | None = "revenue-by-channel-bar"


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: str
    call_id: str


@dataclass(frozen=True)
class Decision:
    calls: tuple[ToolCall, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


MESSAGES = {
    "invalid_input": "The command does not match the supported input contract.",
    "missing_credentials": "Live mode requires OPENAI_API_KEY.",
    "invalid_dataset": "The bundled dataset failed validation.",
    "invalid_tool_call": "The proposed tool call is not permitted or is malformed.",
    "invalid_tool_result": "A tool result failed validation.",
    "invalid_state": "The operation is invalid for the current run state.",
    "provider_error": "The provider request failed.",
    "provider_refusal": "The provider declined the request.",
    "provider_timeout": "The provider request exceeded its deadline.",
    "incomplete_result": "The run ended without all required results.",
    "limit_reached": "The run exceeded an execution limit.",
    "artifact_error": "The run could not safely create or publish its artifacts.",
    "cancelled": "The run was interrupted.",
}


class Failure(Exception):
    def __init__(
        self,
        code: str,
        *,
        status: str = "failed",
        phase: str = "execution",
        request_id: str | None = None,
        http_status: int | None = None,
    ):
        if code not in MESSAGES:
            raise ValueError("Unknown failure code")
        super().__init__(MESSAGES[code])
        self.code = code
        self.status = status
        self.phase = phase
        self.request_id = request_id if isinstance(request_id, str) and re.fullmatch(r"req_[A-Za-z0-9_-]{1,100}", request_id) else None
        self.http_status = http_status if type(http_status) is int and 100 <= http_status <= 599 else None

    def as_dict(self) -> dict[str, Any]:
        result = {"code": self.code, "phase": self.phase, "message": MESSAGES[self.code]}
        if self.request_id is not None:
            result["request_id"] = self.request_id
        if self.http_status is not None:
            result["http_status"] = self.http_status
        return result
