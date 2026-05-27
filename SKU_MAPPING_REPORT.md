# SKU Mapping Report

The public IOO catalog maps internal supplier records to IOO-only public SKUs.
Supplier names and source URLs are retained only as private/internal fields and should not be shown in the public UI.

- Public brand: IOO
- Public products generated: 631
- Mapping rows generated: 631

## Public SKU Pattern

- `IOO-RL-####`: ring light candidates
- `IOO-BL-####`: backlight candidates
- `IOO-CL-####`: coaxial / in-line candidates
- `IOO-BAR-####`: bar light candidates
- `IOO-LS-####`: line scan candidates
- `IOO-SP-####`: spot light candidates
- `IOO-DF-####`: dark-field / low-angle candidates
- `IOO-DM-####`: dome / diffuse candidates
- `IOO-LT-####`: uncategorized lighting candidates

## Light Type Distribution

- illumination: 212
- line_scan_light: 114
- backlight: 74
- coaxial_light: 63
- bar_light: 50
- dark_field: 45
- ring_light: 41
- spot_light: 20
- dome_light: 12

## Public UI Rule

The public UI should display `public_model` and `public_brand` only. Internal model, supplier, and private source URL fields are for internal review and debugging only.
