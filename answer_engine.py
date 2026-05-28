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


def answer_question(
    question: str,
    brand_filter: str | None = None,
    mode: str = "public",
    conversation_context: list[dict[str, Any]] | None = None,
    uploaded_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    del brand_filter, mode
    full_question = _merge_context(question, conversation_context, uploaded_context)
    intent = classify_intent(full_question)
    knowledge = retrieve_public_knowledge(full_question, limit=5)
    missing = missing_information(full_question)
    completeness = solution_profile_completeness(full_question)

    if intent == "comparison":
        result = answer_comparison(full_question, knowledge, missing, completeness)
    elif intent == "model_lookup":
        result = answer_model_lookup(full_question, knowledge, missing, completeness)
    elif intent == "list_search":
        result = answer_list_search(full_question, knowledge, missing, completeness)
    else:
        result = answer_recommendation(full_question, knowledge, missing, completeness)

    result["answer"] = sanitize_public_text(result.get("answer", ""))
    result["direct_recommendation"] = sanitize_public_text(result.get("direct_recommendation", ""))
    result["lighting_strategy"] = sanitize_public_text(result.get("lighting_strategy", ""))
    result["warnings"] = [sanitize_public_text(warning) for warning in result.get("warnings", [])]
    result["product_sources"] = [{"type": "product_database", "title": "IOO product database", "url": None}]
    result["sources"] = result.get("knowledge_sources", []) + result["product_sources"]
    result["query_interpretation"] = interpret_question(full_question, intent)
    result["evidence"] = product_evidence(result.get("closest_ioo_products", []) or result.get("product_results", []))
    result["match_reason"] = product_match_reasons(result.get("closest_ioo_products", []) or result.get("product_results", []))
    result["mode"] = "openai" if result.get("used_openai") else "local fallback"
    return result


def classify_intent(question: str) -> str:
    text = (question or "").lower()
    if any(token in text for token in ["compare", "比较", "对比"]):
        return "comparison"
    if product_search.model_mentions(question):
        return "model_lookup"
    list_tokens = [
        "list",
        "show all",
        "which",
        "what products",
        "有哪些",
        "哪些",
        "列出",
        "所有",
        "多少",
    ]
    if any(token in text for token in list_tokens):
        return "list_search"
    return "recommendation"


def answer_model_lookup(
    question: str,
    knowledge: dict[str, Any],
    missing: list[str],
    completeness: str,
) -> dict[str, Any]:
    mentions = product_search.model_mentions(question)
    products = []
    missing_models = []
    for mention in mentions:
        product = product_search.resolve_model(mention)
        if product:
            product["fit_type"] = "Exact fit"
            product["why_it_may_fit"] = "model exactly matched in the IOO product database"
            products.append(product)
        else:
            missing_models.append(mention)
    zh = is_chinese(question)
    if products:
        models = ", ".join(p["public_model"] for p in products)
        direct = f"当前 IOO 产品库记录了这些型号：{models}。" if zh else f"The current IOO product database includes: {models}."
        confidence = "high"
    else:
        requested = ", ".join(missing_models) if missing_models else "the requested model"
        direct = (
            f"当前 IOO 产品库未记录明确匹配型号：{requested}。"
            if zh
            else f"No exact IOO product match was found for: {requested}."
        )
        confidence = "high"
    answer = compose_plain_answer(direct, "", products, [], missing_models)
    return base_result(
        question,
        intent="model_lookup",
        answer=answer,
        direct=direct,
        strategy="",
        products=products,
        product_results=products,
        total=len(products),
        knowledge=knowledge,
        missing=missing,
        completeness=completeness,
        confidence=confidence,
        warnings=[f"No exact IOO match for {model}." for model in missing_models],
    )


def answer_comparison(
    question: str,
    knowledge: dict[str, Any],
    missing: list[str],
    completeness: str,
) -> dict[str, Any]:
    mentions = product_search.model_mentions(question)
    comparison = product_search.compare_products(mentions)
    products = comparison["products"]
    zh = is_chinese(question)
    if products:
        direct = (
            f"已找到 {len(products)} 个可比较的 IOO 型号。"
            if zh
            else f"Found {len(products)} IOO products to compare."
        )
    else:
        direct = "当前 IOO 产品库未记录可比较的明确型号。" if zh else "No exact IOO products were found for comparison."
    rows = product_search.product_table_rows(products, limit=20)
    lines = [direct]
    for row in rows:
        lines.append(
            f"- {row['public_model']}: {row.get('light_type')}; {row.get('voltage_v')}; {row.get('power_w')}; {row.get('dimensions')}"
        )
    if comparison["missing"]:
        lines.append("Missing exact matches: " + ", ".join(comparison["missing"]))
    return base_result(
        question,
        intent="comparison",
        answer="\n".join(lines),
        direct=direct,
        strategy="Comparison uses only exact IOO database matches.",
        products=products[:5],
        product_results=products,
        total=len(products),
        knowledge=knowledge,
        missing=missing,
        completeness=completeness,
        confidence="high" if products else "medium",
        warnings=[f"No exact IOO match for {model}." for model in comparison["missing"]],
    )


def answer_list_search(
    question: str,
    knowledge: dict[str, Any],
    missing: list[str],
    completeness: str,
) -> dict[str, Any]:
    search = product_search.search_products(question, limit=20)
    products = search["products"]
    total = search["total"]
    zh = is_chinese(question)
    filters = ", ".join(f"{k}={v}" for k, v in search["filters"].items()) or "keyword search"
    if total:
        direct = (
            f"当前 IOO 产品库找到 {total} 个匹配产品；下面显示前 {len(products)} 个。"
            if zh
            else f"Found {total} matching IOO products; showing first {len(products)}."
        )
    else:
        direct = "当前 IOO 产品库未记录明确匹配产品。" if zh else "No exact IOO product match was found."
    rows = product_search.product_table_rows(products, limit=20)
    product_lines = [f"- {row['public_model']}: {row.get('light_type')}, {row.get('color')}, {row.get('voltage_v')}" for row in rows]
    answer = "\n".join([direct, f"Matched filters: {filters}", *product_lines])
    return base_result(
        question,
        intent="list_search",
        answer=answer,
        direct=direct,
        strategy="This is a database search, not a generated recommendation.",
        products=products[:5],
        product_results=products,
        total=total,
        knowledge=knowledge,
        missing=missing,
        completeness=completeness,
        confidence="high" if total else "medium",
        warnings=[] if total else ["No exact IOO product match was found."],
    )


def answer_recommendation(
    question: str,
    knowledge: dict[str, Any],
    missing: list[str],
    completeness: str,
) -> dict[str, Any]:
    products = product_search.recommend_products(question, limit=5)
    strategy = lighting_strategy(question, knowledge)
    direct = direct_recommendation(question, products)
    test_plan = practical_test_plan(question)
    followups = follow_up_suggestions(missing)
    local_answer = compose_plain_answer(direct, strategy, products, test_plan, missing)
    openai_answer, used_openai, openai_warning = compose_openai_answer(
        question, direct, strategy, products, test_plan, missing, knowledge
    )
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
    return base_result(
        question,
        intent="recommendation",
        answer=answer,
        direct=direct,
        strategy=strategy,
        products=products,
        product_results=products,
        total=len(products),
        knowledge=knowledge,
        missing=missing,
        completeness=completeness,
        confidence="medium" if products else "low",
        warnings=warnings,
        test_plan=test_plan,
        followups=followups,
        used_openai=used_openai,
    )


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
        "fit_type": products[0].get("fit_type", "Close fit") if products else "Needs custom / manual review",
        "solution_profile_completeness": completeness,
        "follow_up_suggestions": followups or follow_up_suggestions(missing),
        "used_openai": used_openai,
        "warnings": warnings,
        "intent": intent,
        "question": question,
        "knowledge_basis": knowledge["basis"],
    }


