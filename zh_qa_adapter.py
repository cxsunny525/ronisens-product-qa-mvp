from __future__ import annotations

import re
from typing import Any

import qa_engine


ORIGINAL_ANSWER_QUESTION = qa_engine.answer_question


QUERY_EXPANSIONS = [
    (["\u6761\u5f62", "\u6761\u72b6", "\u6761\u706f", "\u6761\u5149", "\u7ebf\u6027\u5149", "\u7ebf\u5f62\u5149"], "bar light HLBS HLBQ LSW LLA"),
    (["\u73af\u5f62", "\u73af\u72b6", "\u73af\u706f", "\u5706\u5f62"], "ring light LBR DLR HPD"),
    (["\u80cc\u5149", "\u80cc\u5149\u6e90"], "backlight BHL BHH BHS BIDS HBL"),
    (["\u540c\u8f74"], "coaxial CAS MCAX"),
    (["\u7a79\u9876", "\u6f2b\u5c04", "\u65e0\u5f71"], "dome diffuse FDD HBF"),
    (["\u4f4e\u89d2\u5ea6", "\u6697\u573a"], "low angle dark field DLQ DLA"),
    (["\u7ebf\u626b", "\u7ebf\u5149\u6e90"], "line scan line light"),
    (["\u70b9\u5149", "\u70b9\u5149\u6e90"], "spot light"),
    (["\u7ea2\u5149", "\u7ea2\u8272"], "red"),
    (["\u84dd\u5149", "\u84dd\u8272"], "blue"),
    (["\u7eff\u5149", "\u7eff\u8272"], "green"),
    (["\u767d\u5149", "\u767d\u8272"], "white"),
    (["\u7d2b\u5916", "UV"], "UV ultraviolet"),
    (["\u7ea2\u5916", "IR"], "IR infrared"),
    (["\u6570\u636e\u8868", "\u89c4\u683c\u4e66", "\u8d44\u6599", "\u76ee\u5f55", "PDF"], "datasheet catalog pdf"),
    (["\u7535\u538b"], "voltage"),
    (["\u529f\u7387"], "power watt"),
    (["\u7535\u6d41"], "current"),
    (["\u5c3a\u5bf8", "\u5916\u5f84", "\u5185\u5f84", "\u957f\u5ea6", "\u5bbd\u5ea6", "\u9ad8\u5ea6"], "dimension diameter length width height mm"),
]

LIGHT_TYPE_TERMS = {
    "ring": ["ring", "\u73af\u5f62", "\u73af\u706f"],
    "bar": ["bar", "\u6761\u5f62", "\u6761\u706f", "\u6761\u5149", "\u7ebf\u6027\u5149"],
    "backlight": ["backlight", "\u80cc\u5149", "\u80cc\u5149\u6e90"],
    "coaxial": ["coaxial", "\u540c\u8f74"],
    "dome": ["dome", "\u7a79\u9876", "\u6f2b\u5c04", "\u65e0\u5f71"],
    "low_angle": ["low angle", "\u4f4e\u89d2\u5ea6", "dark field", "\u6697\u573a"],
    "line": ["line", "\u7ebf\u626b", "\u7ebf\u5149\u6e90"],
    "spot": ["spot", "\u70b9\u5149", "\u70b9\u5149\u6e90"],
}

