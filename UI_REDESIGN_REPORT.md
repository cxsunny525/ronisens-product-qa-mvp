# UI Redesign Report

## Summary

The Streamlit interface has been redesigned as a single-brand IOO Lighting AI
experience. The page now behaves like a clean search and conversation entry point
instead of a database dashboard.

## Main Changes

- Public title: `IOO Lighting AI`
- Hero headline: `Find the right machine vision lighting approach.`
- Removed public brand selector.
- Removed public database table counts.
- Removed public multi-vendor positioning.
- Added IOO Insight Points.
- Added simple upload intake for image, PDF, text, and markdown notes.
- Added conversation memory for the latest 8 turns.
- Added closest-fit IOO product cards.
- Product basis is shown as `IOO internal product database`.

## Upload Behavior

- Text and markdown notes are read into the question context.
- Images are displayed as thumbnails only.
- PDF files are acknowledged; deeper extraction can be added later.
- The app does not pretend to visually analyze images unless a vision model is
  configured.

## Trust Design

- Answers use confidence and fit labels.
- No exact fit is reframed as closest-fit or workaround-fit rather than a dead
  end.
- Follow-up prompts encourage the user to provide working distance, field of
  view, sample images, and material details.

## Remaining Limitations

- Image reasoning is not active by default.
- OpenAI responses require `OPENAI_API_KEY`.
- Physical sample testing is still required before final selection.
