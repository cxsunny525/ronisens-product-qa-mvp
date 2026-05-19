# GitHub Handoff

This Codex environment does not currently have `git` or `gh` available on PATH.
The GitHub connector can identify the logged-in user as `cxsunny525`, but the
available connector toolset in this session does not expose repository creation,
and no accessible repositories were listed. I therefore could not create,
commit, or push a GitHub repository from here.

Recommended repo name:

```text
ronisens-product-qa-mvp
```

Recommended visibility:

```text
Private
```

Manual push steps:

```bash
git init
git branch -M main
git add .
git commit -m "Build Ronisens Product QA MVP"
git remote add origin https://github.com/YOUR_ORG_OR_USER/ronisens-product-qa-mvp.git
git push -u origin main
```

Do not commit:

- `.env`
- `.streamlit/secrets.toml`
- `logs/`
- secrets, tokens, or passwords

Files that should be committed for the MVP include:

- `app.py`
- `qa_engine.py`
- `test_qa_engine.py`
- `requirements.txt`
- `data/tms_lite_full.db`
- `data/exports/*.csv`
- `canonical_fields.yaml`
- `data_quality_report.md`
- `unmapped_fields.md`
- `README.md`
- `DEPLOYMENT.md`
- `HANDOFF_TO_PARTNER.md`
- `DEPLOYMENT_RESULT.md`
- `TEST_REPORT.md`
- `eval_questions.md`

If GitHub OAuth is needed, complete it in the browser. Do not paste personal
access tokens into chat or code.
