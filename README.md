# Ronisens Product QA MVP

Ronisens Product QA MVP is a Streamlit web application for asking questions
against the current TMS Lite product database. It is designed for remote partner
testing, early machine-vision lighting selection, and competitive product
research.

The app is grounded in local database records. It must not invent product
models, voltages, wattages, dimensions, datasheet URLs, or source claims. When a
field is missing, the app should say `not available` or `not available in the
current database`.

## Current Data Scope

Current database coverage: TMS Lite only.

SQLite database:

- `data/tms_lite_full.db`

Current database statistics:

| Table | Count |
| --- | ---: |
| `brands` | 1 |
| `product_families` | 175 |
| `products` | 654 |
| `product_specs` | 6712 |
| `product_assets` | 2910 |
| `crawl_pages` | 726 |

CSV exports:

- `data/exports/products_flat.csv`
- `data/exports/product_specs.csv`
- `data/exports/product_assets.csv`

The app uses SQLite first. If SQLite cannot be loaded, `qa_engine.py` falls back
to the CSV exports.

## What The MVP Can Do

- Model lookup: check whether a TMS Lite model exists in the current database.
- Parameter lookup: show voltage, power, current, dimensions, weight, and raw specs when recorded.
- Datasheet/source lookup: show product URL and recorded datasheet/document links.
- Parameter filtering: search for 24V products, red lights, ring lights, coaxial lights, datasheet-backed records, and similar queries.
- Product comparison: compare known fields across several models.
- Data quality questions: show missing fields and products missing datasheet links.
- Preliminary selection guidance: suggest candidate light types and database-backed product candidates for applications such as metal scratch inspection, transparent bottle edge detection, PCB inspection, and backlight inspection.

## What The MVP Cannot Do Yet

- It does not cover brands beyond TMS Lite.
- It does not guarantee final PDF resolution for all OneDrive/FutureIP links.
- It does not provide pricing, inventory, lead time, or lifecycle status.
- It does not replace sample testing or optical engineering validation.
- It cannot answer questions using data not present in the current database.

## Local Run

Create a Python environment, then install dependencies:

```powershell
pip install -r requirements.txt
```

Run the Streamlit app:

```powershell
streamlit run app.py
```

If you are using the bundled Codex Python runtime on this machine:

```powershell
& 'C:\Users\cxsun\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m streamlit run app.py
```

## Environment Variables

Create a local `.env` file only for local development. Do not commit it.

```text
OPENAI_API_KEY=
APP_PASSWORD=
```

`APP_PASSWORD`:

- Recommended for any public test URL.
- If not set, the app allows entry in development mode and shows a warning.

`OPENAI_API_KEY`:

- Optional.
- If set, the app may use OpenAI to polish grounded local answers.
- If not set, the app runs in local keyword/rule-based fallback mode.

Secrets must never be written into source code or committed to Git.

## Testing

Run the core engine tests:

```powershell
python test_qa_engine.py
```

If `pytest` is installed:

```powershell
python -m pytest
```

The evaluation question set is in:

- `eval_questions.md`

## Quality And Field Dictionary

Data quality report:

- `data_quality_report.md`

Canonical field dictionary:

- `canonical_fields.yaml`

Unmapped raw fields:

- `unmapped_fields.md`

The field dictionary is intended for future adapters for CCS, OPT, Keyence,
Smart Vision Lights, Basler, and other machine-vision suppliers.

## Feedback Collection

The app includes a feedback text box. Feedback is written to:

- `logs/feedback.csv`

Fields:

- `timestamp`
- `question`
- `answer_summary`
- `confidence`
- `mode`
- `feedback`

`logs/` is ignored by Git.

## Streamlit Cloud Deployment

1. Push this repo to GitHub.
2. Open Streamlit Cloud.
3. Create a new app from the GitHub repo.
4. Select `app.py` as the app file.
5. Add secrets:

```toml
APP_PASSWORD = "choose-a-test-password"
OPENAI_API_KEY = "optional"
```

6. Deploy and copy the app URL.

The database file `data/tms_lite_full.db` is intentionally small enough to keep
in the repo for this MVP.

## Render Deployment

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
streamlit run app.py --server.port $PORT --server.address 0.0.0.0
```

Environment variables:

- `APP_PASSWORD`
- `OPENAI_API_KEY` optional

## How To Give This To A Partner

1. Deploy to Streamlit Cloud or Render.
2. Set `APP_PASSWORD`.
3. Send the partner:
   - test URL
   - password
   - `HANDOFF_TO_PARTNER.md`
4. Ask them to try questions from `eval_questions.md`.
5. Review `logs/feedback.csv` after testing.

## How To Add A Second Brand

1. Keep the existing schema.
2. Add a new collector/adapter that writes into `brands`, `product_families`,
   `products`, `product_specs`, and `product_assets`.
3. Map raw vendor fields to `canonical_fields.yaml`.
4. Put uncertain raw fields into `unmapped_fields.md`.
5. Run `test_qa_engine.py` and spot-check sources before exposing the data.

## How To Update The Database

For TMS Lite, the previous crawler is still available in:

- `ivdb/tms_lite_collector.py`

Do not rerun the crawler unless intentionally refreshing the database. The
current MVP should use `data/tms_lite_full.db` as-is.

## Roadmap

1. Review noisy extracted models and duplicate model records.
2. Resolve redirected datasheet/catalogue URLs to final file URLs.
3. Add family-specific dimension mapping for A/B/C and diameter fields.
4. Add explicit application tags and light-type tags.
5. Add the second brand adapter.
6. Add vector/RAG retrieval over datasheet text.
7. Add authenticated hosted feedback storage.
