from __future__ import annotations

from typing import Any

import qa_engine
import zh_qa_adapter


NO_ANSWER_ZH = "\u76ee\u524d\u7cfb\u7edf\u5c1a\u672a\u6709\u8fd9\u4e2a\u7b54\u6848\u3002\u5f53\u524d MVP \u53ea\u4f1a\u5728\u80fd\u591f\u660e\u786e\u7406\u89e3\u95ee\u9898\uff0c\u5e76\u4e14\u5f53\u524d TMS Lite \u6570\u636e\u5e93\u6216\u5df2\u914d\u7f6e\u89c4\u5219\u4e2d\u6709\u76f4\u63a5\u4f9d\u636e\u65f6\u56de\u7b54\uff1b\u4e3a\u907f\u514d\u8bef\u5bfc\uff0c\u672c\u95ee\u9898\u6682\u4e0d\u505a\u63a8\u6d4b\u3002"
NO_ANSWER_EN = "The system does not have this answer yet. This MVP only answers when the question is clearly understood and directly supported by the current TMS Lite database or configured rules; to avoid misleading guidance, it will not infer an answer."

ZH_APPLICATION_CUES = ["\u68c0\u6d4b", "\u9009\u578b", "\u9002\u5408", "\u5e94\u8be5", "\u63a8\u8350", "\u5e94\u7528", "\u770b\u4ec0\u4e48\u5149\u6e90"]
EN_APPLICATION_CUES = ["inspection", "detect", "selection", "suitable", "recommend", "lighting type", "what light"]
SCRATCH_TERMS = ["scratch", "\u5212\u75d5", "\u522e\u75d5", "\u64e6\u4f24"]
GLASS_TERMS = ["glass", "\u73bb\u7483", "\u900f\u660e\u4ef6", "\u900f\u660e", "\u4e9a\u514b\u529b", "\u955c\u7247"]
METAL_TERMS = ["metal", "\u91d1\u5c5e", "\u94dd", "\u94a2", "\u4e0d\u9508\u94a2", "\u94dc", "\u94c1"]
SUPPORTED_ZH_APP_TERMS = [
    ["\u91d1\u5c5e", "\u5212\u75d5"],
    ["\u91d1\u5c5e", "\u522e\u75d5"],
    ["pcb"],
    ["\u7535\u8def\u677f"],
    ["\u900f\u660e", "\u8fb9\u7f18"],
    ["\u74f6", "\u8fb9\u7f18"],
    ["\u80cc\u5149"],
    ["\u8f6e\u5ed3"],
]


def _has_chinese(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in str(text or ""))


def _contains_any(text: str, terms: list[str]) -> bool:
    low = str(text or "").lower()
    return any(term.lower() in low for term in terms)


def _contains_all(text: str, terms: list[str]) -> bool:
    low = str(text or "").lower()
    return all(term.lower() in low for term in terms)


def _no_answer(is_zh: bool) -> dict[str, Any]:
    return {
        "answer": NO_ANSWER_ZH if is_zh else NO_ANSWER_EN,
        "matched_products": [],
        "spec_table": [],
        "sources": [],
        "missing_or_uncertain": [
            "\u9700\u8981\u5148\u628a\u8be5\u573a\u666f\u52a0\u5165\u53d7\u652f\u6301\u7684\u9009\u578b\u89c4\u5219\uff0c\u6216\u5728\u6570\u636e\u5e93\u4e2d\u8865\u5145\u53ef\u6838\u5bf9\u7684\u8bc1\u636e\u3002"
            if is_zh
            else "Add this scenario to supported selection rules or add verifiable database evidence before answering."
        ],
        "confidence": "low",
        "mode": "local",
    }


def _is_supported_zh_application(question: str) -> bool:
    return any(_contains_all(question, terms) for terms in SUPPORTED_ZH_APP_TERMS)


def _is_supported_en_application(question: str) -> bool:
    low = question.lower()
    if "metal" in low and "scratch" in low:
        return True
    if "transparent" in low and ("edge" in low or "bottle" in low):
        return True
    if "pcb" in low:
        return True
    if "backlight" in low:
        return True
    return False


def _looks_like_application_question(question: str, is_zh: bool) -> bool:
    cues = ZH_APPLICATION_CUES if is_zh else EN_APPLICATION_CUES
    return _contains_any(question, cues)


def answer_question(question: str) -> dict[str, Any]:
    is_zh = _has_chinese(question)

    if _looks_like_application_question(question, is_zh):
        if is_zh:
            if _contains_any(question, SCRATCH_TERMS) and not _contains_any(question, METAL_TERMS):
                return _no_answer(True)
            if _contains_any(question, GLASS_TERMS) and not _is_supported_zh_application(question):
                return _no_answer(True)
            if not _is_supported_zh_application(question):
                return _no_answer(True)
        else:
            if _contains_any(question, SCRATCH_TERMS) and not _contains_any(question, METAL_TERMS):
                return _no_answer(False)
            if _contains_any(question, GLASS_TERMS) and not _is_supported_en_application(question):
                return _no_answer(False)
            if not _is_supported_en_application(question):
                return _no_answer(False)

    result = zh_qa_adapter.answer_question(question) if is_zh else qa_engine.answer_question(question)
    if _looks_like_application_question(question, is_zh) and not result.get("matched_products"):
        return _no_answer(is_zh)
    return result
