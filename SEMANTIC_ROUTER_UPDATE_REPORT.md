# Semantic Router Update Report

Date: 2026-05-27

## Problem Fixed

After a product availability question, the next question could behave as if the app was still in product-search mode. For example, asking about green lights and then asking which light to use for metal scratch detection could incorrectly return no product match.

## Changes

- Added semantic intent routing in `answer_engine.py`.
- Current-turn classification now decides whether to use:
  - IOO product availability search
  - IOO product list search
  - model lookup
  - product comparison
  - lighting selection recommendation
  - knowledge explanation
  - identification help
  - off-topic response
- If `OPENAI_API_KEY` is available, OpenAI is used first for semantic classification.
- If OpenAI is unavailable, local rule-based classification remains fully functional.
- Product retrieval now uses the latest user question by default, not the merged conversation history.
- Recent conversation context is only merged for ambiguous follow-ups or uploaded text notes.
- Off-topic questions receive a polite, lightly humorous refusal and no product recommendation.

## Verification

- `有没有绿色光源` -> `attribute_search`, 375 matches.
- Follow-up `which light I should consider if I want to detect the scratch on the metal ?` -> `recommendation`, 5 IOO dark-field candidates.
- `今天天气怎么样？` -> `off_topic`, no products.
- `Can you recommend a good pizza recipe?` -> `off_topic`, no products.
- `What is global shutter in machine vision?` -> `knowledge_explanation`.

## Tests

- `test_public_brand_safety.py`: passed, 2/2.
- `test_qa_engine.py`: passed, 23/23.
- Python compile check passed for `answer_engine.py`, `app.py`, and `product_search.py`.
