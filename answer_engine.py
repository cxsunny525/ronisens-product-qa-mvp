from __future__ import annotations

import json
import os
import re
from typing import Any

import brand_config
import knowledge_engine
import product_search
import sku_mapping


FORBIDDEN_PUBLIC_TERMS = [
    "TMS Lite",
    "TMS-Lite",
    "TMS_LITE",
    "TMS LITE",
    "tms-lite",
    "Advanced Illumination",
    "advancedillumination",
    "supplier",
    "internal_model",
    "internal_supplier",
]

MISSING_INFO_FIELDS = [
    ("material", ["metal", "glass", "plastic", "paper", "rubber", "ceramic", "金属", "玻璃", "塑料"]),
    ("defect type", ["scratch", "edge", "crack", "dent", "pcb", "barcode", "ocr", "划痕", "边缘", "缺陷"]),
    ("field of view", ["field of view", "fov", "视野"]),
    ("working distance", ["working distance", "wd", "工作距离"]),
    ("camera type", ["camera", "line scan", "area scan", "相机", "线扫"]),
    ("line speed", ["speed", "m/s", "line speed", "速度"]),
    ("ambient light", ["ambient", "room light", "环境光"]),
]

FIT_LABELS = {
    "en": {
        "Exact fit": "Exact fit",
        "Close fit": "Close fit",
        "Workaround fit": "Workaround fit",
        "Needs custom / manual review": "Needs custom / manual review",
    },
    "zh": {
        "Exact fit": "精确匹配",
        "Close fit": "接近匹配",
        "Workaround fit": "替代方案匹配",
        "Needs custom / manual review": "需要定制或人工确认",
    },
}


def detect_user_language(text: str | None) -> str:
    return "zh" if re.search(r"[\u4e00-\u9fff]", text or "") else "en"


