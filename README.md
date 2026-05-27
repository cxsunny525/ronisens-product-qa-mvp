# IOO Lighting AI

IOO Lighting AI is a single-brand machine vision lighting selection assistant for
industrial inspection. It explains lighting strategy first, then recommends the
closest available IOO lighting configurations from the current IOO product
catalog.

Brand statement:

Designed in California. Manufactured in Malaysia.

## Product Strategy

- Public brand: IOO
- Public app name: IOO Lighting AI
- Public website/domain reference: ioo.pro
- Public product recommendations use IOO public SKUs only.
- Supplier and original source details are private/internal and are not shown in
  the public UI.

The current public catalog is generated from internal product records into:

- `public_products.csv`
- `ioo_sku_mapping.csv`
- `SKU_MAPPING_REPORT.md`

Public SKU examples:

- `IOO-RL-0001`: ring light candidate
- `IOO-BL-0001`: backlight candidate
- `IOO-CL-0001`: coaxial / in-line candidate
- `IOO-BAR-0001`: bar light candidate
- `IOO-DF-0001`: dark-field / low-angle candidate

## How Answers Work

The answer flow is:

1. Understand the inspection challenge.
2. Search the source-linked lighting knowledge base.
3. Retrieve the closest IOO product configurations.
4. Compose a grounded recommendation.
5. Ask for missing information such as material, defect size, field of view, and
   working distance.

If there is no exact fit, the app still recommends the closest IOO option and
labels it as a close fit or workaround fit. Final selection should be verified
with sample testing.

## OpenAI API

The app runs without an API key in local fallback mode.

To enable full AI responses on Streamlit Cloud:

1. Open Streamlit Cloud.
2. Go to App -> Settings -> Secrets.
3. Add:

```toml
OPENAI_API_KEY = "your_api_key_here"
```

Do not write API keys into code or commit them to GitHub.

The model name is configured in:

- `config/brand_config.yaml`

Default:

```yaml
openai:
  env_var: "OPENAI_API_KEY"
  model: "gpt-4.1-mini"
  fallback_enabled: true
```

## Local Run

```powershell
pip install -r requirements.txt
python sku_mapping.py
streamlit run app.py
```

If no `OPENAI_API_KEY` is configured, the page displays local fallback mode and
still works.

## Logs

Session logs are written locally:

- `logs/conversation_log.csv`
- `logs/conversation_points.csv`
- `logs/feedback.csv`

The points system is session-based and does not require login.

## IOO Insight Points

The demo awards lightweight session points:

- Valid question: +5
- Upload image, sketch, PDF, or note: +10
- Add useful parameters such as material, field of view, or working distance: +5
- Feedback: +5
- Follow-up in the same inspection case: +3

Points do not have a fixed cash value. Potential future benefits may include
sample credits, consultation priority, or pilot order support.

## Updating The IOO Product Catalog

1. Update the internal product database.
2. Run:

```powershell
python sku_mapping.py
```

3. Review:

- `public_products.csv`
- `ioo_sku_mapping.csv`
- `SKU_MAPPING_REPORT.md`

4. Confirm public SKUs and descriptions do not expose private supplier/source
   details.

## Current Limitations

- Image reasoning is not enabled unless a vision model is configured.
- Uploaded images are displayed as context only.
- Product recommendations are closest-fit suggestions, not guaranteed matches.
- Final selection should be verified with sample images and physical testing.
- Supplier/internal source information is private.
- Some product specifications are not available in the current catalog and are
  shown as `not available`.

## Edmund Optics Knowledge Import

Edmund Optics knowledge import tooling exists for internal knowledge-base
expansion:

```powershell
python crawl_edmund_knowledge.py --dry-run --limit 20
python crawl_edmund_knowledge.py --limit 150
python import_edmund_knowledge.py
python extract_edmund_knowledge.py
python knowledge_quality_edmund.py
```

The crawler respects robots rules and a minimum 10 second crawl delay. Public UI
shows source-linked summaries and URLs only; it should not display full articles
as IOO-authored content.
