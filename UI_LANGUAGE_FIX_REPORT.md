# UI Language Fix Report

Date: 2026-05-27

## Files Updated

- `app.py`
- `answer_engine.py`
- `product_search.py`

## What Changed

- Added `detect_user_language(text)` to classify user input as `zh` or `en`.
- `answer_question()` now returns `language`.
- Streamlit session state stores the most recent user language.
- Added `UI_TEXT` dictionary for the main user-facing labels.
- Localized key answer sections:
  - Ask IOO / 询问 IOO
  - Direct recommendation / 直接建议
  - Lighting strategy / 打光策略
  - Product shortlist / 产品候选
  - Closest IOO product options / 最接近的 IOO 产品选项
  - Missing information / 还需要补充的信息
  - Sources / Basis / 依据来源
  - Save / 保存
  - Compare / 对比
  - Details / 详情
  - Spec sheet / 规格书

## Product Card Localization

- Added light type display mapping for Chinese:
  - bar light -> 条形光源
  - ring light -> 环形光源
  - backlight -> 背光源
  - coaxial light -> 同轴光源
  - dome / diffuse -> 穹顶光 / 漫射光源
  - dark field -> 暗场光源
  - line scan -> 线扫光源
  - UV -> 紫外光源
  - IR -> 红外光源
- Added fit type mapping:
  - Exact fit -> 精确匹配
  - Close fit -> 接近匹配
  - Workaround fit -> 替代方案匹配

## Verification

- Chinese questions now return `language = zh`.
- English questions return `language = en`.
- Product model numbers remain unchanged.
- Public product recommendations remain database-backed.

