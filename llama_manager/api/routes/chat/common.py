from __future__ import annotations

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field, model_validator

from llama_manager.core.chat.proxy import ModelNotRunningError


class ChatMessage(BaseModel):
    role: str
    content: str | list[dict[str, object]]


class ChatRequestBody(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=512, ge=1, le=32768)
    n_predict: int | None = Field(default=None, ge=1, le=32768)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    top_k: int | None = Field(default=None, ge=0)
    min_p: float | None = Field(default=None, ge=0.0, le=1.0)
    repeat_penalty: float | None = Field(default=None, ge=0.0)
    seed: int | None = None
    stop: str | list[str] | None = None
    json_schema: dict[str, object] | None = None
    grammar: str | None = None
    reasoning: bool = False
    target: str = "auto"
    cache_prompt: bool | None = None
    slot_id: int | None = None

    @model_validator(mode="after")
    def normalize_fields(self) -> "ChatRequestBody":
        if self.n_predict is not None:
            self.max_tokens = self.n_predict
        if isinstance(self.stop, str):
            tokens = [item.strip() for item in self.stop.split(",") if item.strip()]
            if not tokens:
                self.stop = None
            elif len(tokens) == 1:
                self.stop = tokens[0]
            else:
                self.stop = tokens
        elif isinstance(self.stop, list):
            tokens = [item.strip() for item in self.stop if isinstance(item, str) and item.strip()]
            self.stop = tokens or None
        if isinstance(self.grammar, str):
            normalized_grammar = self.grammar.strip()
            self.grammar = normalized_grammar or None
        if self.json_schema is not None and self.grammar is not None:
            raise ValueError("json_schema and grammar are mutually exclusive")
        return self


class EmbeddingsRequestBody(BaseModel):
    input: str | list[str]
    target: str = "auto"


class SlotActionRequest(BaseModel):
    target: str = "auto"
    action: str = "clear"


class SessionMessage(BaseModel):
    role: str
    content: str


class SaveChatSessionRequest(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=120)
    model: str = Field(min_length=1, max_length=120)
    target: str = "auto"
    messages: list[SessionMessage] = Field(default_factory=list)
    request_defaults: dict[str, object] = Field(default_factory=dict)


def raise_proxy_http_exception(exc: Exception) -> None:
    if isinstance(exc, KeyError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, ModelNotRunningError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, httpx.HTTPStatusError):
        raise HTTPException(
            status_code=502,
            detail={
                "upstream_status": exc.response.status_code,
                "text": exc.response.text,
            },
        ) from exc
    if isinstance(exc, httpx.HTTPError):
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    raise exc