DATASHEET_TERMS = ["datasheet", "\u6570\u636e\u8868", "\u89c4\u683c\u4e66", "\u8d44\u6599", "\u76ee\u5f55", "pdf", "catalog", "catalogue"]
QUERY_TERMS = ["\u6709\u54ea\u4e9b", "\u54ea\u4e9b", "\u6709\u54ea", "\u6709\u6ca1\u6709", "\u67e5\u8be2", "\u627e", "\u5217\u51fa", "\u4ea7\u54c1", "\u5149\u6e90", "\u578b\u53f7", "\u53c2\u6570"]
APPLICATION_CUES = ["\u68c0\u6d4b", "\u9009\u578b", "\u9002\u5408", "\u5e94\u8be5", "\u63a8\u8350", "\u5e94\u7528", "\u770b\u4ec0\u4e48\u5149\u6e90"]
EN_APPLICATION_CUES = ["inspection", "detect", "selection", "suitable", "recommend", "lighting type", "what light"]
SCRATCH_TERMS = ["scratch", "\u5212\u75d5", "\u522e\u75d5", "\u64e6\u4f24"]
GLASS_TERMS = ["glass", "\u73bb\u7483", "\u900f\u660e\u4ef6", "\u900f\u660e", "\u4e9a\u514b\u529b", "\u955c\u7247"]
METAL_TERMS = ["metal", "\u91d1\u5c5e", "\u94dd", "\u94a2", "\u4e0d\u9508\u94a2", "\u94dc", "\u94c1"]
NO_ANSWER_ZH = "\u76ee\u524d\u7cfb\u7edf\u5c1a\u672a\u6709\u8fd9\u4e2a\u7b54\u6848\u3002\u5f53\u524d MVP \u53ea\u4f1a\u5728\u80fd\u591f\u660e\u786e\u7406\u89e3\u95ee\u9898\uff0c\u5e76\u4e14\u5f53\u524d TMS Lite \u6570\u636e\u5e93\u6216\u5df2\u914d\u7f6e\u89c4\u5219\u4e2d\u6709\u76f4\u63a5\u4f9d\u636e\u65f6\u56de\u7b54\uff1b\u4e3a\u907f\u514d\u8bef\u5bfc\uff0c\u672c\u95ee\u9898\u6682\u4e0d\u505a\u63a8\u6d4b\u3002"
NO_ANSWER_EN = "The system does not have this answer yet. This MVP only answers when the question is clearly understood and directly supported by the current TMS Lite database or configured rules; to avoid misleading guidance, it will not infer an answer."

