from __future__ import annotations

import os

from langchain_openai import ChatOpenAI

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:  # pragma: no cover
    ChatGoogleGenerativeAI = None

DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    raise RuntimeError(
        f"Missing required environment variable: {name}. "
        "See .env.example for the expected configuration."
    )


def get_openai_lm(
    temperature: float = 0,
    thinking: str = "disabled",
    reasoning_effort: str = "high",
) -> ChatOpenAI:
    api_key = _require_env("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL).strip() or DEFAULT_OPENAI_MODEL
    base_url = os.getenv("OPENAI_BASE_URL", "").strip()

    client_kwargs = {
        "api_key": api_key,
        "model": model,
        "seed": 42,
        "temperature": temperature,
    }
    if base_url:
        client_kwargs["base_url"] = base_url

    if thinking == "enabled":
        client_kwargs["extra_body"] = {"thinking": {"type": thinking}}
        client_kwargs["reasoning_effort"] = reasoning_effort

    return ChatOpenAI(**client_kwargs)


def get_gemini_lm(
    model: str = DEFAULT_GEMINI_MODEL,
    temperature: float = 0,
) -> "ChatGoogleGenerativeAI":
    if ChatGoogleGenerativeAI is None:
        raise ImportError(
            "langchain_google_genai is not installed. "
            "Install the optional dependency before using Gemini."
        )

    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=_require_env("GOOGLE_API_KEY"),
        seed=42,
        temperature=temperature,
    )


__all__ = ["get_openai_lm", "get_gemini_lm"]
