import os
from dataclasses import dataclass


def _as_bool(val: str | None, default: bool = False) -> bool:
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass
class Settings:
    use_ollama: bool = _as_bool(os.getenv("USE_OLLAMA"), False)
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    use_rag: bool = _as_bool(os.getenv("USE_RAG"), True)
    rag_top_k: int = int(os.getenv("RAG_TOP_K", "3"))
    # Agentic AI
    use_agents: bool = _as_bool(os.getenv("USE_AGENTS"), False)
    agent_type: str = os.getenv("AGENT_TYPE", "langchain")  # langchain | crewai


settings = Settings()
