# IOO Lighting AI Deployment

## Local Run

```powershell
pip install -r requirements.txt
python sku_mapping.py
streamlit run app.py
```

## Streamlit Cloud

1. Push the project to GitHub.
2. Create or open the Streamlit app.
3. Set the app file to `app.py`.
4. Open App -> Settings -> Secrets.
5. Add:

```toml
OPENAI_API_KEY = "your_api_key_here"
APP_PASSWORD = "optional_test_password"
```

`OPENAI_API_KEY` is optional. Without it, the app runs in local fallback mode.

## Render

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
streamlit run app.py --server.port $PORT --server.address 0.0.0.0
```

Environment variables:

- `OPENAI_API_KEY` optional
- `APP_PASSWORD` optional but recommended for private demos

## Files Required For Deployment

- `app.py`
- `answer_engine.py`
- `knowledge_engine.py`
- `sku_mapping.py`
- `brand_config.py`
- `config/brand_config.yaml`
- `public_products.csv`
- `ioo_sku_mapping.csv`
- `data/ioo_product_test.db`
- `requirements.txt`

## Public UI Safety

Before deployment, confirm:

- The public page only shows IOO.
- Product cards display public IOO SKUs.
- Private supplier/source URLs do not appear in the UI.
- API keys are only stored in secrets or environment variables.
