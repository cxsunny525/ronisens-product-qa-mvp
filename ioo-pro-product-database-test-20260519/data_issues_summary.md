# Data Issues Summary

Generated: 2026-05-19T09:25:19

Total issues: 7132

## By Severity

- high: 388
- medium: 3161
- low: 3583

## By Issue Type

- missing_datasheet: 64
- missing_product_url: 0
- missing_voltage: 187
- missing_power: 187
- missing_color: 560
- missing_category: 183
- duplicate_model: 201
- unmapped_field: 3023
- unparsed_unit: 2667
- broken_asset_url: 0
- suspicious_value: 60
- empty_specs: 0

## Recommended Fix Order

1. Fix high-severity duplicate models, missing product URLs, malformed asset URLs, and missing voltage fields.
2. Review missing datasheets and missing category/light-type mappings.
3. Normalize unit parsing and map the highest-volume unmapped fields.
4. Use manual_overrides.yaml only for human-verified corrections that should not alter the source database.
