from __future__ import annotations
import requests
from typing import Optional

from .config import settings

OLLAMA_URL = "http://localhost:11434/api/generate"


def _ask_via_langchain(full_prompt: str, max_tokens: int) -> Optional[str]:
    """Try LangChain's Ollama wrapper if installed; return None if unavailable/errors."""
    try:
        # Lazy import to avoid hard dependency
        from langchain_community.llms import Ollama as LC_Ollama

        llm = LC_Ollama(model=settings.ollama_model, num_predict=max_tokens)
        # LangChain uses .invoke for a single call
        out = llm.invoke(full_prompt)
        if isinstance(out, str):
            return out
        # Some wrappers may return objects; cast to str
        return str(out)
    except Exception:
        return None


def _ask_via_rest(full_prompt: str, max_tokens: int) -> Optional[str]:
    try:
        payload = {
            "model": settings.ollama_model,
            "prompt": full_prompt,
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
        resp = requests.post(OLLAMA_URL, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response")
    except Exception:
        return None


def ask_ollama(prompt: str, system: Optional[str] = None, max_tokens: int = 512) -> Optional[str]:
    """Call local Ollama only if enabled. Prefer LangChain adapter if available; fallback to REST.

    Returns None on error/disabled.
    """
    if not settings.use_ollama:
        return None

    full_prompt = (system + "\n\n" if system else "") + prompt

    # Try LangChain adapter first
    out = _ask_via_langchain(full_prompt, max_tokens)
    if out:
        return out

    # Fallback to REST
    return _ask_via_rest(full_prompt, max_tokens)
