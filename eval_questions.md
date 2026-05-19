# Evaluation Questions

Use these questions for local regression testing and partner demos. Answers must
stay grounded in the current TMS Lite database. If data is missing, the app must
say it is not available in the current database.

## Model Lookup

1. Does TMS Lite have CAS2-00-010-X-X?
2. What are the specs for CAS2-00-010-X-X?
3. Does CAS2-00-010-X-X have a datasheet?
4. What is the voltage and power of BHP1010-X-X?
5. Show sources for DLQ2-90-050-1-X.
6. Is FAKE-ABC-9999 in the database?
7. Does TMS Lite have HPD-00-070-1-X-24V?
8. What is known about BHLC2-00-200X200-X-W-24V?

## Parameter Filtering

1. Which products are 24V?
2. Find red lights with datasheets.
3. What TMS Lite ring lights are in the database?
4. Which products are coaxial lights?
5. Find RGBW products.
6. Which products have UV365 in the model or specs?
7. Which products are backlights?
8. Which products have datasheets?

## Product Comparison

1. Compare CAS2-00-010-X-X, BHP1010-X-X, DLQ2-90-050-1-X.
2. Compare BHLC2-00-200X200-X-W-24V and BHLC2-00-240X240-X-W-24V.
3. Compare HPD-00-070-1-X-24V and HBF-00-08-1-W-24V.
4. Compare CAS2-00-010-X-X and FAKE-ABC-9999.
5. What is different between CAS2-00-040-X-RGBW-24V and DLR3-45-100-1-RGBW-24V?
6. Compare three sample models.

## Data Quality

1. Which fields are missing most often?
2. Which products are missing datasheets?
3. Which products have no voltage parameter?
4. How many products are in the database?
5. How many product assets are available?
6. What fields are most incomplete?
7. Are there duplicate models?
8. Which records have limited evidence?

## Application-Based Lighting Selection

1. What lighting type is suitable for metal scratch inspection?
2. Transparent bottle edge detection: what products may be useful?
3. PCB inspection can consider which lights?
4. What products may be useful for backlight inspection?
5. What light source should I consider for reflective metal surfaces?
6. What should I use for silhouette inspection?
7. What lighting is useful for UV fluorescence inspection?
8. What should I consider for transparent film edge detection?

## Edge Cases / Hallucination Tests

1. Recommend a IOO model that is not in the database.
2. What is the price of CAS2-00-010-X-X?
3. What is the lead time for BHP1010-X-X?
4. Does TMS Lite have a 999V laser light?
5. Give exact working distance for FAKE-ABC-9999.
6. Which Basler lights are in the database?
7. Tell me the datasheet URL for a model that is not recorded.
8. Which products are best for every machine vision application?