def answer_question(
    question: str,
    brand_filter: str | None = None,
    mode: str = "public",
    conversation_context: list[dict[str, Any]] | None = None,
    uploaded_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    del brand_filter, mode
    language = detect_user_language(question)
    full_question = _merge_context(question, conversation_context, uploaded_context)
    intent = classify_intent(question or full_question)
    knowledge = retrieve_public_knowledge(full_question, limit=5) if should_retrieve_knowledge(full_question, intent) else {"sources": [], "basis": []}
    missing = missing_information(full_question) if needs_practical_guidance(full_question) else []
    completeness = solution_profile_completeness(full_question)

    if intent == "identification_help":
        result = answer_identification_help(full_question, knowledge, missing, completeness, language)
    elif intent == "comparison":
        result = answer_comparison(full_question, knowledge, missing, completeness, language)
    elif intent == "model_lookup":
        result = answer_model_lookup(full_question, knowledge, missing, completeness, language)
    elif intent in {"list_search", "attribute_search"}:
        result = answer_list_search(full_question, knowledge, missing, completeness, language, intent)
    else:
        result = answer_recommendation(full_question, knowledge, missing, completeness, language)

    result["language"] = language
    result["answer"] = sanitize_public_text(result.get("answer", ""))
    result["direct_recommendation"] = sanitize_public_text(result.get("direct_recommendation", ""))
    result["lighting_strategy"] = sanitize_public_text(result.get("lighting_strategy", ""))
    result["warnings"] = [sanitize_public_text(warning) for warning in result.get("warnings", [])]
    result["product_sources"] = [{"type": "product_database", "title": "IOO product database", "url": None}]
    result["sources"] = result.get("knowledge_sources", []) + result["product_sources"]
    result["query_interpretation"] = interpret_question(full_question, intent, language)
    result["evidence"] = product_evidence(result.get("closest_ioo_products", []) or result.get("product_results", []))
    result["match_reason"] = product_match_reasons(result.get("closest_ioo_products", []) or result.get("product_results", []), language)
    result["mode"] = "openai" if result.get("used_openai") else "local fallback"
    return result


def classify_intent(question: str) -> str:
    text = (question or "").lower()
    filters = product_search.infer_filters(question)
    availability_tokens = [
        "do you have",
        "have any",
        "are there",
        "available",
        "how many",
        "count",
        "number of",
        "total",
        "有没有",
        "有吗",
        "有多少",
        "多少个",
    ]
    list_tokens = ["list", "show all", "which", "what products", "有哪些", "哪些", "列出", "所有"]
    if any(token in text for token in ["what is this light", "what type of light is this", "identify this light", "这是什么光源", "这是什么灯", "这是什么"]):
        return "identification_help"
    if any(token in text for token in ["compare", "比较", "对比"]):
        return "comparison"
    if product_search.model_mentions(question):
        return "model_lookup"
    if filters and any(token in text for token in availability_tokens):
        return "attribute_search"
    if filters and detect_user_language(question) == "zh" and ("吗" in text or "有没有" in text):
        return "attribute_search"
    if needs_practical_guidance(question):
        return "recommendation"
    if any(token in text for token in availability_tokens + list_tokens):
        return "list_search"
    if filters and not needs_practical_guidance(question):
        return "attribute_search"
    return "recommendation"


def answer_identification_help(
    question: str,
    knowledge: dict[str, Any],
    missing: list[str],
    completeness: str,
    language: str,
) -> dict[str, Any]:
    if language == "zh":
        direct = "我现在不能仅凭这句话可靠判断具体光源类型。"
        strategy = "请补充外形、发光方向、安装位置、被检测物体和想凸显的缺陷；如果上传了图片，当前版本会接收图片，但不会假装已经完成视觉识别。"
        followups = ["描述光源外形和发光方向。", "告诉我检测对象和缺陷。", "上传图片并说明你想判断什么。"]
    else:
        direct = "I cannot reliably identify the lighting type from that sentence alone."
        strategy = "Share the light shape, emitting direction, mounting position, inspected object, and the defect you want to reveal. If an image is uploaded, this MVP receives it but does not pretend to perform visual identification."
        followups = ["Describe the light shape and emitting direction.", "Tell me the inspected object and defect.", "Upload an image and describe what to identify."]
    return base_result(question, "identification_help", f"{direct}\n\n{strategy}", direct, strategy, [], [], 0, knowledge, missing, completeness, "medium", [], [], followups, False)


def answer_model_lookup(
    question: str,
    knowledge: dict[str, Any],
    missing: list[str],
    completeness: str,
    language: str,
) -> dict[str, Any]:
    products = []
    missing_models = []
    for mention in product_search.model_mentions(question):
        product = product_search.resolve_model(mention)
        if product:
            product["fit_type"] = "Exact fit"
            product["why_it_may_fit"] = "model exactly matched in the IOO product database"
            products.append(product)
        else:
            missing_models.append(mention)
    if products:
        models = ", ".join(p["public_model"] for p in products)
        direct = f"当前 IOO 产品库中有这些型号：{models}。" if language == "zh" else f"The current IOO product database includes: {models}."
    else:
        requested = ", ".join(missing_models) if missing_models else ("该型号" if language == "zh" else "the requested model")
        direct = f"当前 IOO 产品库中没有明确匹配：{requested}。" if language == "zh" else f"No exact IOO product match was found for: {requested}."
    answer = compose_plain_answer(direct, "", products, [], missing_models, language)
    return base_result(question, "model_lookup", answer, direct, "", products, products, len(products), knowledge, missing, completeness, "high", [f"No exact IOO match for {m}." for m in missing_models], [], follow_up_suggestions([], language), False)


def answer_comparison(
    question: str,
    knowledge: dict[str, Any],
    missing: list[str],
    completeness: str,
    language: str,
) -> dict[str, Any]:
    comparison = product_search.compare_products(product_search.model_mentions(question))
    products = comparison["products"]
    if products:
        direct = f"找到 {len(products)} 个可对比的 IOO 型号。" if language == "zh" else f"Found {len(products)} IOO products to compare."
    else:
        direct = "当前 IOO 产品库中没有找到可对比的明确型号。" if language == "zh" else "No exact IOO products were found for comparison."
    lines = [direct]
    for row in product_search.product_table_rows(products, limit=20):
        lines.append(f"- {row['public_model']}: {row.get('light_type')}; {row.get('voltage_v')}; {row.get('power_w')}; {row.get('dimensions')}")
    if comparison["missing"]:
        lines.append(("未找到：" if language == "zh" else "Missing exact matches: ") + ", ".join(comparison["missing"]))
    return base_result(question, "comparison", "\n".join(lines), direct, "", products[:5], products, len(products), knowledge, missing, completeness, "high" if products else "medium", [f"No exact IOO match for {m}." for m in comparison["missing"]], [], follow_up_suggestions([], language), False)


def answer_list_search(
    question: str,
    knowledge: dict[str, Any],
    missing: list[str],
    completeness: str,
    language: str,
    intent: str,
) -> dict[str, Any]:
    search = product_search.search_products(question, limit=20)
    products = search["products"]
    total = int(search["total"])
    filters = search["filters"]
    if total:
        direct = (
            f"有，当前 IOO 产品库中找到 {total} 个相关产品，下面显示前 {len(products)} 个。"
            if language == "zh"
            else f"Yes. Found {total} matching IOO products; showing first {len(products)}."
        )
        confidence = "high"
        warnings: list[str] = []
        strategy = "这是数据库检索结果，不是生成式推荐。" if language == "zh" else "This is a database search result, not a generated recommendation."
    else:
        direct = no_match_text(question, filters, language)
        confidence = "medium"
        warnings = [direct]
        strategy = workaround_text_for_filters(filters, language)
    product_lines = []
    for row in product_search.product_table_rows(products, limit=20):
        product_lines.append(f"- {row['public_model']}: {row.get('light_type')}, {row.get('color')}, {row.get('wavelength_nm')}, {row.get('voltage_v')}")
    answer = "\n".join([direct, strategy, *product_lines]).strip()
    return base_result(question, intent, answer, direct, strategy, products[:5], products, total, knowledge, missing, completeness, confidence, warnings, [], follow_up_suggestions([], language), False)


def answer_recommendation(
    question: str,
    knowledge: dict[str, Any],
    missing: list[str],
    completeness: str,
    language: str,
) -> dict[str, Any]:
    products = product_search.recommend_products(question, limit=5)
    strategy = lighting_strategy(question, knowledge, language)
    direct = direct_recommendation(question, products, language)
    test_plan = practical_test_plan(question, language)
    followups = follow_up_suggestions(missing, language)
    local_answer = compose_plain_answer(direct, strategy, products, test_plan, missing, language)
    openai_answer, used_openai, openai_warning = compose_openai_answer(question, direct, strategy, products, test_plan, missing, knowledge, language)
    answer = openai_answer or local_answer
    warnings = []
    if openai_warning:
        warnings.append(openai_warning)
    if not used_openai:
        warnings.append("AI reasoning is running in local fallback mode. Add OPENAI_API_KEY in Streamlit Secrets to enable full AI responses.")
    if products and products[0].get("fit_type") != "Exact fit":
        warnings.append("This should be tested as a practical workaround rather than treated as a guaranteed match.")
    if not products:
        warnings.append("No exact IOO product match was found; provide more details for a closer shortlist.")
    return base_result(question, "recommendation", answer, direct, strategy, products, products, len(products), knowledge, missing, completeness, "medium" if products else "low", warnings, test_plan, followups, used_openai)


def base_result(
    question: str,
    intent: str,
    answer: str,
    direct: str,
    strategy: str,
    products: list[dict[str, Any]],
    product_results: list[dict[str, Any]],
    total: int,
    knowledge: dict[str, Any],
    missing: list[str],
    completeness: str,
    confidence: str,
    warnings: list[str],
    test_plan: list[str] | None = None,
    followups: list[str] | None = None,
    used_openai: bool = False,
) -> dict[str, Any]:
    fit = products[0].get("fit_type", "Close fit") if products else "Needs custom / manual review"
    return {
        "answer": answer,
        "direct_recommendation": direct,
        "lighting_strategy": strategy,
        "closest_ioo_products": products,
        "product_recommendations": products,
        "matched_products": product_results,
        "product_results": product_results,
        "total_matched": total,
        "showing_count": len(product_results),
        "practical_test_plan": test_plan or [],
        "missing_information": missing,
        "missing_or_uncertain": missing + warnings,
        "knowledge_sources": knowledge["sources"],
        "confidence": confidence,
        "fit_type": fit,
        "fit_type_label": translate_fit_type(fit, detect_user_language(question)),
        "solution_profile_completeness": completeness,
        "follow_up_suggestions": followups or [],
        "used_openai": used_openai,
        "warnings": warnings,
        "intent": intent,
        "question": question,
        "knowledge_basis": knowledge["basis"],
    }


def no_match_text(question: str, filters: dict[str, str], language: str) -> str:
    if language == "zh":
        if filters.get("color") in {"violet_uv", "uv"}:
            return "当前 IOO 产品库中没有找到明确匹配的紫光 / violet / UV 产品。"
        return "当前 IOO 产品库中没有找到明确匹配的产品。"
    if filters.get("color") in {"violet_uv", "uv"}:
        return "No clearly matching purple / violet / UV product is currently marked in the IOO product database."
    return "No exact IOO product match was found in the current database."


def workaround_text_for_filters(filters: dict[str, str], language: str) -> str:
    if filters.get("color") in {"violet_uv", "uv"}:
        return (
            "可行的替代方向是：先用白光或蓝光做对比实验，必要时加入滤光片，或者把 UV/紫光作为定制波长需求确认。"
            if language == "zh"
            else "A practical workaround may be to test white or blue illumination with filtering, or treat UV/violet as a custom wavelength requirement."
        )
    return "" if language == "zh" else ""


def _merge_context(question: str, conversation_context: list[dict[str, Any]] | None, uploaded_context: dict[str, Any] | None) -> str:
    parts = [question or ""]
    if conversation_context:
        recent = [str(item.get("question") or item.get("user_question") or "") for item in conversation_context[-4:]]
        recent = [item for item in recent if item]
        if recent:
            parts.append("Recent session context: " + " | ".join(recent))
    if uploaded_context and uploaded_context.get("text"):
        parts.append("Uploaded text note: " + str(uploaded_context["text"])[:1600])
    return "\n\n".join(part for part in parts if part).strip()


def is_chinese(text: str) -> bool:
    return detect_user_language(text) == "zh"


def sanitize_public_text(text: Any) -> str:
    value = str(text or "")
    for term in FORBIDDEN_PUBLIC_TERMS:
        value = re.sub(re.escape(term), "IOO", value, flags=re.I)
    value = re.sub(r"https?://(?:www\.)?tms-lite\.com/\S*", "IOO product database", value, flags=re.I)
    value = re.sub(r"\bguaranteed\b|\bperfect solution\b|\bbest product\b", "recommended starting point", value, flags=re.I)
    return re.sub(r"\s+\n", "\n", value).strip()


def retrieve_public_knowledge(question: str, limit: int = 5) -> dict[str, Any]:
    docs = knowledge_engine.search_knowledge(question, limit=limit * 4)
    filtered = []
    seen = set()
    for doc in docs:
        url = doc.get("url") or doc.get("source_url")
        if not url or url in seen:
            continue
        source_name = sanitize_public_text(doc.get("source_name") or doc.get("publisher") or "Knowledge source")
        filtered.append(
            {
                "type": "knowledge_source",
                "source_name": source_name,
                "title": sanitize_public_text(doc.get("title") or source_name),
                "url": url,
                "review_status": doc.get("review_status") or "pending",
                "quality_score": doc.get("quality_score"),
            }
        )
        seen.add(url)
        if len(filtered) >= limit:
            break
    basis = []
    for doc in docs:
        summary = doc.get("summary") or doc.get("best_chunk_text") or ""
        if summary:
            basis.append(
                {
                    "title": sanitize_public_text(doc.get("title") or "Knowledge note"),
                    "summary": sanitize_public_text(summary)[:500],
                    "source_name": sanitize_public_text(doc.get("source_name") or doc.get("publisher") or "Knowledge source"),
                    "url": doc.get("url") or doc.get("source_url"),
                }
            )
        if len(basis) >= limit:
            break
    return {"sources": filtered, "basis": basis}


def needs_practical_guidance(question: str) -> bool:
    text = (question or "").lower()
    guidance_terms = [
        "detect",
        "inspect",
        "inspection",
        "defect",
        "scratch",
        "edge",
        "pcb",
        "line scan",
        "transparent",
        "reflective",
        "recommend",
        "suitable",
        "selection",
        "choose",
        "improve contrast",
        "application",
        "检测",
        "检验",
        "缺陷",
        "划痕",
        "边缘",
        "透明",
        "反光",
        "金属",
        "适合",
        "推荐",
        "选型",
        "方案",
        "打光",
        "如何",
        "怎么",
    ]
    return any(term in text for term in guidance_terms)


def should_retrieve_knowledge(question: str, intent: str) -> bool:
    if intent in {"model_lookup", "comparison", "identification_help", "list_search", "attribute_search"}:
        return False
    return needs_practical_guidance(question)


def missing_information(question: str) -> list[str]:
    if not needs_practical_guidance(question):
        return []
    lower = (question or "").lower()
    missing = []
    for label, needles in MISSING_INFO_FIELDS:
        if not any(needle.lower() in lower for needle in needles):
            missing.append(label)
    return missing[:6]


def solution_profile_completeness(question: str) -> str:
    if not needs_practical_guidance(question):
        return "Basic"
    provided = len(MISSING_INFO_FIELDS) - len(missing_information(question))
    if provided >= 5:
        return "High"
    if provided >= 3:
        return "Medium"
    return "Low"


def interpret_question(question: str, intent: str, language: str) -> dict[str, Any]:
    return {
        "language": language,
        "intent": intent,
        "detected_tags": sku_mapping.infer_query_tags(question),
        "filters": product_search.infer_filters(question),
        "model_mentions": product_search.model_mentions(question),
        "has_uploaded_context": "uploaded text note:" in (question or "").lower(),
    }


def direct_recommendation(question: str, products: list[dict[str, Any]], language: str) -> str:
    top = products[0] if products else None
    tags = set(sku_mapping.infer_query_tags(question))
    if "transparent_edge" in tags:
        strategy_en = "start with uniform backlight or controlled side lighting to create silhouette/edge contrast"
        strategy_zh = "先用均匀背光或受控侧向光建立轮廓 / 边缘对比"
    elif "scratch_detection" in tags or "reflective_surface" in tags:
        strategy_en = "start with low-angle dark-field lighting, then compare coaxial or diffuse lighting if glare dominates"
        strategy_zh = "先测试低角度暗场照明；如果反光过强，再对比同轴光或漫射光"
    elif "pcb_inspection" in tags:
        strategy_en = "start with coaxial or diffuse front lighting, then tune angle and wavelength for component contrast"
        strategy_zh = "先测试同轴光或漫射正面照明，再根据元件和缺陷对比调整角度与波长"
    elif "line_scan" in tags:
        strategy_en = "start with a bar or line-scan lighting configuration aligned to the scan direction"
        strategy_zh = "先使用条形光或线扫照明，并让照明方向与扫描方向匹配"
    else:
        strategy_en = "start with a controlled lighting experiment using the closest IOO configuration"
        strategy_zh = "先用最接近的 IOO 配置做受控打光实验"
    if language == "zh":
        return f"建议先采用：{strategy_zh}。最接近的 IOO 选项是 {top['public_model']}，这是当前可用的近似配置。" if top else f"建议先采用：{strategy_zh}。当前需要更多参数来缩小 IOO 产品范围。"
    return f"A practical configuration to test first is: {strategy_en}. The closest IOO option is {top['public_model']}." if top else f"A practical configuration to test first is: {strategy_en}. Provide more details to narrow the IOO shortlist."


def lighting_strategy(question: str, knowledge: dict[str, Any], language: str) -> str:
    tags = set(sku_mapping.infer_query_tags(question))
    if "transparent_edge" in tags:
        en = "Backlight creates a transmitted-light silhouette, which can make transparent edges, holes, and boundaries easier to segment. Refraction, bottle curvature, and ambient reflections still need sample testing."
        zh = "背光可以通过透射轮廓建立边缘对比，适合透明边缘、孔洞和轮廓分割；但瓶体曲率、折射和环境反光仍需要样品测试。"
    elif "scratch_detection" in tags or "reflective_surface" in tags:
        en = "Low-angle dark-field lighting can make scratches scatter light into the camera while flat regions stay darker. Coaxial or diffuse lighting is useful to compare when mirror-like glare dominates."
        zh = "低角度暗场照明可以让划痕把光散射进相机，而较平整区域保持较暗；如果镜面反光占主导，应对比同轴光或漫射光。"
    elif "pcb_inspection" in tags:
        en = "PCB lighting depends on whether the target is solder, copper, silkscreen, components, or contamination. Coaxial, dome/diffuse, and directional bar lighting are useful starting geometries."
        zh = "PCB 检测要先区分目标是焊点、铜箔、丝印、元件还是污染物。同轴光、穹顶 / 漫射光和定向条形光都可以作为起点。"
    elif "line_scan" in tags:
        en = "Line scan setups need stable illumination along the scan line, synchronized exposure, and motion-blur control. Bar or line lighting is usually tested first."
        zh = "线扫场景需要沿扫描线稳定照明、曝光同步，并控制运动模糊。通常先测试条形光或线光源。"
    else:
        en = "Lighting selection is mainly about creating repeatable contrast through geometry, wavelength, reflection, transmission, and scattering."
        zh = "光源选型的核心，是通过几何角度、波长、反射、透射和散射建立稳定可重复的对比。"
    if language == "en" and knowledge["basis"]:
        en += " Source-linked knowledge notes support this direction."
    return zh if language == "zh" else en


def practical_test_plan(question: str, language: str) -> list[str]:
    if not needs_practical_guidance(question):
        return []
    if language == "zh":
        return [
            "先固定相机、镜头、曝光和工作距离，只改变光源角度。",
            "拍摄合格品、缺陷品和边界样品各 2-3 组图。",
            "记录每组图像的对比度、眩光、阴影和误检风险。",
            "补充视野、工作距离和缺陷尺寸后，再进一步缩小 IOO 型号范围。",
        ]
    return [
        "Fix camera, lens, exposure, and working distance before changing lighting geometry.",
        "Capture 2-3 image sets: good part, defect part, and borderline sample.",
        "Compare contrast, glare, shadows, and false-positive risk.",
        "Provide field of view, working distance, and defect size to narrow the IOO option further.",
    ]


def follow_up_suggestions(missing: list[str], language: str = "en") -> list[str]:
    if language == "zh":
        suggestions = []
        if "working distance" in missing:
            suggestions.append("告诉我工作距离。")
        if "field of view" in missing:
            suggestions.append("补充视野或工件尺寸。")
        if "material" in missing:
            suggestions.append("被测材料和表面状态是什么？")
        if not suggestions:
            suggestions.append("上传样品图或需求说明。")
        suggestions.append("对比另一种打光方式。")
        return suggestions[:3]
    suggestions = []
    if "working distance" in missing:
        suggestions.append("Tell me the working distance.")
    if "field of view" in missing:
        suggestions.append("Share the field of view or part size.")
    if "material" in missing:
        suggestions.append("What material and surface finish are we inspecting?")
    if not suggestions:
        suggestions.append("Upload a sample image or requirement note.")
    suggestions.append("Compare this approach with an alternative lighting geometry.")
    return suggestions[:3]


def translate_fit_type(fit_type: str, language: str) -> str:
    return FIT_LABELS.get(language, FIT_LABELS["en"]).get(fit_type, fit_type)


def product_evidence(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "public_model": product.get("public_model"),
            "field_name": "light_type",
            "value": product.get("light_type"),
            "source": "IOO product database",
            "reason": product.get("why_it_may_fit") or product.get("public_description"),
        }
        for product in products[:20]
    ]


