"""
Optional LangChain vector-store RAG using FAISS or Chroma.
Safe to import even if dependencies are missing. If packages or index
are unavailable, it falls back to a deterministic response so the app
workflow remains intact.

Enable via environment:
  RAG_MODE=langchain_faiss   -> FAISS local index
  RAG_MODE=langchain_chroma  -> Chroma local index

Env variables (optional):
  LCVS_PATH      -> path to FAISS index directory
  LCVS_DOCS_PATH -> path to docs directory (for building index if missing)
"""
from __future__ import annotations

import os

class LangChainVectorRAG:
    def __init__(self, backend: str = "faiss"):
        self.backend = backend
        self._ok = False
        self._retriever = None
        try:
            # Lazy imports so absence doesn't break app
            from langchain_community.vectorstores import FAISS, Chroma  # type: ignore
            from langchain.text_splitter import RecursiveCharacterTextSplitter  # type: ignore
            from langchain_community.embeddings import HuggingFaceEmbeddings  # type: ignore
            from langchain_community.llms import OpenAI  # or swap to chat model if desired
            self._emb = HuggingFaceEmbeddings(model_name=os.getenv("LC_EMB_MODEL", "sentence-transformers/all-MiniLM-L6-v2"))
            self._llm = OpenAI(temperature=0.2) if os.getenv("OPENAI_API_KEY") else None

            docs_path = os.getenv("LCVS_DOCS_PATH", "docs")
            vs_path = os.getenv("LCVS_PATH", "vector_store")

            def _load_docs(p):
                texts = []
                try:
                    for root, _, files in os.walk(p):
                        for f in files:
                            if f.lower().endswith((".md", ".txt")):
                                fp = os.path.join(root, f)
                                with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
                                    texts.append((fp, fh.read()))
                except Exception:
                    pass
                return texts

            def _build_index(texts):
                if not texts:
                    return None
                splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)
                docs = []
                for path, content in texts:
                    for chunk in splitter.split_text(content):
                        # store path in metadata
                        docs.append({"page_content": chunk, "metadata": {"source": path}})
                if self.backend == "chroma":
                    return Chroma.from_documents(
                        documents=[d["page_content"] for d in docs],
                        embedding=self._emb,
                        metadatas=[d["metadata"] for d in docs],
                        persist_directory=vs_path,
                    )
                else:
                    return FAISS.from_texts(
                        texts=[d["page_content"] for d in docs],
                        embedding=self._emb,
                    )

            if self.backend == "chroma":
                try:
                    self._vs = Chroma(embedding_function=self._emb, persist_directory=vs_path)
                except Exception:
                    self._vs = None
            else:
                try:
                    self._vs = FAISS.load_local(vs_path, self._emb, allow_dangerous_deserialization=True)
                except Exception:
                    self._vs = None

            if self._vs is None:
                texts = _load_docs(docs_path)
                self._vs = _build_index(texts)
                # Persist FAISS if requested
                try:
                    if self.backend != "chroma" and self._vs is not None:
                        self._vs.save_local(vs_path)
                except Exception:
                    pass

            if self._vs is not None:
                self._retriever = self._vs.as_retriever(search_kwargs={"k": 4})
                self._ok = True
        except Exception:
            self._ok = False
            self._retriever = None
            self._emb = None
            self._llm = None

    def answer_question(self, question: str) -> tuple[str, float]:
        if not self._ok or self._retriever is None:
            return (
                "RAG is running in fallback mode. Connect LangChain and a vector store to enable richer answers.",
                0.4,
            )
        try:
            # Simple retrieve-then-generate
            docs = self._retriever.get_relevant_documents(question)
            context = "\n\n".join([getattr(d, "page_content", str(d)) for d in docs])
            if self._llm is None:
                # Without LLM, return context excerpt
                snippet = (context[:800] + "...") if len(context) > 800 else context
                return (f"Top results from knowledge base:\n\n{snippet}", 0.6)
            prompt = f"Answer the user using only this context if possible.\nContext:\n{context}\n\nQuestion: {question}\nAnswer:"
            ans = self._llm(prompt)
            text = getattr(ans, "strip", None)
            text = text() if callable(text) else str(ans)
            return text.strip(), 0.75
        except Exception:
            return (
                "I couldn't query the vector store right now. Please try again shortly.",
                0.4,
            )
