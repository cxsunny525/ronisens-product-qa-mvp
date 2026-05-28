# Contextual Follow-Up Fix Report

Date: 2026-05-27

## Problem

After IOO recommended products, follow-up questions such as `how much is this model?`, `what voltage?`, or `datasheet for this model?` were treated as new standalone lookup questions. Because the phrase `this model` is not an actual model number, the system could answer as if no product existed.

## Fix

- Added contextual follow-up detection in `answer_engine.py`.
- The system now resolves previous IOO candidate models from the active conversation history.
- Added `pricing_followup` intent.
- Added `product_detail_followup` intent.
- Pricing responses explicitly state that price is not available in the current IOO product database and should be confirmed by quote.
- Spec/detail responses reuse the previous candidate models and show public database fields.

## Supported Follow-Ups

- `how much is this model?`
- `what is the price?`
- `多少钱？`
- `报价是多少？`
- `what voltage?`
- `what are the specs of this model?`
- `datasheet for this model?`
- `这个型号的参数？`

## Verification

- `Inspect transparent bottle edges.` -> recommendation with IOO candidates.
- `how much is this model ?` -> `pricing_followup`, resolves previous candidates, does not invent pricing.
- `what voltage?` -> `product_detail_followup`, resolves previous candidates.
- `what are the specs of this model?` -> `product_detail_followup`.
- `datasheet for this model?` -> `product_detail_followup`.

## Tests

- `test_public_brand_safety.py`: passed, 2/2.
- `test_qa_engine.py`: passed, 23/23.
- Python compile check passed for `answer_engine.py`, `app.py`, and `product_search.py`.
