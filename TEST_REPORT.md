# Test Report

## IOO Lighting AI Upgrade

Test date: 2026-05-27

## Scope

This report covers the upgrade to a single-brand IOO Lighting AI selection
assistant with public IOO SKUs, closest-fit recommendations, optional OpenAI
reasoning, local fallback mode, uploads, conversation history, and session
points.

## Checks Completed

- Public UI title is `IOO Lighting AI`.
- Public product cards show IOO public SKUs only.
- Public answers use IOO product recommendations only.
- Public product source is shown as `IOO internal product database`.
- Upload image behavior does not claim visual interpretation.
- Text upload context can be added to the recommendation.
- Local fallback mode works without `OPENAI_API_KEY`.
- OpenAI API key is read from environment variables or Streamlit secrets only.
- Conversation log and points log structures are implemented.
- Public SKU mapping was generated.
- Public-facing files were scanned for old public brand leakage.

## Commands Run

```powershell
python sku_mapping.py
python -m py_compile app.py answer_engine.py sku_mapping.py brand_config.py
python test_qa_engine.py
python -c "import app, answer_engine, sku_mapping, brand_config; print('imports ok')"
```

## Results

- Public SKU generation: passed, 631 IOO lighting products.
- Python compile check: passed.
- App and helper imports: passed.
- Product QA regression tests: passed, 23/23.
- Answer-engine smoke tests returned IOO-only public SKUs with no public brand leakage.
- No `OPENAI_API_KEY` was present in the local environment, so fallback mode was verified.

## Smoke-Tested Questions

- `Detect scratches on reflective metal.`
  - Returned dark-field IOO candidates such as `IOO-DF-0001`.
- `Inspect transparent bottle edges.`
  - Returned backlight IOO candidates such as `IOO-BL-0001`.
- `PCB defect inspection lighting.`
  - Returned coaxial IOO candidates such as `IOO-CL-0001`.
- `I need lighting for line scan inspection.`
  - Returned close IOO bar / line-light candidates.
- `What if no product exactly matches my application?`
  - Returned closest IOO option and workaround language.

## Not Fully Run

- Local Streamlit launch could not be completed in this Codex runtime because
  the bundled package has no `streamlit.__main__` entry point. The app imports
  successfully and remains compatible with normal Streamlit Cloud deployment.
- OpenAI live-response mode was not tested because no API key was present.

## Current Known Limitations

- Image reasoning requires a future vision-enabled model.
- Product matches are closest-fit recommendations and need sample validation.
- Some product specifications are unavailable and are shown as `not available`.
- Session points are demo-only and reset if the session is cleared.