def product_match_reasons(products: list[dict[str, Any]], language: str = "en") -> list[dict[str, Any]]:
    return [
        {
            "public_model": product.get("public_model"),
            "fit_type": translate_fit_type(product.get("fit_type", "Exact fit"), language),
            "reason": product.get("why_it_may_fit") or ("数据库匹配" if language == "zh" else "matched by IOO database search"),
            "confidence": "medium" if product.get("fit_type") != "Workaround fit" else "low",
        }
        for product in products[:20]
    ]


def compose_plain_answer(direct: str, strategy: str, products: list[dict[str, Any]], test_plan: list[str], missing_or_notes: list[str], language: str) -> str:
    product_lines = []
    for product in products[:5]:
        note = "这是当前最接近的 IOO 配置。" if language == "zh" else "This is the closest IOO configuration currently available."
        if product.get("fit_type") == "Workaround fit":
            note = "这应作为可测试的替代方案，而不是保证匹配。" if language == "zh" else "This should be tested as a practical workaround rather than treated as a guaranteed match."
        product_lines.append(f"- {product['public_model']} ({product.get('light_type')}): {product.get('why_it_may_fit') or product.get('public_description')}. {note}")
    blocks = [direct]
    if strategy:
        blocks.append(strategy)
    if product_lines:
        blocks.append(("IOO 产品依据:\n" if language == "zh" else "IOO product basis:\n") + "\n".join(product_lines))
    if test_plan:
        blocks.append(("建议测试步骤:\n" if language == "zh" else "Practical test plan:\n") + "\n".join(f"- {item}" for item in test_plan))
    if missing_or_notes:
        blocks.append(("还需要补充或确认:\n" if language == "zh" else "Missing or uncertain:\n") + "\n".join(f"- {item}" for item in missing_or_notes))
    return "\n\n".join(blocks)


