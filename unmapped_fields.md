# Unmapped Raw Fields

These raw `product_specs.spec_name` values were found in `tms_lite_full.db` but
should not be aggressively normalized without more family-specific context.

The MVP keeps them in `product_specs` and shows them as source evidence when
needed. Future cleanup should map these per product family after inspecting the
datasheet table layout.

| Raw field | Count | Reason |
| --- | ---: | --- |
| `extra_4` | 409 | Often generated from wide datasheet/link tables; may mean color, datasheet variant, or table overflow depending on family. |
| `extra_5` | 316 | Same issue as `extra_4`. |
| `extra_6` | 282 | Same issue as `extra_4`. |
| `extra_7` | 244 | Same issue as `extra_4`. |
| `extra_8` | 5 | Same issue as `extra_4`. |
| `A (mm)` | 308 | Dimension label is real but vendor-specific; not always length/width/height. |
| `B (mm)` | 303 | Dimension label is real but vendor-specific. |
| `C (mm)` | 259 | Dimension label is real but vendor-specific. |
| `D (mm)` | 241 | Dimension label is real but vendor-specific. |
| `E (mm)` | 214 | Dimension label is real but vendor-specific. |
| `F (mm)` | 149 | Dimension label is real but vendor-specific. |
| `G (mm)` | 122 | Dimension label is real but vendor-specific. |
| `H (mm)` | 68 | Dimension label is real but vendor-specific. |
| `I (mm)` | 18 | Dimension label is real but vendor-specific. |
| `J (mm)` | 6 | Dimension label is real but vendor-specific. |
| `K (mm)` | 3 | Dimension label is real but vendor-specific. |
| `D° (mm)` | 24 | Appears to be an angle/dimension hybrid; needs product drawing context. |
| `E° (mm)` | 10 | Appears to be an angle/dimension hybrid; needs product drawing context. |
| `F row (mm)` | 23 | Row/dimension label needs family-specific interpretation. |
| `F Row (mm)` | 17 | Row/dimension label needs family-specific interpretation. |
| `E (Row) (mm)` | 2 | Row/dimension label needs family-specific interpretation. |

Known mapped fields from the current database include:

- `Datasheet`, `DATASHEET (ID)` -> `datasheet_url`
- `Drawing (2D)`, `DXF (2D)`, `PDF (2D)`, `2D Drawing`, `Drawing` -> document/asset metadata
- `STEP (3D)`, `STEP(3D)`, `STEP File` -> 3D asset metadata
- `Voltage (V) / Watt (W)`, `Voltage (V)/Watt (W)`, `Voltage (V) /Watt (W)` -> `voltage_v`, `power_w`
- `Current` -> `current_a` or source `current_ma`
- `Weight (g)`, `Weight` -> `weight_g`
- `Colour`, `COLOUR`, `Color`, `RGBW`, `IR`, `UV` -> `color` / `wavelength_nm`
- `Tap Hole (mm)`, `TapHole (mm)`, `Tap Hole E (mm)`, `Tap Hole F (mm)` -> `mounting`
- `Drive Mode` -> `strobe_mode`


## Advanced Illumination pilot unmapped fields
- Advanced Illumination: Intensity
- Advanced Illumination: Lead Time
- Advanced Illumination: Light Conditioning
- Advanced Illumination: Sizes
