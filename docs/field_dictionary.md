# 工业视觉产品统一字段字典

这份字段字典用于把不同品牌的工业视觉产品统一进一个产品数据库。
第一阶段覆盖照明、控制器、镜头/光学件、测试台、附件；后续可扩展到相机、
镜头、采集卡、工控机、线缆和软件。

## 设计原则

- 每个产品必须保留来源 URL 和品牌，方便追溯。
- 每个品牌的特殊参数不要硬塞进主表，放入 `product_specs` 长表。
- 主表只放跨品牌稳定字段，便于搜索、筛选、去重和 AI 推荐。
- 字段长度要稳定，文本超长内容放说明表或原始文档，不放核心字段。
- 同一型号可能有颜色、波长、驱动方式、资料页差异，先保留来源，再做人工/规则合并。

## 核心实体

| 表 | 用途 | 关键字段 |
| --- | --- | --- |
| `brands` | 品牌/制造商 | `name`, `website`, `country` |
| `product_families` | 系列或产品页面 | `family_name`, `series_code`, `product_type`, `category_path`, `source_url` |
| `products` | 型号级产品 | `model`, `product_type`, `voltage_v`, `power_w`, `current_ma`, `dimensions_mm_json` |
| `product_specs` | 参数长表 | `spec_name`, `raw_value`, `normalized_value`, `unit` |
| `product_assets` | 文档和资料 | `asset_type`, `title`, `url`, `local_path`, `source_url` |
| `crawl_pages` | 抓取日志 | `url`, `status_code`, `raw_path`, `error` |

## 产品主表字段

| 字段 | 建议长度 | 必填 | 说明 |
| --- | ---: | --- | --- |
| `brand` | 80 | 是 | 品牌名称，如 TMS LITE、CCS、OPT、Basler |
| `product_type` | 80 | 是 | 统一产品类型，见下方枚举 |
| `family_name` | 160 | 是 | 系列名或产品页标题 |
| `series_code` | 120 | 否 | 系列代码，如 CAS2、BHP、LC-20 |
| `model` | 180 | 是 | 原始型号，保留厂商写法 |
| `model_normalized` | 180 | 是 | 大写、去空格后的型号，用于去重和搜索 |
| `variant_code` | 180 | 否 | 颜色、波长、接口等变体码 |
| `title` | 240 | 否 | 页面标题或产品名称 |
| `color_options` | 255 | 否 | Red/Green/Blue/White/RGB/RGBW/IR/UV 等 |
| `wavelength_nm` | 120 | 否 | 波长，建议保留原文并在长表中进一步标准化 |
| `voltage_v` | 120 | 否 | 电压，如 12V、24V、5V |
| `power_w` | 120 | 否 | 功率，如 3.24W / 3.36W |
| `current_ma` | 120 | 否 | 电流，如 270mA |
| `weight_g` | 80 | 否 | 重量，单位 g |
| `dimensions_mm_json` | JSON | 否 | 尺寸键值，如 A/B/C/D 或 W/H/L，单位 mm |
| `source_url` | 1000 | 是 | 来源页面 |
| `search_text` | TEXT | 否 | 为搜索/AI 检索拼接的文本 |

## 统一产品类型

| 枚举 | 中文 | 适用范围 |
| --- | --- | --- |
| `illumination` | 机器视觉光源 | 环形、条形、背光、同轴、穹顶、低角度、UV/IR/SWIR、多波长 |
| `controller` | 光源控制器 | 模拟、数字、频闪、以太网/串口控制器 |
| `lens_or_optics` | 镜头/光学件 | 镜头、滤光片、液态镜头、转接环 |
| `camera_solution` | 相机方案 | 智能相机、相机+光源一体方案 |
| `station_or_mounting` | 测试台/安装件 | MVM、PTS、支架、测试平台 |
| `demo_kit` | Demo Kit | 演示套件、样机组合 |
| `accessory` | 附件 | 线缆、支架、安装板、电源等 |
| `software` | 软件/SDK | 控制软件、SDK、示例代码 |
| `industrial_vision_product` | 未细分工业视觉产品 | 暂未能稳定归类的产品 |

## 资料类型

| `asset_type` | 中文 | 说明 |
| --- | --- | --- |
| `datasheet` | 数据表 | PDF 或产品规格说明 |
| `2d_drawing` | 2D 图纸 | DXF/DWG/PDF 图纸 |
| `3d_model` | 3D 模型 | STEP/STP/3D 预览 |
| `catalogue` | 产品目录 | 年度 catalog 或综合目录 |
| `software` | 软件 | 安装包、源码、SDK 下载 |
| `application_note` | 应用说明 | 应用案例、对比测试、白皮书 |
| `image` | 图片 | 产品图、结构图 |
| `link` | 普通链接 | 未能识别类型的资料链接 |

## 参数标准化规则

| 原始字段 | 标准字段 | 处理方式 |
| --- | --- | --- |
| `Voltage (V) / Watt (W)` | `voltage_v`, `power_w` | 抽取 V 和 W，同时保留原始字段到 `product_specs` |
| `Current` | `current_ma` | 保留原文，后续可拆成 min/max/current_per_channel |
| `Weight (g)` | `weight_g` | 保留数值和单位 |
| `COLOUR` / `COLOR` | `color_options` | 保留颜色文本 |
| `Dimensions (mm)` | `dimensions_mm_json` | 按 A/B/C/D 或 W/H/L 存 JSON |
| `Drawing` / `Datasheet` / `STEP` | `product_assets` | 存资料链接，不进入型号字段 |

## AI 选型需要的额外字段

为了从“产品库”升级到“选型 AI”，建议下一阶段补这些字段：

| 字段 | 说明 |
| --- | --- |
| `lighting_geometry` | ring/bar/backlight/coaxial/dome/low_angle/spot/line 等 |
| `illumination_mode` | bright_field/dark_field/backlight/diffuse/coaxial/multi_angle |
| `suitable_applications` | OCR、划痕、边缘、透明物、金属表面、尺寸测量等 |
| `target_materials` | metal/glass/plastic/film/label/semiconductor 等 |
| `inspection_goal` | defect_detection/measurement/positioning/recognition |
| `compatibility` | 推荐控制器、电源、相机、镜头 |
| `availability_status` | active/discontinued/coming_soon |
| `confidence_score` | 数据可信度，来源页面高于推断字段 |

## 验收门槛

- 每个品牌至少 95% 产品有 `brand`、`model`、`family_name`、`product_type`、`source_url`。
- 照明产品至少 60% 有电压、功率、电流、尺寸之一。
- 每个系列至少保留一个来源页面或 datasheet/catalogue 链接。
- 重要字段必须能回溯到网页、PDF 或目录来源。
