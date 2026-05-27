# IOO redesign package — Soft Light Lab

This package contains a reusable UI direction for the next version of ioo.pro.

This revision removes the heavy dark theme and replaces it with a light, low-glare laboratory interface: mist white surfaces, pale blue-green focus areas, soft graphite text, teal optical accents, and warm amber credit/reward cues.

## Files

- `index.html` - responsive desktop/mobile prototype.
- `styles/tokens.css` - CSS custom properties for brand colors, typography, radius, and motion.
- `styles/ui.css` - prototype layout and component styling.
- `design-tokens.json` - reusable design token source for design/dev systems.
- `assets/logo-ioo.svg` - square logo source.
- `assets/logo-ioo-mark.svg` - compact app/favicon-style mark.
- `assets/logo-ioo-horizontal.svg` - horizontal brand lockup.
- `assets/product-light-bar.svg` - product illustration placeholder.
- `assets/product-coaxial.svg` - product illustration placeholder.
- `assets/product-dome.svg` - product illustration placeholder.
- `assets/mockup-desktop.svg` - desktop UI mockup source.
- `assets/mockup-mobile.svg` - mobile UI mockup source.
- `docs/ux-rationale.md` - psychology and product rationale.
- `docs/brand-guide.md` - mini brand guide.

## How to preview

Open `index.html` in a browser. Resize the browser window to see the mobile and tablet behavior.

## Implementation notes

This prototype is static HTML/CSS. It can be converted into:

- Streamlit custom components
- React/Next.js pages
- Figma import references using SVG and token files
- A design system package for future IOO product pages

## Public-facing data rule

Product cards should display only IOO public model names and public-facing links. Supplier names, internal supplier models, and sourcing metadata should remain hidden in backend systems.
