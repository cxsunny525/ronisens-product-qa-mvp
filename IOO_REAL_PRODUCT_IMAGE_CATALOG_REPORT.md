# IOO Real Product Image Catalog Report

- Products mapped: 654
- Image URLs discovered: 654
- Real image files downloaded: 0
- Images included in public ZIP: 0
- Public CSV: `C:\Users\cxsun\Documents\Codex\2026-05-18\tms-lite-com-ai\data\downloads\ioo_public_product_catalog_real_images.csv`
- Public ZIP: `C:\Users\cxsun\Documents\Codex\2026-05-18\tms-lite-com-ai\data\downloads\ioo_public_product_catalog_real_images.zip`
- Private source manifest: `C:\Users\cxsun\Documents\Codex\2026-05-18\tms-lite-com-ai\data\internal\ioo_tms_real_image_manifest_private.csv`

## Download Status

- pending_download: 654

## Notes

- Public CSV and ZIP do not expose source website URLs or internal supplier fields.
- The private manifest keeps source URLs for internal traceability only.
- If downloads fail due local network restrictions, rerun this script in a network-enabled environment.

Command:

`python build_ioo_real_image_catalog.py --download --delay 1.5`