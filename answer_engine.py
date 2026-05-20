from __future__ import annotations

from typing import Any

import knowledge_engine
import qa_engine
import verifier


def answer_question(question: str, brand_filter: str | None = None, mode: str = "strict") -> dict[str, Any]:
    """Combine knowledge retrieval with product database QA.

    Knowledge sources explain the inspection or selection logic. Product
    recommendations are always delegated to qa_engine so every model remains
    database-backed and verifiable.
    """
    knowledge = knowledge_engine.retrieve_knowledge_for_question(question, limit=5)
    product_result = verifier.verify_answer(qa_engine.answer_question(question, brand_filter=brand_filter, mode=mode))
    product_rows = product_result.get("matched_products") or []
    knowledge_sources = knowledge.get("sources") or []
    product_sources = product_result.get("sources") or []
    warnings = list(product_result.get("warnings") or [])
    missing = list(product_result.get("missing_or_uncertain") or [])

    if knowledge_sources:
        knowledge_answer = knowledge.get("knowledge_answer") or ""
    else:
        knowledge_answer = (
            "当前知识库还没有可引用的资料；本回答不会编造知识来源。"
            if _is_chinese(question)
            else "No relevant knowledge source is available in the current knowledge base; no source will be invented."
        )
        missing.append("No knowledge source found for this question.")

    if not product_rows:
        missing.append("当前产品库暂无明确候选。" if _is_chinese(question) else "No explicit product candidate is available in the current product database.")
    elif not knowledge_sources:
        warnings.append("Recommendation requires verification because no supporting knowledge source was retrieved.")

    answer = _compose_answer(question, knowledge_answer, product_result, bool(product_rows))
    confidence = _combined_confidence(bool(knowledge_sources), bool(product_rows), product_result.get("confidence"))
    return {
        "answer": answer,
        "knowledge_answer": knowledge_answer,
        "product_recommendations": product_rows,
        "matched_products": product_rows,
        "spec_table": product_result.get("spec_table", []),
        "knowledge_sources": knowledge_sources,
        "product_sources": product_sources,
        "sources": knowledge_sources + product_sources,
        "missing_or_uncertain": list(dict.fromkeys(missing)),
        "confidence": confidence,
        "mode": mode,
        "evidence": product_result.get("evidence", []),
        "match_reason": product_result.get("match_reason", []),
        "query_interpretation": product_result.get("query_interpretation", {}),
        "warnings": list(dict.fromkeys(warnings)),
        "knowledge_cards": knowledge.get("cards", []),
        "knowledge_documents": knowledge.get("documents", []),
        "product_answer": product_result.get("answer", ""),
    }


def _is_chinese(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text or "")


def _compose_answer(question: str, knowledge_answer: str, product_result: dict[str, Any], has_products: bool) -> str:
    product_count = len(product_result.get("matched_products") or [])
    if _is_chinese(question):
        product_note = (
            f"产品库找到 {product_count} 条数据库候选，下面只显示有来源记录的产品。"
            if has_products
            else "当前产品库暂无明确候选；不会用相似型号替代。"
        )
        return f"{knowledge_answer}\n\n{product_note}"
    product_note = (
        f"The product database returned {product_count} database-backed candidate(s)."
        if has_products
        else "The current product database has no explicit candidate; no substitute model is invented."
    )
    return f"{knowledge_answer}\n\n{product_note}"


def _combined_confidence(has_knowledge: bool, has_products: bool, product_confidence: str | None) -> str:
    if has_knowledge and has_products and product_confidence in {"high", "medium"}:
        return "medium"
    if has_knowledge or has_products:
        return "low" if product_confidence == "low" else "medium"
    return "low"


if __name__ == "__main__":
    import json
    import sys

    question = " ".join(sys.argv[1:]) or "What lighting is suitable for metal scratch inspection?"
    print(json.dumps(answer_question(question), indent=2, ensure_ascii=False))