APPLICATION_INTENTS = {
    "glass_scratch": {
        "keywords": ["\u73bb\u7483", "\u900f\u660e\u4ef6", "\u5212\u75d5", "\u522e\u75d5"],
        "logic": "\u73bb\u7483\u5212\u75d5\u4e0d\u5e94\u76f4\u63a5\u5957\u7528\u91d1\u5c5e\u5212\u75d5\u903b\u8f91\u3002\u901a\u5e38\u53ef\u5148\u8bc4\u4f30\u4f4e\u89d2\u5ea6/\u6697\u573a\u7167\u660e\uff0c\u8ba9\u8868\u9762\u5212\u4f24\u901a\u8fc7\u6563\u5c04\u53d8\u4eae\uff1b\u5982\u679c\u76ee\u6807\u662f\u8fb9\u7f18\u3001\u5d29\u8fb9\u6216\u8f6e\u5ed3\uff0c\u518d\u8bc4\u4f30\u80cc\u5149\u3002\u900f\u660e\u6750\u6599\u5bf9\u89d2\u5ea6\u3001\u80cc\u666f\u548c\u504f\u632f\u5f88\u654f\u611f\uff0c\u5fc5\u987b\u7528\u6837\u54c1\u9a8c\u8bc1\u3002",
        "query": "low angle dark field glass scratch DLQ DLA backlight BHL BHH coaxial dome",
    },
    "metal_scratch": {
        "keywords": ["\u91d1\u5c5e", "\u94dd", "\u94a2", "\u4e0d\u9508\u94a2", "\u94dc", "\u94c1"],
        "logic": "\u91d1\u5c5e\u5212\u75d5\u68c0\u6d4b\u901a\u5e38\u5148\u8003\u8651\u4f4e\u89d2\u5ea6\u6216\u6697\u573a\u7167\u660e\uff0c\u56e0\u4e3a\u63a0\u5c04\u5149\u66f4\u5bb9\u6613\u628a\u8868\u9762\u5212\u75d5\u51f8\u663e\u51fa\u6765\uff1b\u5e73\u6574\u53cd\u5149\u8868\u9762\u4e5f\u53ef\u4ee5\u8bc4\u4f30\u540c\u8f74\u5149\u3002",
        "query": "low angle dark field metal scratch DLQ DLA coaxial",
    },
    "surface_scratch": {
        "keywords": ["\u5212\u75d5", "\u522e\u75d5", "\u64e6\u4f24"],
        "logic": "\u95ee\u9898\u91cc\u6ca1\u6709\u660e\u786e\u6750\u6599\uff0c\u56e0\u6b64\u53ea\u80fd\u7ed9\u901a\u7528\u8868\u9762\u5212\u75d5\u521d\u6b65\u5efa\u8bae\uff1a\u901a\u5e38\u5148\u8bc4\u4f30\u4f4e\u89d2\u5ea6/\u6697\u573a\uff0c\u8ba9\u5212\u75d5\u901a\u8fc7\u6563\u5c04\u6216\u9634\u5f71\u5448\u73b0\uff1b\u5982\u679c\u662f\u900f\u660e\u4ef6\u6216\u8fb9\u7f18\u7f3a\u9677\uff0c\u5e94\u53e6\u5916\u8bc4\u4f30\u80cc\u5149\u3002",
        "query": "low angle dark field scratch DLQ DLA backlight coaxial",
    },
    "transparent_edge": {
        "keywords": ["\u900f\u660e", "\u74f6", "\u8fb9\u7f18"],
        "logic": "\u900f\u660e\u74f6\u6216\u900f\u660e\u4ef6\u8fb9\u7f18\u68c0\u6d4b\u901a\u5e38\u5148\u8003\u8651\u80cc\u5149\uff0c\u7528\u8f6e\u5ed3\u53cd\u5dee\u628a\u8fb9\u7f18\u62c9\u51fa\u6765\uff1b\u5982\u679c\u76ee\u6807\u662f\u5370\u5237\u6216\u8868\u9762\u53cd\u5c04\uff0c\u518d\u8bc4\u4f30\u540c\u8f74\u5149\u6216\u7a79\u9876\u6f2b\u5c04\u5149\u3002",
        "query": "backlight transparent edge BHL BHH BHS BIDS",
    },
    "pcb": {
        "keywords": ["pcb", "\u7535\u8def\u677f", "\u710a\u70b9", "\u5143\u4ef6"],
        "logic": "PCB \u68c0\u6d4b\u53ef\u4ee5\u5148\u6309\u76ee\u6807\u62c6\u5206\uff1a\u4e00\u822c\u5b9a\u4f4d\u53ef\u770b\u73af\u5f62\u5149\u6216\u6761\u5f62\u5149\uff0c\u710a\u76d8\u7b49\u53cd\u5149\u533a\u57df\u53ef\u770b\u540c\u8f74\u5149\uff0c\u5f3a\u53cd\u5149\u6216\u9634\u5f71\u95ee\u9898\u53ef\u770b\u7a79\u9876/\u6f2b\u5c04\u5149\uff0c\u8367\u5149\u76ee\u6807\u518d\u8003\u8651 UV\u3002",
        "query": "ring coaxial dome bar RGBW UV PCB",
    },
    "backlight": {
        "keywords": ["\u80cc\u5149", "\u8f6e\u5ed3", "\u5c3a\u5bf8", "\u5916\u5f62"],
        "logic": "\u80cc\u5149\u9002\u5408\u8f6e\u5ed3\u3001\u8fb9\u7f18\u3001\u5b54\u4f4d\u548c\u5c3a\u5bf8\u68c0\u6d4b\uff0c\u6838\u5fc3\u903b\u8f91\u662f\u8ba9\u88ab\u6d4b\u7269\u906e\u6321\u5149\u5f62\u6210\u9ad8\u5bf9\u6bd4\u526a\u5f71\u3002",
        "query": "backlight BHL BHH BHS BIDS",
    },
}