def _merge_context(
    question: str,
    conversation_context: list[dict[str, Any]] | None,
    uploaded_context: dict[str, Any] | None,
) -> str:
    parts = [question or ""]
    if conversation_context:
        recent = []
        for item in conversation_context[-4:]:
            q = item.get("question") or item.get("user_question") or ""
            if q:
                recent.append(str(q))
        if recent:
            parts.append("Recent session context: " + " | ".join(recent))
    if uploaded_context and uploaded_context.get("text"):
        parts.append("Uploaded text note: " + str(uploaded_context["text"])[:1600])
    return "\n\n".join(part for part in parts if part).strip()


def is_chinese(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


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


def interpret_question(question: str, intent: str) -> dict[str, Any]:
    return {
        "language": "zh" if is_chinese(question) else "en",
        "intent": intent,
        "detected_tags": sku_mapping.infer_query_tags(question),
        "filters": product_search.infer_filters(question),
        "model_mentions": product_search.model_mentions(question),
        "has_uploaded_context": "uploaded text note:" in (question or "").lower(),
    }


def missing_information(question: str) -> list[str]:
    lower = (question or "").lower()
    missing = []
    for label, needles in MISSING_INFO_FIELDS:
        if not any(needle.lower() in lower for needle in needles):
            missing.append(label)
    return missing[:6]


def solution_profile_completeness(question: str) -> str:
    provided = len(MISSING_INFO_FIELDS) - len(missing_information(question))
    if provided >= 5:
        return "High"
    if provided >= 3:
        return "Medium"
    return "Low"


def direct_recommendation(question: str, products: list[dict[str, Any]]) -> str:
    zh = is_chinese(question)
    top = products[0] if products else None
    tags = set(sku_mapping.infer_query_tags(question))
    if "transparent_edge" in tags:
        strategy = "start with uniform backlight or controlled side lighting to create silhouette/edge contrast"
        strategy_zh = "先用均匀背光或受控侧向光建立轮廓/边缘对比"
    elif "scratch_detection" in tags or "reflective_surface" in tags:
        strategy = "start with low-angle dark-field lighting, then compare coaxial or diffuse lighting if glare dominates"
        strategy_zh = "先测试低角度暗场照明；如果反光过强，再比较同轴光或漫射光"
    elif "pcb_inspection" in tags:
        strategy = "start with coaxial or diffuse front lighting, then tune angle and wavelength for component contrast"
        strategy_zh = "先测试同轴光或漫射正面照明，再根据元件和缺陷对比调整角度与波长"
    elif "line_scan" in tags:
        strategy = "start with a bar or line-scan lighting configuration aligned to the scan direction"
        strategy_zh = "先用条形光或线扫照明，并让照明方向与扫描方向匹配"
    else:
        strategy = "start with a controlled lighting experiment using the closest IOO configuration"
        strategy_zh = "先用最接近的 IOO 配置做受控打光实验"
    if zh:
        if top:
            return f"建议先采用：{strategy_zh}。最接近的 IOO 选项是 {top['public_model']}，这是当前可用的近似配置。"
        return f"建议先采用：{strategy_zh}。当前需要更多参数来缩小 IOO 产品范围。"
    if top:
        return f"A practical configuration to test first is: {strategy}. The closest IOO option is {top['public_model']}."
    return f"A practical configuration to test first is: {strategy}. Provide more details to narrow the IOO shortlist."


def lighting_strategy(question: str, knowledge: dict[str, Any]) -> str:
    zh = is_chinese(question)
    tags = set(sku_mapping.infer_query_tags(question))
    basis_note = " Source-linked knowledge notes support this direction." if knowledge["basis"] else ""
    if "transparent_edge" in tags:
        text = "Backlight creates a transmitted-light silhouette, which can make transparent edges, holes, and boundaries easier to segment. Refraction, bottle curvature, and ambient reflections still need sample testing."
        zh_text = "背光通过透射轮廓建立边缘对比，适合透明边缘、孔洞和轮廓分割；但瓶体曲率、折射和环境反光仍需要样品测试。"
    elif "scratch_detection" in tags or "reflective_surface" in tags:
        text = "Low-angle dark-field lighting can make scratches scatter light into the camera while flat regions stay darker. Coaxial or diffuse lighting is useful to compare when mirror-like glare dominates."
        zh_text = "低角度暗场照明可以让划痕把光散射进相机，而较平整区域保持较暗；如果镜面反光占主导，应对比同轴光或漫射光。"
    elif "pcb_inspection" in tags:
        text = "PCB lighting depends on whether the target is solder, copper, silkscreen, components, or contamination. Coaxial, dome/diffuse, and directional bar lighting are useful starting geometries."
        zh_text = "PCB 检测要先区分目标是焊点、铜箔、丝印、元件还是污染物。同轴光、穹顶/漫射光和定向条形光都可以作为起点。"
    elif "line_scan" in tags:
        text = "Line scan setups need stable illumination along the scan line, synchronized exposure, and motion-blur control. Bar or line lighting is usually tested first."
        zh_text = "线扫场景需要沿扫描线稳定照明、曝光同步，并控制运动模糊。通常先测试条形光或线光源。"
    else:
        text = "Lighting selection is mainly about creating repeatable contrast through geometry, wavelength, reflection, transmission, and scattering."
        zh_text = "光源选型的核心，是通过几何角度、波长、反射、透射和散射建立稳定可重复的对比。"
    return (zh_text if zh else text + basis_note).strip()


def practical_test_plan(question: str) -> list[str]:
    if is_chinese(question):
        return [
            "先固定相机、镜头、曝光和工作距离，只改变光源角度。",
            "拍摄合格品、缺陷品和边界样品各 2-3 组图。",
            "记录每组图像的对比度、眩光、阴影和误检风险。",
            "补充视野、工作距离和缺陷尺寸后，可进一步缩小 IOO 型号范围。",
        ]
    return [
        "Fix camera, lens, exposure, and working distance before changing lighting geometry.",
        "Capture 2-3 image sets: good part, defect part, and borderline sample.",
        "Compare contrast, glare, shadows, and false-positive risk.",
        "Provide field of view, working distance, and defect size to narrow the IOO option further.",
    ]


def follow_up_suggestions(missing: list[str]) -> list[str]:
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


def product_match_reasons(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "public_model": product.get("public_model"),
            "fit_type": product.get("fit_type", "Exact fit"),
            "reason": product.get("why_it_may_fit") or "matched by IOO database search",
            "confidence": "medium" if product.get("fit_type") != "Workaround fit" else "low",
        }
        for product in products[:20]
    ]


