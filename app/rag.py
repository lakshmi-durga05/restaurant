from __future__ import annotations
from typing import List, Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from . import reservation_service
from .config import settings


def _build_corpus(db) -> tuple[list[str], list[str]]:
    docs: list[str] = []
    titles: list[str] = []

    # Menu items
    try:
        menu = reservation_service.get_menu(db)
        for m in menu:
            doc = f"menu item: {m.name}. description: {getattr(m, 'description', '')}. price: {getattr(m, 'price', '')}"
            docs.append(doc)
            titles.append(m.name)
    except Exception:
        pass

    # Views
    try:
        views = reservation_service.get_all_views(db)
        for v in views:
            docs.append(f"view: {v}. seating with {v} ambiance. good for different party sizes.")
            titles.append(f"view:{v}")
    except Exception:
        pass

    # FAQs
    faqs = [
        ("hours", "We are open daily 12:00-23:00. Lunch 12:00–15:30. Dinner 18:30–23:00."),
        ("address", "123 Serene Lake Drive, Lakeside District, Bangalore, Karnataka 560001, India."),
        ("booking", "Provide name, party size, date, time and at least one contact (email or phone)."),
        ("preorder", "You can add dishes anytime. After booking, they attach to your reservation."),
    ]
    for title, content in faqs:
        docs.append(f"faq {title}: {content}")
        titles.append(f"faq:{title}")

    return docs, titles


def retrieve_answers(db, query: str, top_k: Optional[int] = None) -> List[str]:
    if not settings.use_rag:
        return []
    docs, _ = _build_corpus(db)
    if not docs:
        return []
    k = top_k or settings.rag_top_k
    vect = TfidfVectorizer(stop_words="english")
    X = vect.fit_transform(docs)
    qv = vect.transform([query])
    sims = cosine_similarity(qv, X).ravel()
    idx = sims.argsort()[::-1][:k]
    return [docs[i] for i in idx if sims[i] > 0]


def answer(db, query: str) -> Optional[str]:
    from .llm import ask_ollama

    ctxs = retrieve_answers(db, query)
    if not ctxs:
        return None
    context = "\n".join(ctxs)
    # If Ollama enabled, let it compose a friendly answer
    reply = ask_ollama(
        prompt=f"Context information:\n{context}\n\nQuestion: {query}\nAnswer in 1-3 short sentences.",
        system="You are a helpful restaurant assistant for Lake Serinity.",
    )
    if reply:
        return reply
    # Otherwise, return the top context as a basic answer
    return ctxs[0]
