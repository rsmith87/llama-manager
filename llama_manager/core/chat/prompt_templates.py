from __future__ import annotations

from typing import Any
from collections.abc import Callable


TemplateHandler = Callable[[str, dict[str, Any], dict[str, Any]], dict[str, Any]]


def _chat_template_handler(chat_template_name: str) -> TemplateHandler:
    def _handler(model_name: str, request_payload: dict[str, Any], request_body: dict[str, Any]) -> dict[str, Any]:
        request_payload["chat_template"] = chat_template_name
        return request_payload
    return _handler


class PromptTemplateAdapter:
    def __init__(self, registry: dict[str, TemplateHandler] | None = None):
        default_registry: dict[str, TemplateHandler] = {
            "llama3": _chat_template_handler("llama3"),
            "llama-3": _chat_template_handler("llama3"),
            "chatml": _chat_template_handler("chatml"),
            "qwen": _chat_template_handler("chatml"),
            "gemma": _chat_template_handler("gemma"),
            "gpt-oss": _chat_template_handler("chatml"),
            "gptoss": _chat_template_handler("chatml"),
        }
        self._registry = registry or default_registry

    def apply(self, model_name: str, model_template: str | None, request_payload: dict[str, Any], request_body: dict[str, Any]) -> dict[str, Any]:
        template = (model_template or "").strip().lower()
        if not template:
            return request_payload
        handler = self._registry.get(template)
        if handler is None:
            return request_payload
        return handler(model_name, request_payload, request_body)