def compose_plain_answer(
    direct: str,
    strategy: str,
    products: list[dict[str, Any]],
    test_plan: list[str],
    missing_or_notes: list[str],
) -> str:
    product_lines = []
    for product in products[:5]:
        note = "This is the closest IOO configuration currently available."
        if product.get("fit_type") == "Workaround fit":
            note = "This should be tested as a practical workaround rather than treated as a guaranteed match."
        product_lines.append(f"- {product['public_model']} ({product.get('light_type')}): {product.get('why_it_may_fit') or product.get('public_description')}. {note}")
    blocks = [direct]
    if strategy:
        blocks.append(strategy)
    if product_lines:
        blocks.append("IOO product basis:\n" + "\n".join(product_lines))
    if test_plan:
        blocks.append("Practical test plan:\n" + "\n".join(f"- {item}" for item in test_plan))
    if missing_or_notes:
        blocks.append("Missing or uncertain:\n" + "\n".join(f"- {item}" for item in missing_or_notes))
    return "\n\n".join(blocks)


def compose_openai_answer(
    question: str,
    direct: str,
    strategy: str,
    products: list[dict[str, Any]],
    test_plan: list[str],
    missing: list[str],
    knowledge: dict[str, Any],
) -> tuple[str | None, bool, str | None]:
    cfg = brand_config.openai_config()
    api_key = os.getenv(str(cfg.get("env_var") or "OPENAI_API_KEY"))
    if not api_key:
        return None, False, None
    try:
        from openai import OpenAI  # type: ignore

        allowed_models = {str(product.get("public_model")) for product in products}
        payload = {
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
            "If no exact product exists, choose closest candidates from the provided IOO database and label them as close fit or workaround."
        )
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=str(cfg.get("model") or "gpt-4.1-mini"),
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
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