def _has_chinese(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def _contains_any(text: str, terms: list[str]) -> bool:
    low = text.lower()
    return any(term.lower() in low for term in terms)


def _wants_datasheet(question: str) -> bool:
    return _contains_any(question, DATASHEET_TERMS)


def _expand_query(question: str) -> str:
    expanded = [question]
    for triggers, addition in QUERY_EXPANSIONS:
        if any(trigger.lower() in question.lower() for trigger in triggers):
            expanded.append(addition)
    return " ".join(expanded)


def _requested_light_types(question: str) -> list[str]:
    expanded = _expand_query(question).lower()
    return [light_type for light_type, terms in LIGHT_TYPE_TERMS.items() if any(term.lower() in expanded for term in terms)]


def _public_row(product: dict[str, Any]) -> dict[str, Any]:
    return {
        "brand": product.get("brand") or "not available",
        "model": product.get("model") or "not available",
        "family": product.get("product_family") or "not available",
        "series": product.get("series") or "not available",
        "category": product.get("product_category") or "not available",
        "light_type": product.get("light_type") or "not available",
        "color": product.get("color") or product.get("wavelength_nm") or "not available",
        "voltage": product.get("voltage_v") or "not available",
        "power": product.get("power_w") or "not available",
        "current": product.get("current_ma") or "not available",
        "weight": product.get("weight_g") or "not available",
        "dimensions": product.get("dimensions_mm_json") or "not available",
        "product_url": product.get("product_url") or product.get("source_url") or "not available",
        "datasheet_url": product.get("datasheet_url") or "not available",
    }


def _sources_from_hits(hits: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    sources = []
    seen = set()
    for hit in hits:
        for key, source_type in [("product_url", "product_url"), ("datasheet_url", "datasheet")]:
            url = hit.get(key)
            if url and url != "not available" and url not in seen:
                seen.add(url)
                sources.append({"type": source_type, "title": hit.get("model"), "url": url})
            if len(sources) >= limit:
                return sources
    return sources


def _response(
    answer: str,
    matched_products: list[dict[str, Any]] | None = None,
    spec_table: list[dict[str, Any]] | None = None,
    sources: list[dict[str, Any]] | None = None,
    missing_or_uncertain: list[str] | None = None,
    confidence: str = "medium",
) -> dict[str, Any]:
    return {
        "answer": answer,
        "matched_products": matched_products or [],
        "spec_table": spec_table or [],
        "sources": sources or [],
        "missing_or_uncertain": missing_or_uncertain or [],
        "confidence": confidence,
        "mode": "local",
    }


def _no_answer(is_zh: bool = True) -> dict[str, Any]:
    return _response(
        NO_ANSWER_ZH if is_zh else NO_ANSWER_EN,
        [],
        [],
        [],
        [
            "\u9700\u8981\u5148\u628a\u8be5\u573a\u666f\u52a0\u5165\u53d7\u652f\u6301\u7684\u9009\u578b\u89c4\u5219\uff0c\u6216\u5728\u6570\u636e\u5e93\u4e2d\u8865\u5145\u53ef\u6838\u5bf9\u7684\u8bc1\u636e\u3002"
            if is_zh
            else "Add this scenario to supported selection rules or add verifiable database evidence before answering.",
        ],
        "low",
    )


def _extract_models(question: str) -> list[str]:
    compact = re.sub(r"\s+", "", question.upper())
    found = []
    for product in sorted(qa_engine.load_database().products, key=lambda p: len(str(p.get("model") or "")), reverse=True):
        model = str(product.get("model") or "")
        model_norm = re.sub(r"\s+", "", model.upper())
        if model_norm and len(model_norm) >= 4 and model_norm in compact:
            found.append(model)
    unique = list(dict.fromkeys(found))
    return [model for model in unique if not any(model != other and model.upper().replace(" ", "") in other.upper().replace(" ", "") for other in unique)]


def _select_application_intent(question: str) -> str | None:
    if not _contains_any(question, APPLICATION_CUES):
        return None
    if _contains_any(question, SCRATCH_TERMS):
        if _contains_any(question, METAL_TERMS):
            return "metal_scratch"
        return "unsupported_application"
    if _contains_any(question, GLASS_TERMS):
        return "unsupported_application"
    for intent, payload in APPLICATION_INTENTS.items():
        if _contains_any(question, payload["keywords"]):
            return intent
    return None


def _select_english_application_intent(question: str) -> str | None:
    if not _contains_any(question, EN_APPLICATION_CUES):
        return None
    if _contains_any(question, SCRATCH_TERMS):
        if _contains_any(question, GLASS_TERMS):
            return "unsupported_application"
        if _contains_any(question, METAL_TERMS):
            return "metal_scratch"
        return "unsupported_application"
    low = question.lower()
    if "transparent" in low and ("edge" in low or "bottle" in low):
        return "transparent_edge"
    if "pcb" in low:
        return "pcb"
    if "backlight" in low:
        return "backlight"
    return "unsupported_application"


def answer_question(question: str) -> dict[str, Any]:
    if not _has_chinese(question):
        english_intent = _select_english_application_intent(question)
        if english_intent == "unsupported_application":
            return _no_answer(False)
        return ORIGINAL_ANSWER_QUESTION(question)

    models = _extract_models(question)

    if "\u6bd4\u8f83" in question or "\u5bf9\u6bd4" in question:
        if not models:
            models = [hit["model"] for hit in qa_engine.search_products("24V backlight ring coaxial", limit=3)]
        table = qa_engine.compare_products(models)
        sources = []
        for model in models:
            sources.extend(qa_engine.get_product_sources(model)[:3])
        found_count = sum(1 for row in table if row.get("status") == "found")
        return _response(f"\u5df2\u5bf9\u6bd4 {len(models)} \u4e2a\u578b\u53f7\uff0c\u5176\u4e2d {found_count} \u4e2a\u5728\u5f53\u524d\u6570\u636e\u5e93\u4e2d\u6709\u8bb0\u5f55\uff1b\u672a\u6536\u5f55\u578b\u53f7\u4f1a\u660e\u786e\u6807\u4e3a not available\u3002", table, table, sources, confidence="high" if found_count else "low")

    quality_question = (
        _contains_any(question, ["\u7f3a\u5931", "\u7f3a\u5c11", "\u5b57\u6bb5", "\u672a\u8bb0\u5f55", "\u6ca1\u6709\u7535\u538b"])
        or ((not models) and "\u6ca1\u6709" in question and (_wants_datasheet(question) or "\u7535\u538b" in question))
    )
    if quality_question:
        if _wants_datasheet(question):
            products = [p for p in qa_engine.load_database().products if not p.get("datasheet_url")]
            rows = [_public_row(p) for p in products[:50]]
            return _response(
                f"\u5f53\u524d\u6570\u636e\u5e93\u4e2d\u6709 {len(products)} \u6761\u4ea7\u54c1\u8bb0\u5f55\u6ca1\u6709 datasheet_url\u3002",
                rows,
                [{"model": row["model"], "missing_field": "datasheet_url"} for row in rows],
                [],
                ["\u6ca1\u6709 datasheet_url \u53ef\u80fd\u8868\u793a\u722c\u866b\u6ca1\u6709\u89e3\u6790\u5230\u5916\u90e8\u94fe\u63a5\uff0c\u4e0d\u4e00\u5b9a\u4ee3\u8868\u5382\u5bb6\u6ca1\u6709\u89c4\u683c\u4e66\u3002"],
                "high",
            )
        if "\u7535\u538b" in question:
            missing = qa_engine.find_missing_fields("voltage_v")
            rows = [_public_row(p) for p in qa_engine.load_database().products if not p.get("voltage_v")][:50]
            return _response(f"\u5f53\u524d\u6570\u636e\u5e93\u4e2d\u6709 {missing['summary'][0]['missing_count']} \u6761\u4ea7\u54c1\u8bb0\u5f55\u6ca1\u6709\u7535\u538b\u53c2\u6570\u3002", rows, missing["summary"], [], [], "high")
        missing = qa_engine.find_missing_fields()
        return _response("\u5df2\u6839\u636e\u5f53\u524d\u6570\u636e\u5e93\u751f\u6210\u7f3a\u5931\u5b57\u6bb5\u7edf\u8ba1\uff0c\u7f3a\u5931\u6700\u591a\u7684\u5b57\u6bb5\u5e94\u4f18\u5148\u6e05\u6d17\u3002", [], missing["summary"], [], [], "high")

    if models:
        model = models[0]
        product = qa_engine.get_product_by_model(model)
        if product is None:
            return _response(f"{model} \u5f53\u524d\u6570\u636e\u5e93\u672a\u8bb0\u5f55\uff1b\u6211\u4e0d\u4f1a\u63a8\u6d4b\u6216\u7f16\u9020\u8fd9\u4e2a\u578b\u53f7\u3002", [], [], [], [f"\u672a\u627e\u5230\u578b\u53f7: {model}"], "high")
        specs = qa_engine.get_product_specs(product["model"])
        sources = qa_engine.get_product_sources(product["model"])
        if _wants_datasheet(question):
            if product.get("datasheet_url") != "not available":
                answer = f"{product['model']} \u5728\u5f53\u524d\u6570\u636e\u5e93\u4e2d\u6709 datasheet URL: {product['datasheet_url']}"
            else:
                answer = f"{product['model']} \u5f53\u524d\u6570\u636e\u5e93\u6709\u8bb0\u5f55\uff0c\u4f46\u6ca1\u6709 datasheet URL\u3002"
        else:
            answer = f"{product['model']} \u5f53\u524d\u6570\u636e\u5e93\u6709\u8bb0\u5f55\u3002\u5173\u952e\u5b57\u6bb5\uff1a\u7535\u538b {product['voltage']}\uff0c\u529f\u7387 {product['power']}\uff0c\u7535\u6d41 {product['current']}\uff0c\u5c3a\u5bf8 {product['dimensions']}\u3002"
        return _response(answer, [product], specs[:30], sources, [], "high")

    selected_intent = _select_application_intent(question)
    if selected_intent:
        if selected_intent == "unsupported_application":
            return _no_answer(True)
        payload = APPLICATION_INTENTS[selected_intent]
        hits = qa_engine.search_products(payload["query"], limit=10)
        missing = ["\u9009\u578b\u5efa\u8bae\u53ea\u662f\u521d\u6b65\u5efa\u8bae\uff0c\u9700\u8981\u7ed3\u5408\u6837\u54c1\u3001\u51e0\u4f55\u7ed3\u6784\u3001\u5de5\u4f5c\u8ddd\u79bb\u3001\u76f8\u673a/\u955c\u5934\u548c\u5b9e\u9645\u56fe\u50cf\u9a8c\u8bc1\u3002"]
        if not hits:
            missing.append("current database evidence is limited")
        return _response(f"\u521d\u6b65\u9009\u578b\u903b\u8f91\uff1a{payload['logic']} \u4e0b\u65b9\u5019\u9009\u4ea7\u54c1\u53ea\u6765\u81ea\u5f53\u524d TMS Lite \u6570\u636e\u5e93\u3002", hits, [], _sources_from_hits(hits), missing, "medium" if hits else "low")

    requested_types = _requested_light_types(question)
    if _contains_any(question, QUERY_TERMS) or requested_types or _wants_datasheet(question):
        hits = qa_engine.search_products(_expand_query(question), limit=40)
        if requested_types:
            strict_hits = [hit for hit in hits if hit.get("light_type") in requested_types]
            if strict_hits:
                hits = strict_hits
        if _wants_datasheet(question):
            hits = [hit for hit in hits if hit.get("datasheet_url") != "not available"]
        hits = hits[:20]
        type_note = f"\uff08\u5339\u914d\u5149\u6e90\u7c7b\u578b\uff1a{', '.join(requested_types)}\uff09" if requested_types else ""
        if hits:
            answer = f"\u5f53\u524d\u6570\u636e\u5e93\u627e\u5230 {len(hits)} \u6761\u5339\u914d\u4ea7\u54c1\u8bb0\u5f55{type_note}\u3002\u7ed3\u679c\u57fa\u4e8e\u6570\u636e\u5e93\u5b57\u6bb5\u3001\u7cfb\u5217\u540d\u3001\u578b\u53f7\u548c\u6765\u6e90\u6587\u672c\u6392\u5e8f\uff1b\u8bf7\u7ee7\u7eed\u6838\u5bf9\u8868\u683c\u4e2d\u7684 light_type\u3001family \u548c\u6765\u6e90\u94fe\u63a5\u3002"
        else:
            answer = "\u5f53\u524d\u6570\u636e\u5e93\u672a\u627e\u5230\u5339\u914d\u4ea7\u54c1\u8bb0\u5f55\u3002"
        return _response(answer, hits, [], _sources_from_hits(hits), [], "medium" if hits else "low")

    hits = qa_engine.search_products(_expand_query(question), limit=10)
    if hits:
        return _response(f"\u5f53\u524d\u6570\u636e\u5e93\u627e\u5230 {len(hits)} \u6761\u53ef\u80fd\u76f8\u5173\u7684\u4ea7\u54c1\u8bb0\u5f55\uff0c\u7ed3\u679c\u53ea\u57fa\u4e8e\u5f53\u524d\u6570\u636e\u5e93\u3002", hits, [], _sources_from_hits(hits), [], "medium")
    return _response("\u5f53\u524d\u6570\u636e\u5e93\u672a\u627e\u5230\u76f8\u5173\u8bb0\u5f55\u3002\u53ef\u4ee5\u8865\u5145\u4ea7\u54c1\u7c7b\u578b\u3001\u7535\u538b\u3001\u989c\u8272\u6216\u5e94\u7528\u573a\u666f\u518d\u8bd5\u3002", [], [], [], ["\u53ef\u4ee5\u8865\u5145\u4ea7\u54c1\u7c7b\u578b\u3001\u7535\u538b\u3001\u989c\u8272\u6216\u5e94\u7528\u573a\u666f\u3002"], "low")