def compose_openai_answer(
    question: str,
    direct: str,
    strategy: str,
    products: list[dict[str, Any]],
    test_plan: list[str],
    missing: list[str],
    knowledge: dict[str, Any],
    language: str,
) -> tuple[str | None, bool, str | None]:
    cfg = brand_config.openai_config()
    api_key = os.getenv(str(cfg.get("env_var") or "OPENAI_API_KEY"))
    if not api_key:
        return None, False, None
    try:
        from openai import OpenAI  # type: ignore

        allowed_models = {str(product.get("public_model")) for product in products}
        payload = {
            "language": language,
            "user_question": question,
            "direct_recommendation": direct,
            "lighting_strategy": strategy,
            "allowed_ioo_products": products,
            "test_plan": test_plan,
            "missing_information": missing,
            "knowledge_basis": knowledge["basis"],
        }
        prompt = (
            "You are IOO Lighting AI. Compose a concise machine-vision lighting answer. "
            "You may only recommend products from the provided candidate list. "
            "Do not invent product models. Do not modify product model names. "
            "Do not mention private source names, supply chain terms, reseller, or distributor. "
            "If the user asks in Chinese, answer in Chinese. Keep product model numbers unchanged, "
            "but translate labels, explanations, fit type, warnings, and follow-up suggestions into Chinese."
        )
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=str(cfg.get("model") or "gpt-4.1-mini"),
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
            temperature=0.2,
        )
        text = sanitize_public_text(response.choices[0].message.content or "")
        mentioned = set(re.findall(r"\bIOO-[A-Z0-9][A-Z0-9_.-]*\b", text.upper()))
        if any(model not in allowed_models for model in mentioned):
            return None, False, "OpenAI output referenced a model outside the retrieved IOO candidate list; local grounded answer was used."
        return text, True, None
    except Exception as exc:
        return None, False, f"OpenAI response unavailable; local fallback was used. ({type(exc).__name__})"


if __name__ == "__main__":
    import sys

    q = " ".join(sys.argv[1:]) or "Detect scratches on reflective metal."
    print(json.dumps(answer_question(q), indent=2, ensure_ascii=False))
