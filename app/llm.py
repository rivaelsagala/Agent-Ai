"""LLM client factory.

The LLM is accessed through OpenRouter's OpenAI-compatible endpoint so any
OpenAI-family model can be selected via the ``LLM_MODEL`` env var.
"""
from functools import lru_cache
from typing import Optional

from langchain_openai import ChatOpenAI

from app.config import settings


@lru_cache(maxsize=1)
def get_llm(temperature: Optional[float] = None, streaming: bool = False) -> ChatOpenAI:
    """Return a chat model pointed at OpenRouter."""
    return ChatOpenAI(
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE if temperature is None else temperature,
        api_key=settings.OPENROUTER_API_KEY or "EMPTY",
        base_url=settings.OPENROUTER_BASE_URL,
        timeout=settings.HTTP_TIMEOUT,
        streaming=streaming,
        default_headers={
            "HTTP-Referer": "https://atlas-ai.local",
            "X-Title": "Atlas AI",
        },
    )
