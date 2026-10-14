"""Offline stand-ins for Mistral models. Tests never call real APIs."""

import hashlib
import math
import re
from collections.abc import AsyncIterator, Iterator
from typing import Any

from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.runnables import Runnable, RunnableLambda
from pydantic import BaseModel, Field


class FakeChatModel(BaseChatModel):
    """Returns preset Pydantic objects for structured output and preset text otherwise.

    `structured` maps a schema class to one object or a list consumed in order
    (the last one repeats). `calls` records every input for assertions.
    """

    text: str = "fake answer"
    structured: dict[type[BaseModel], BaseModel | list[BaseModel]] = Field(default_factory=dict)
    calls: list[Any] = Field(default_factory=list)
    structured_calls: list[tuple[type[BaseModel], Any]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "fake-chat"

    def with_structured_output(
        self, schema: dict[str, Any] | type, *, include_raw: bool = False, **kwargs: Any
    ) -> Runnable[LanguageModelInput, dict[str, Any] | BaseModel]:
        if not (isinstance(schema, type) and issubclass(schema, BaseModel)):
            raise TypeError("FakeChatModel only supports Pydantic schemas")

        def _respond(inp: Any) -> BaseModel:
            self.structured_calls.append((schema, inp))
            return self._next_structured(schema)

        return RunnableLambda(_respond)

    def _next_structured(self, schema: type[BaseModel]) -> BaseModel:
        if schema not in self.structured:
            raise KeyError(f"No preset structured output for {schema.__name__}")
        preset = self.structured[schema]
        if isinstance(preset, list):
            return preset.pop(0) if len(preset) > 1 else preset[0]
        return preset

    def _tokens(self) -> list[str]:
        return re.findall(r"\S+\s*", self.text) or [self.text]

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.calls.append(messages)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self.text))])

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        self.calls.append(messages)
        for tok in self._tokens():
            yield ChatGenerationChunk(message=AIMessageChunk(content=tok))

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        self.calls.append(messages)
        for tok in self._tokens():
            chunk = ChatGenerationChunk(message=AIMessageChunk(content=tok))
            if run_manager:
                await run_manager.on_llm_new_token(tok, chunk=chunk)
            yield chunk


class FakeEmbedder(Embeddings):
    """Deterministic hashed bag-of-words vectors (dim 64, unit length).

    Texts sharing words get similar vectors, so retrieval tests behave sensibly.
    """

    def __init__(self, dim: int = 64) -> None:
        self.dim = dim
        self.calls = 0  # number of embed requests
        self.texts_embedded = 0

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        for word in re.findall(r"\w+", text.lower()):
            h = hashlib.sha256(word.encode()).digest()
            idx = int.from_bytes(h[:4], "big") % self.dim
            v[idx] += 1.0 if h[4] % 2 == 0 else -1.0
        norm = math.sqrt(sum(x * x for x in v))
        if norm == 0:
            v[0], norm = 1.0, 1.0
        return [x / norm for x in v]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        self.texts_embedded += len(texts)
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.embed_documents(texts)

    async def aembed_query(self, text: str) -> list[float]:
        return self.embed_query(text)
