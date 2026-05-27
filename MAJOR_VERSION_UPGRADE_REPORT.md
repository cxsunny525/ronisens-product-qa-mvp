# Major Version Upgrade Report

## Summary

The project has been upgraded into a single-brand IOO Lighting AI experience.
The public app is now positioned as an IOO machine vision lighting selection
assistant rather than a multi-vendor database test tool.

## Completion Checklist

1. Single-brand IOO conversion: completed.
2. Public UI removal of previous supplier/vendor names: completed in the new
   public app and public docs.
3. Public UI removal of non-IOO product vendors: completed in the new public app
   and public docs.
4. Public SKU mapping: completed.
5. IOO public products generated: 631.
6. Search-engine-style UI: completed.
7. OpenAI API integration: completed.
8. `OPENAI_API_KEY` location: set in environment variables or Streamlit Cloud
   App -> Settings -> Secrets.
9. Knowledge-first, product-second answer logic: completed.
10. IOO Insight Points: completed.
11. Conversation history: completed for latest 8 turns.
12. Upload entry: completed for image, PDF, text, and markdown.
13. Closest-fit recommendation logic: completed.

## Generated Catalog Files

- `public_products.csv`
- `ioo_sku_mapping.csv`
- `SKU_MAPPING_REPORT.md`

## OpenAI Setup

Set in Streamlit Cloud secrets:

```toml
OPENAI_API_KEY = "your_api_key_here"
```

If no key is configured, the app runs in local fallback mode.

## Local Test Results

- `python sku_mapping.py`: generated 631 public IOO lighting products.
- `python -m py_compile app.py answer_engine.py sku_mapping.py brand_config.py`: passed.
- `python answer_engine.py "Detect scratches on reflective metal."`: returned IOO-only product recommendations and public knowledge sources.
- `python test_qa_engine.py`: passed, 23/23.
- Public leakage check over `app.py`, README, deployment docs, public CSVs, and reports: passed.
- Local Streamlit launch in this Codex runtime is blocked by the bundled package entry point; use normal `streamlit run app.py` in Streamlit Cloud or a standard local environment.

## Deployment Recommendation

Deploy to Streamlit after uploading the updated files and configuring secrets.

## Current Biggest Risk

The public IOO SKU mapping is a first-pass mapping from internal records. It
should be reviewed before customer-facing quotation or formal datasheet use.

## Next Steps

1. Manually review public SKU naming and category grouping.
2. Add official IOO product imagery and datasheets.
3. Add vision-model image reasoning for uploaded samples.
4. Add login/account persistence if points need to survive browser refresh.
5. Review source licenses for knowledge-base content before broad public use.
