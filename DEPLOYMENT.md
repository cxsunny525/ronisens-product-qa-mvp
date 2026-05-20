# Deployment Guide

## A. Local Run

Install dependencies:

```bash
pip install -r requirements.txt
```

Run:

```bash
streamlit run app.py
```

Open the local URL printed by Streamlit, usually:

```text
http://localhost:8501
```

Optional local environment variables:

```bash
OPENAI_API_KEY=
APP_PASSWORD=
```

If `APP_PASSWORD` is not set, the app runs in development mode and displays a
warning.

## B. Streamlit Cloud Deployment

1. Push this project to a GitHub repository, ideally `ioo-product-qa-mvp`.
2. Go to Streamlit Cloud.
3. Create a new app.
4. Select the GitHub repository.
5. Set main file path to:

```text
app.py
```

6. Configure secrets in Streamlit Cloud:

```toml
APP_PASSWORD = "choose-a-test-password"
OPENAI_API_KEY = "optional-openai-key"
```

`OPENAI_API_KEY` is optional. If it is absent, the app still works in local
fallback mode.

7. Deploy.
8. Copy the public app URL and add it to `DEPLOYMENT_RESULT.md` and
   `HANDOFF_TO_PARTNER.md`.

## C. Render Deployment

Create a new Render Web Service from the GitHub repository.

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
streamlit run app.py --server.port $PORT --server.address 0.0.0.0
```

Environment variables:

```text
APP_PASSWORD=choose-a-test-password
OPENAI_API_KEY=optional-openai-key
```

The app listens on Render's `$PORT`.

## Multi-Brand Update

The deployed app should include `data/ioo_product_test.db`. This unified test database preserves TMS Lite records and adds the Advanced Illumination pilot import. Keep `data/tms_lite_full.db` in the repo as the untouched source database.

After pushing the update to GitHub, Streamlit Cloud should redeploy automatically. In the app, confirm the sidebar shows:

- Total brands: 2
- TMS Lite products: 654
- Advanced Illumination products: 13

If the hosted app still shows one brand, reboot the Streamlit app and confirm `data/ioo_product_test.db` was uploaded with the repository.

## D. Fast Manual Deployment Path

If automatic deployment was not completed, the fastest path when you return is:

1. Create a private GitHub repo named `ioo-product-qa-mvp`.
2. Push this folder to that repo.
3. Open Streamlit Cloud and select the repo.
4. Set `app.py` as the entrypoint.
5. Add `APP_PASSWORD` in secrets.
6. Optionally add `OPENAI_API_KEY`.
7. Click deploy.

Expected time: 5-10 minutes after GitHub and Streamlit Cloud access are ready.

## Notes

- Do not commit `.env` or `.streamlit/secrets.toml`.
- Keep `data/tms_lite_full.db` in the repo for this MVP; it is small enough for
  normal Git hosting.
- If a future database becomes too large, use compressed CSV, Git LFS, external
  object storage, Supabase, or another hosted database.
