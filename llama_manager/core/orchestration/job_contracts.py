from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ChatMessage(BaseModel):
    role: str
    content: str | list[dict[str, object]]


class JobRequirements(BaseModel):
    labels: dict[str, Any] = Field(default_factory=dict)
    capacity: dict[str, Any] = Field(default_factory=dict)


class LlmGenerateJobPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str = Field(min_length=1)
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
    requirements: JobRequirements | None = None

    @model_validator(mode="after")
    def normalize_fields(self) -> "LlmGenerateJobPayload":
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


def validate_job_payload(job_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    if job_type != "llm.generate":
        return payload
    return LlmGenerateJobPayload.model_validate(payload).model_dump(mode="json", exclude_none=True)


def chat_payload_from_llm_generate(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    parsed = LlmGenerateJobPayload.model_validate(payload)
    data = parsed.model_dump(mode="json", exclude_none=True)
    model = data.pop("model")
    data.pop("requirements", None)
    return model, data
