from __future__ import annotations

import json
import os
import re
from typing import Any

import brand_config
import knowledge_engine
import sku_mapping


FORBIDDEN_PUBLIC_TERMS = [
    "TMS Lite",
    "TMS-Lite",
    "TMS_LITE",
    "TMS LITE",
    "tms-lite",
    "TMS",
    "Advanced Illumination",
    "advancedillumination",
]

FORBIDDEN_SOURCE_NAMES = {"advanced illumination", "tms lite", "tms"}

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
    knowledge = retrieve_public_knowledge(full_question, limit=5)
    products = [public_product(row) for row in sku_mapping.search_public_products(full_question, limit=5)]
    missing = missing_information(full_question)
    completeness = solution_profile_completeness(full_question)
    direct = direct_recommendation(full_question, products)
    strategy = lighting_strategy(full_question, knowledge)
    test_plan = practical_test_plan(full_question, products)
    followups = follow_up_suggestions(missing)
    local_answer = compose_local_answer(full_question, direct, strategy, products, test_plan, missing, followups)
    openai_answer, used_openai, openai_warning = compose_openai_answer(
        full_question,
        direct,
        strategy,
        products,
        test_plan,
        missing,
        knowledge,
    )
    answer = openai_answer or local_answer
    warnings = []
    if openai_warning:
        warnings.append(openai_warning)
    if not used_openai:
        warnings.append(
            "AI reasoning is running in local fallback mode. Add OPENAI_API_KEY in Streamlit Secrets to enable full AI responses."
        )
    if products and products[0].get("fit_type") != "Exact fit":
        warnings.append("This should be tested as a practical workaround rather than treated as a guaranteed match.")
    clean_answer = sanitize_public_text(answer)
    fit_type = products[0].get("fit_type") if products else "Needs custom / manual review"
    confidence = "medium" if knowledge["sources"] and products else "low"
    return {
        "answer": clean_answer,
        "direct_recommendation": sanitize_public_text(direct),
        "lighting_strategy": sanitize_public_text(strategy),
        "closest_ioo_products": products,
        "product_recommendations": products,
        "matched_products": products,
        "practical_test_plan": test_plan,
        "missing_information": missing,
        "missing_or_uncertain": missing + warnings,
        "knowledge_sources": knowledge["sources"],
        "product_sources": [{"type": "product_database", "title": "IOO internal product database", "url": None}],
        "sources": knowledge["sources"] + [{"type": "product_database", "title": "IOO internal product database", "url": None}],
        "confidence": confidence,
        "fit_type": fit_type,
        "solution_profile_completeness": completeness,
        "follow_up_suggestions": followups,
        "mode": "openai" if used_openai else "local fallback",
        "used_openai": used_openai,
        "warnings": [sanitize_public_text(w) for w in warnings],
        "query_interpretation": interpret_question(full_question),
        "evidence": product_evidence(products),
        "match_reason": product_match_reasons(products),
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
    value = re.sub(r"https?://(?:www\.)?tms-lite\.com/\S*", "IOO internal product database", value, flags=re.I)
    value = re.sub(r"https?://(?:www\.)?advancedillumination\.com/\S*", "public knowledge source", value, flags=re.I)
    value = re.sub(r"\bguaranteed\b|\bperfect solution\b|\bbest product\b", "recommended starting point", value, flags=re.I)
    return re.sub(r"\s+\n", "\n", value).strip()


def retrieve_public_knowledge(question: str, limit: int = 5) -> dict[str, Any]:
    docs = knowledge_engine.search_knowledge(question, limit=limit * 4)
    filtered = []
    seen = set()
    for doc in docs:
        source_name = str(doc.get("source_name") or doc.get("publisher") or "").strip()
        if source_name.lower() in FORBIDDEN_SOURCE_NAMES:
            continue
        url = doc.get("url") or doc.get("source_url")
        if not url or url in seen:
            continue
        title = sanitize_public_text(doc.get("title") or source_name or "Knowledge source")
        filtered.append(
            {
                "type": "knowledge_source",
                "source_name": sanitize_public_text(source_name or "Knowledge source"),
                "title": title,
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
        source_name = str(doc.get("source_name") or doc.get("publisher") or "").strip()
        if source_name.lower() in FORBIDDEN_SOURCE_NAMES:
            continue
        summary = doc.get("summary") or doc.get("best_chunk_text") or ""
        if summary:
            basis.append(
                {
                    "title": sanitize_public_text(doc.get("title") or "Knowledge note"),
                    "summary": sanitize_public_text(summary)[:500],
                    "source_name": sanitize_public_text(source_name or "Knowledge source"),
                    "url": doc.get("url") or doc.get("source_url"),
                }
            )
        if len(basis) >= limit:
            break
    return {"sources": filtered, "basis": basis}


def public_product(row: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "public_brand",
        "public_model",
        "product_category",
        "light_type",
        "color",
        "wavelength_nm",
        "voltage_v",
        "power_w",
        "current_a",
        "dimensions",
        "key_specs",
        "public_description",
        "recommendation_tags",
        "score",
        "fit_type",
        "why_it_may_fit",
    }
    item = {key: sanitize_public_text(row.get(key)) for key in allowed if key in row}
    item["brand"] = "IOO"
    item["model"] = item.get("public_model", "")
    return item


def interpret_question(question: str) -> dict[str, Any]:
    text = (question or "").lower()
    return {
        "language": "zh" if is_chinese(question) else "en",
        "intent": "lighting_selection",
        "detected_tags": sku_mapping.infer_query_tags(question),
        "has_uploaded_context": "uploaded text note:" in text,
        "asks_for_line_scan": "line scan" in text or "线扫" in text,
    }


def missing_information(question: str) -> list[str]:
    lower = (question or "").lower()
    missing = []
    for label, needles in MISSING_INFO_FIELDS:
        if not any(needle.lower() in lower for needle in needles):
            missing.append(label)
    return missing[:6]


def solution_profile_completeness(question: str) -> str:
    total = len(MISSING_INFO_FIELDS)
    missing_count = len(missing_information(question))
    provided = total - missing_count
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
        strategy = "start with uniform backlight or controlled side lighting to create a silhouette/edge contrast"
        strategy_zh = "先用均匀背光或受控侧向光建立轮廓/边缘对比"
    elif "scratch_detection" in tags or "reflective_surface" in tags:
        strategy = "start with low-angle dark-field lighting, then compare coaxial or diffuse lighting if glare dominates"
        strategy_zh = "先测试低角度暗场照明；如果反光太强，再比较同轴光或漫射光"
    elif "pcb_inspection" in tags:
        strategy = "start with coaxial or diffuse front lighting, then tune angle and wavelength for component contrast"
        strategy_zh = "先测试同轴光或漫射正面照明，再根据元件和缺陷对比调整角度与波长"
    elif "line_scan" in tags:
        strategy = "start with a bar or line-scan lighting configuration aligned to the scan direction"
        strategy_zh = "先用条形光或线扫照明，并让光照方向与扫描方向匹配"
    else:
        strategy = "start with a controlled lighting experiment using the closest IOO configuration"
        strategy_zh = "先用最接近的 IOO 配置做受控打光实验"
    if zh:
        if top:
            return f"建议先采用：{strategy_zh}。最接近的 IOO 选项是 {top['public_model']}，这是当前可用的近似配置。"
        return f"建议先采用：{strategy_zh}。当前需要人工确认最接近的 IOO 配置。"
    if top:
        return f"A practical configuration to test first is: {strategy}. The closest IOO option is {top['public_model']}. This is the closest IOO configuration currently available."
    return f"A practical configuration to test first is: {strategy}. This may be a custom lighting case."


def lighting_strategy(question: str, knowledge: dict[str, Any]) -> str:
    zh = is_chinese(question)
    tags = set(sku_mapping.infer_query_tags(question))
    basis_note = ""
    if knowledge["basis"]:
        basis_note = " Source-linked knowledge notes support this direction."
    if "transparent_edge" in tags:
        text = "Backlight works by putting the object between the light and camera, so edges, holes, and transparent boundaries become silhouette features. Risk factors include bottle curvature, refraction, and ambient reflections."
        zh_text = "背光的核心机制是让工件位于光源和相机之间，把边缘、孔洞和透明边界变成轮廓特征。风险点包括瓶体曲率、折射和环境反光。"
    elif "scratch_detection" in tags or "reflective_surface" in tags:
        text = "Low-angle dark-field lighting can make scratches and shallow surface defects scatter light into the camera while flatter areas stay darker. Coaxial or diffuse lighting may be useful if the surface is mirror-like and glare dominates."
        zh_text = "低角度暗场照明可以让划痕和浅表面缺陷把光散射进相机，而较平整区域保持较暗。如果表面接近镜面反射，同轴光或漫射光也值得对比测试。"
    elif "pcb_inspection" in tags:
        text = "PCB inspection usually depends on whether the target is solder, copper, silkscreen, components, or surface contamination. Coaxial, dome/diffuse, and directional bar lighting are useful starting geometries to compare."
        zh_text = "PCB 检测要先区分目标是焊点、铜箔、丝印、元件还是污染物。同轴光、穹顶/漫射光和定向条形光都可以作为起点对比。"
    elif "line_scan" in tags:
        text = "Line scan setups need stable illumination across the scan line, synchronized exposure, and control of motion blur. Bar or line lighting is usually tested first."
        zh_text = "线扫场景需要沿扫描线稳定照明、曝光同步，并控制运动模糊。通常先测试条形光或线光源。"
    else:
        text = "Lighting selection is mainly about creating repeatable contrast through geometry, wavelength, reflection, transmission, and scattering. The current information is enough for a first-pass recommendation, but sample testing is still needed."
        zh_text = "光源选型的核心是通过几何角度、波长、反射、透射和散射建立稳定对比。当前信息足够做第一轮建议，但仍需要样品测试确认。"
    return (zh_text if zh else text + basis_note).strip()


def practical_test_plan(question: str, products: list[dict[str, Any]]) -> list[str]:
    zh = is_chinese(question)
    if zh:
        return [
            "先固定相机、镜头、曝光和工作距离，只改变光源角度。",
            "拍摄 2-3 组样品图：合格品、缺陷品和边界样品。",
            "记录每组图像的对比度、眩光、阴影和误检风险。",
            "提供视野、工作距离和缺陷尺寸后，可以进一步缩小 IOO 型号范围。",
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
            "source": "IOO internal product database",
            "reason": product.get("why_it_may_fit"),
        }
        for product in products
    ]


def product_match_reasons(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "public_model": product.get("public_model"),
            "fit_type": product.get("fit_type"),
            "reason": product.get("why_it_may_fit"),
            "confidence": "medium" if product.get("fit_type") != "Workaround fit" else "low",
        }
        for product in products
    ]


def compose_local_answer(
    question: str,
    direct: str,
    strategy: str,
    products: list[dict[str, Any]],
    test_plan: list[str],
    missing: list[str],
    followups: list[str],
) -> str:
    zh = is_chinese(question)
    product_lines = []
    for product in products[:3]:
        note = "This is the closest IOO configuration currently available."
        if product.get("fit_type") == "Workaround fit":
            note = "A practical workaround may be to test this geometry first, then adjust mounting, wavelength, or diffusion."
        product_lines.append(f"- {product['public_model']} ({product.get('light_type')}): {product.get('why_it_may_fit')}. {note}")
    if zh:
        return "\n\n".join(
            [
                f"直接建议：{direct}",
                f"打光逻辑：{strategy}",
                "最接近的 IOO 产品：\n" + "\n".join(product_lines),
                "测试计划：\n" + "\n".join(f"- {item}" for item in test_plan),
                "还需要补充： " + ", ".join(missing),
                "可以继续问： " + " | ".join(followups),
            ]
        )
    return "\n\n".join(
        [
            f"Direct recommendation: {direct}",
            f"Lighting strategy: {strategy}",
            "Closest IOO product options:\n" + "\n".join(product_lines),
            "Practical test plan:\n" + "\n".join(f"- {item}" for item in test_plan),
            "Missing information: " + ", ".join(missing),
            "Continue with: " + " | ".join(followups),
        ]
    )


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

        client = OpenAI(api_key=api_key)
        payload = {
            "user_question": question,
            "direct_recommendation": direct,
            "lighting_strategy": strategy,
            "ioo_products": products,
            "test_plan": test_plan,
            "missing_information": missing,
            "knowledge_basis": knowledge["basis"],
        }
        prompt = (
            "You are IOO Lighting AI. Compose a concise, professional machine-vision lighting recommendation. "
            "Use only the IOO product models provided. Do not invent models, specs, URLs, or sources. "
            "Never mention supplier names, TMS, TMS Lite, Advanced Illumination, reseller, or distributor. "
            "Avoid guarantee language. If products are not exact, say closest IOO option or practical workaround. "
            "Keep sources conceptual; product source is IOO internal product database."
        )
        response = client.chat.completions.create(
            model=str(cfg.get("model") or "gpt-4.1-mini"),
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0.2,
        )
        text = response.choices[0].message.content or ""
        return sanitize_public_text(text), True, None
    except Exception as exc:
        return None, False, f"OpenAI response unavailable; local fallback was used. ({type(exc).__name__})"


if __name__ == "__main__":
    import sys

    q = " ".join(sys.argv[1:]) or "Detect scratches on reflective metal."
    print(json.dumps(answer_question(q), indent=2, ensure_ascii=False))
