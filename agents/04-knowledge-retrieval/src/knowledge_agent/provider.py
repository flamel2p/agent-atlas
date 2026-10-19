from contextlib import contextmanager
from importlib.resources import files
import json
import logging
import os
import re

from .contracts import AgentError, Request, strict_json
from .corpus import Passage


OFFICIAL_BASE_URL = "https://api.openai.com/v1"
TIMEOUT_SECONDS = 20.0
MAX_OUTPUT_TOKENS = 512


@contextmanager
def isolated_sdk_settings():
    # This CLI is synchronous; restore process settings after each SDK operation.
    names = ("OPENAI_LOG", "OPENAI_CUSTOM_HEADERS")
    removed = {name: os.environ.pop(name) for name in names if name in os.environ}
    previous_logging = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        yield
    finally:
        os.environ.update(removed)
        logging.disable(previous_logging)


def selection_schema(candidates: tuple[Passage, ...]) -> dict:
    return {
        "type": "object", "additionalProperties": False,
        "properties": {
            "status": {"type": "string", "enum": ["selected", "abstained"]},
            "passage_ids": {"type": "array", "maxItems": 3,
                            "items": {"type": "string", "enum": [part.id for part in candidates]}},
        },
        "required": ["status", "passage_ids"],
    }


def parse_response(response) -> object:
    try:
        data = response.model_dump(mode="json", warnings=False)
        if not isinstance(data, dict):
            raise AgentError("provider_malformed")
        if data.get("status") != "completed" or data.get("incomplete_details") is not None:
            raise AgentError("provider_incomplete")
        if data.get("error") is not None:
            raise AgentError("provider_error")
        output = data.get("output")
        if not isinstance(output, list) or not 1 <= len(output) <= 16:
            raise AgentError("provider_malformed")
        texts = []
        for item in output:
            if not isinstance(item, dict):
                raise AgentError("provider_malformed")
            if item.get("type") == "reasoning":
                if item.get("status") not in (None, "completed"):
                    raise AgentError("provider_incomplete")
                continue
            if item.get("type") != "message" or item.get("role") != "assistant":
                raise AgentError("provider_malformed")
            if item.get("status") != "completed":
                raise AgentError("provider_incomplete")
            content = item.get("content")
            if not isinstance(content, list) or len(content) != 1:
                raise AgentError("provider_malformed")
            piece = content[0]
            if not isinstance(piece, dict):
                raise AgentError("provider_malformed")
            if piece.get("type") == "refusal":
                raise AgentError("provider_refusal")
            if piece.get("type") != "output_text" or not isinstance(piece.get("text"), str):
                raise AgentError("provider_malformed")
            if not 1 <= len(piece["text"]) <= 4096 or piece.get("annotations") not in (None, []):
                raise AgentError("provider_malformed")
            texts.append(piece["text"])
        if len(texts) != 1:
            raise AgentError("provider_malformed")
        return strict_json(texts[0])
    except AgentError:
        raise
    except (ValueError, TypeError, AttributeError, RecursionError):
        raise AgentError("provider_malformed") from None


class OpenAISelector:
    def __init__(self, client, model: str, instructions: str):
        self.client = client
        self.model = model
        self.instructions = instructions

    def select(self, request: Request, candidates: tuple[Passage, ...]) -> object:
        payload = {
            "question": request.question, "scope": request.scope(),
            "passages": [{"passage_id": part.id, "text": part.text,
                          "title": part.document.title, "revision": part.document.revision,
                          "version": part.document.version,
                          "reviewed_at": part.document.reviewed_at.isoformat()}
                         for part in candidates],
        }
        try:
            with isolated_sdk_settings():
                response = self.client.responses.create(
                    model=self.model, instructions=self.instructions,
                    input=[{"role": "user", "content": json.dumps(payload, ensure_ascii=True)}],
                    text={"format": {"type": "json_schema", "name": "passage_selection",
                                     "strict": True, "schema": selection_schema(candidates)}},
                    tools=[], tool_choice="none", store=False, stream=False, background=False,
                    truncation="disabled", max_output_tokens=MAX_OUTPUT_TOKENS,
                )
                return parse_response(response)
        except AgentError:
            raise
        except Exception:
            raise AgentError("provider_error") from None

    def close(self):
        with isolated_sdk_settings():
            self.client.close()


def preflight_openai(*, environ=None, transport=None) -> OpenAISelector:
    environment = os.environ if environ is None else environ
    api_key, model = environment.get("OPENAI_API_KEY"), environment.get("OPENAI_MODEL")
    if not isinstance(api_key, str) or not re.fullmatch(r"[!-~]{1,512}", api_key):
        raise AgentError("missing_or_invalid_api_key")
    if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", model):
        raise AgentError("missing_or_invalid_model")
    try:
        with isolated_sdk_settings():
            import httpx2
            from openai import OpenAI

            instructions = files("knowledge_agent").joinpath("resources/selector.txt").read_text(encoding="utf-8")
            http_client = httpx2.Client(transport=transport, trust_env=False,
                                       follow_redirects=False, timeout=TIMEOUT_SECONDS)
            try:
                client = OpenAI(
                    api_key=api_key, base_url=OFFICIAL_BASE_URL, max_retries=0,
                    timeout=TIMEOUT_SECONDS, http_client=http_client,
                    organization="", project="", admin_api_key="", webhook_secret="",
                )
            except BaseException:
                http_client.close()
                raise
    except ImportError:
        raise AgentError("sdk_unavailable") from None
    except Exception:
        raise AgentError("provider_configuration_error") from None
    return OpenAISelector(client, model, instructions)
