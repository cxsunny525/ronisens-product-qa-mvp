# Real Product Image Download Instructions

## What Is Done

- Extracted real product image source URLs from the locally saved original product-page HTML.
- Built a one-to-one mapping:
  - IOO `public_model`
  - internal OEM model
  - original product id
  - real source image URL
- Products mapped: 654.
- Real image URLs discovered: 654.

## Files

- Private source manifest:
  `data/internal/ioo_tms_real_image_manifest_private.csv`
- Public CSV for website download:
  `data/downloads/ioo_public_product_catalog_real_images.csv`
- Public ZIP path:
  `data/downloads/ioo_public_product_catalog_real_images.zip`
- Downloader script:
  `build_ioo_real_image_catalog.py`

## Important

The current Codex runtime cannot open outbound network sockets, so it cannot download the image binaries directly here. The downloader is ready, but it must be run on a machine or CI environment with internet access.

## Run This To Download Real Images

```powershell
cd C:\Users\cxsun\Documents\Codex\2026-05-18\tms-lite-com-ai
python build_ioo_real_image_catalog.py --download --delay 1.5
```

The script will:

1. Read `data/tms_lite_full.db` and `data/ioo_products.db`.
2. Match every original product to its IOO public model.
3. Extract the real product image URL from saved product-page HTML.
4. Download the image into `data/product_images_real/`.
5. Rebuild:
   - `data/downloads/ioo_public_product_catalog_real_images.csv`
   - `data/downloads/ioo_public_product_catalog_real_images.zip`

For compatibility with older download links, after a successful image download you may also copy the regenerated real-image files over the older catalog filenames:

```powershell
copy data\downloads\ioo_public_product_catalog_real_images.csv data\downloads\ioo_public_product_catalog.csv
copy data\downloads\ioo_public_product_catalog_real_images.zip data\downloads\ioo_public_product_catalog_with_images.zip
```

## Public Safety

The public CSV and ZIP do not expose original source URLs, supplier fields, or internal model fields. Those stay only in:

`data/internal/ioo_tms_real_image_manifest_private.csv`
