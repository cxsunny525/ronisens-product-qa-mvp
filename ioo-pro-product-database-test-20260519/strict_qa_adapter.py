from __future__ import annotations

import qa_engine


def answer_question(question: str) -> dict[str, Any]:
    return qa_engine.answer_question(question, mode="strict")
