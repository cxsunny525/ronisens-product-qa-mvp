# Data Quality Report

Database reviewed: `data/tms_lite_full.db`

## Summary

| Metric | Count |
| --- | ---: |
| Brands | 1 |
| Product families | 175 |
| Products | 654 |
| Product specs | 6712 |
| Product assets | 2910 |
| Crawl pages | 726 |

The current database is suitable for a first Product QA MVP. It has enough
product, parameter, source URL, and document-link coverage to support model
lookup, parameter filtering, basic comparison, missing-field inspection, and
preliminary lighting-selection guidance. It is not yet complete enough for final
engineering recommendations without human validation.

## Schema Summary

| Table | Purpose |
| --- | --- |
| `brands` | Manufacturer metadata |
| `product_families` | Series/page-level product grouping |
| `products` | Model-level product records |
| `product_specs` | Long-form raw and normalized spec key-value records |
| `product_assets` | Datasheets, drawings, 3D files, catalogues, and links |
| `crawl_pages` | Crawl traceability and raw-page references |

## Field Presence

| Field | Missing | Coverage |
| --- | ---: | ---: |
| `model` | 0 | 100.0% |
| `product_type` | 0 | 100.0% |
| `source_url` / `product_url` | 0 | 100.0% |
| `voltage_v` | 187 | 71.4% |
| `power_w` | 187 | 71.4% |
| `current_ma` | 188 | 71.3% |
| `weight_g` | 191 | 70.8% |
| `dimensions_mm_json` | 218 | 66.7% |
| `color_options` | 565 | 13.6% |
| `wavelength_nm` | 649 | 0.8% |

## URL Coverage

| URL type | Product count | Coverage |
| --- | ---: | ---: |
| Product/source URL | 654 | 100.0% |
| Product-specific datasheet URL | 475 | 72.6% |
| Any product-specific asset | 525 | 80.3% |

Note: some datasheet and catalogue links point to OneDrive/FutureIP redirect
pages. The MVP shows those URLs as source evidence but does not claim they are
resolved final PDF URLs.

## Duplicate Model Summary

There are 93 normalized model values that appear on more than one source page.
Some are normal cross-listings; others are extraction cleanup candidates.

Most repeated examples:

| Model normalized | Count |
| --- | ---: |
| `UV385` | 5 |
| `UV395` | 5 |
| `UV405` | 5 |
| `CAS2-00-040-X-X` | 4 |
| `CAS2-00-025-X-X` | 3 |
| `LLA-60-090-2-X` | 3 |
| `LSW-15-070-3-X` | 3 |
| `R` | 3 |

The `R` duplicate is likely a noisy extraction artifact and should be reviewed.

## Most Common Spec Fields

| Raw spec field | Count |
| --- | ---: |
| `Datasheet` | 472 |
| `Current` | 468 |
| `Drawing (2D)` | 465 |
| `Weight (g)` | 462 |
| `STEP (3D)` | 461 |
| `Voltage (V) / Watt (W)` | 441 |
| `extra_4` | 409 |
| `extra_5` | 316 |
| `A (mm)` | 308 |
| `B (mm)` | 303 |
| `extra_6` | 282 |
| `C (mm)` | 259 |
| `extra_7` | 244 |
| `D (mm)` | 241 |
| `E (mm)` | 214 |

## Most Confusing Raw Field Names

- `extra_4`, `extra_5`, `extra_6`, `extra_7`: created from wide vendor tables, often mixing color/datasheet/variant columns.
- `A (mm)` through `K (mm)`: real dimensions but the meaning changes by drawing/family.
- `ØA (mm)` through `ØJ (mm)`: diameter-style dimensions that require family-specific interpretation.
- `D° (mm)` and `E° (mm)`: angle/dimension hybrid labels.
- `Product Page Title`: useful as page evidence, not a technical parameter.

## MVP Readiness

Ready for MVP: yes.

Good enough for:

- model lookup
- datasheet/source lookup
- 24V/color/light-type style filtering
- basic spec comparison
- missing-field analysis
- preliminary lighting selection grounded in database records

Not yet good enough for:

- final product selection without sample testing
- exact dimension semantics across all families
- guaranteed final datasheet PDF downloads
- cross-brand comparison
- pricing, availability, lead time, or lifecycle status

## Recommended Fixes

1. Review and suppress noisy short models such as `R`.
2. Build family-level dimension maps for `A/B/C/D` and `ØA/ØB/ØC`.
3. Resolve OneDrive/FutureIP datasheet and catalogue redirects to final file URLs where possible.
4. Add explicit `light_type` and `application_tags` fields from family names and source pages.
5. Add a second brand only after the canonical field dictionary is stable.
6. Keep all answer generation grounded in `products`, `product_specs`, and `product_assets`; never invent missing specs.
