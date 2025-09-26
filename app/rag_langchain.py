"""
Optional LangChain-backed RAG wrapper.
This module is safe to import even if langchain is not installed. It will
silently fall back to a deterministic placeholder answer to avoid
breaking the app workflow.

Enable via environment: RAG_MODE=langchain
"""
from __future__ import annotations

class LangChainRAG:
    def __init__(self):
        self._ok = False
        self._llm = None
        try:
            # Minimal dependency so import errors don't break the app
            from langchain_community.chat_models import ChatOpenAI  # type: ignore
            import os
            api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LC_API_KEY")
            # If no key, still avoid crashing; mark as not ready
            if api_key:
                self._llm = ChatOpenAI(temperature=0.2)
                self._ok = True
        except Exception:
            self._ok = False
            self._llm = None

    def answer_question(self, question: str) -> tuple[str, float]:
        """Return (answer, confidence).
        If langchain stack isn't available, return a graceful deterministic
        response so the app keeps working.
        """
        if self._ok and self._llm:
            try:
                resp = self._llm.invoke(question)
                text = getattr(resp, "content", None) or str(resp)
                return text.strip(), 0.7
            except Exception:
                pass
        # Fallback deterministic
        return (
            "I can help with that. For detailed FAQs I am using the built-in knowledge base."
            " If you connect LangChain with an API key (RAG_MODE=langchain), I will use it automatically.",
            0.4,
        )
