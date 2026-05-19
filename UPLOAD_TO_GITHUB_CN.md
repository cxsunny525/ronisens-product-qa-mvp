# 如何把这个 MVP 放到 GitHub 并拿到测试网址

## 先说结论

GitHub 本身只能保存代码和数据文件，不能直接运行这个 Streamlit/Python 网站。

要让合伙人打开一个网页测试，推荐路径是：

1. 把本项目上传到 GitHub 仓库。
2. 用 Streamlit Cloud 连接这个 GitHub 仓库。
3. 在 Streamlit Cloud 设置 `APP_PASSWORD` 和可选的 `OPENAI_API_KEY`。
4. 部署后获得公网测试 URL。

GitHub Pages 不适合这个项目，因为它只能托管静态网页，不能运行 SQLite + Python + Streamlit 后端。

## 最快路径：GitHub + Streamlit Cloud

### 1. 新建 GitHub 仓库

打开：

```text
https://github.com/new
```

建议设置：

```text
Repository name: ronisens-product-qa-mvp
Visibility: Private
Initialize this repository with: 不勾选 README / .gitignore / license
```

### 2. 上传项目文件

你可以上传当前目录里的项目文件，或者使用我生成的压缩包：

```text
ronisens-product-qa-mvp.zip
```

上传时请确保包含这些关键文件：

```text
app.py
qa_engine.py
requirements.txt
canonical_fields.yaml
data_quality_report.md
unmapped_fields.md
README.md
DEPLOYMENT.md
HANDOFF_TO_PARTNER.md
DEPLOYMENT_RESULT.md
TEST_REPORT.md
eval_questions.md
data/tms_lite_full.db
data/exports/products_flat.csv
data/exports/product_specs.csv
data/exports/product_assets.csv
```

不要上传：

```text
.env
.streamlit/secrets.toml
logs/
.runtime_pkgs/
.packages/
__pycache__/
```

### 3. 用 Streamlit Cloud 部署

打开：

```text
https://share.streamlit.io/
```

操作：

1. Sign in with GitHub。
2. New app。
3. 选择仓库 `ronisens-product-qa-mvp`。
4. Branch 选择 `main`。
5. Main file path 填：

```text
app.py
```

### 4. 设置 Secrets

在 Streamlit Cloud 的 app settings 里设置 secrets：

```toml
APP_PASSWORD = "你想给合伙人的测试密码"
OPENAI_API_KEY = "可选，如果没有就删掉这一行"
```

没有 `OPENAI_API_KEY` 也可以运行，只是使用本地规则模式。

### 5. 部署并获得测试网址

点击 Deploy。成功后 Streamlit Cloud 会给你一个类似这样的公网 URL：

```text
https://ronisens-product-qa-mvp.streamlit.app/
```

把这个 URL 和 `APP_PASSWORD` 发给合伙人即可。

## 如果用 Render

Build command:

```text
pip install -r requirements.txt
```

Start command:

```text
streamlit run app.py --server.port $PORT --server.address 0.0.0.0
```

Environment variables:

```text
APP_PASSWORD
OPENAI_API_KEY
```

## 我回来后 5-10 分钟最短动作

1. GitHub 新建空仓库 `ronisens-product-qa-mvp`。
2. 上传 `ronisens-product-qa-mvp.zip` 解压后的文件。
3. Streamlit Cloud 选择这个仓库，入口文件 `app.py`。
4. 设置 `APP_PASSWORD`。
5. 点击 Deploy，拿到测试 URL。

