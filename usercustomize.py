"""Runtime patches for hosted Streamlit QA behavior."""

try:
    import qa_engine
    import zh_qa_adapter

    _ORIGINAL_ZH_ANSWER = zh_qa_adapter.answer_question

    _SCRATCH_TERMS = ["scratch", "\u5212\u75d5", "\u522e\u75d5", "\u64e6\u4f24"]
    _GLASS_TERMS = ["glass", "\u73bb\u7483", "\u900f\u660e\u4ef6", "\u900f\u660e", "\u4e9a\u514b\u529b", "\u955c\u7247"]
    _APPLICATION_CUES = ["\u68c0\u6d4b", "\u9009\u578b", "\u9002\u5408", "\u5e94\u8be5", "\u63a8\u8350", "\u5e94\u7528", "\u770b\u4ec0\u4e48\u5149\u6e90"]

    def _contains_any(text, terms):
        low = str(text or "").lower()
        return any(term.lower() in low for term in terms)

    def _sources_from_hits(hits, limit=10):
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

    def _glass_scratch_answer(question):
        hits = qa_engine.search_products("low angle dark field glass scratch DLQ DLA backlight BHL BHH coaxial dome", limit=10)
        return {
            "answer": (
                "\u521d\u6b65\u9009\u578b\u903b\u8f91\uff1a\u73bb\u7483\u5212\u75d5\u4e0d\u5e94\u76f4\u63a5\u5957\u7528\u91d1\u5c5e\u5212\u75d5\u903b\u8f91\u3002"
                "\u901a\u5e38\u53ef\u5148\u8bc4\u4f30\u4f4e\u89d2\u5ea6/\u6697\u573a\u7167\u660e\uff0c\u8ba9\u8868\u9762\u5212\u4f24\u901a\u8fc7\u6563\u5c04\u53d8\u4eae\uff1b"
                "\u5982\u679c\u76ee\u6807\u662f\u8fb9\u7f18\u3001\u5d29\u8fb9\u6216\u8f6e\u5ed3\uff0c\u518d\u8bc4\u4f30\u80cc\u5149\u3002"
                "\u900f\u660e\u6750\u6599\u5bf9\u89d2\u5ea6\u3001\u80cc\u666f\u548c\u504f\u632f\u5f88\u654f\u611f\uff0c\u5fc5\u987b\u7528\u6837\u54c1\u9a8c\u8bc1\u3002"
                " \u4e0b\u65b9\u5019\u9009\u4ea7\u54c1\u53ea\u6765\u81ea\u5f53\u524d TMS Lite \u6570\u636e\u5e93\u3002"
            ),
            "matched_products": hits,
            "spec_table": [],
            "sources": _sources_from_hits(hits),
            "missing_or_uncertain": [
                "\u9009\u578b\u5efa\u8bae\u53ea\u662f\u521d\u6b65\u5efa\u8bae\uff0c\u9700\u8981\u7ed3\u5408\u6837\u54c1\u3001\u51e0\u4f55\u7ed3\u6784\u3001\u5de5\u4f5c\u8ddd\u79bb\u3001\u76f8\u673a/\u955c\u5934\u548c\u5b9e\u9645\u56fe\u50cf\u9a8c\u8bc1\u3002",
                "\u5982\u679c\u662f\u6781\u6d45\u5212\u75d5\uff0c\u53ef\u80fd\u8fd8\u9700\u8981\u8bc4\u4f30\u504f\u632f\u3001\u80cc\u666f\u548c\u76f8\u673a\u89d2\u5ea6\uff1b\u5f53\u524d\u6570\u636e\u5e93\u8fd8\u6ca1\u6709\u8bb0\u5f55\u8fd9\u4e9b\u5b9e\u9a8c\u6761\u4ef6\u3002",
            ],
            "confidence": "medium" if hits else "low",
            "mode": "local",
        }

    def answer_question(question):
        if (
            _contains_any(question, _APPLICATION_CUES)
            and _contains_any(question, _SCRATCH_TERMS)
            and _contains_any(question, _GLASS_TERMS)
        ):
            return _glass_scratch_answer(question)
        return _ORIGINAL_ZH_ANSWER(question)

    zh_qa_adapter.answer_question = answer_question
    qa_engine.answer_question = answer_question
except Exception:
    pass
