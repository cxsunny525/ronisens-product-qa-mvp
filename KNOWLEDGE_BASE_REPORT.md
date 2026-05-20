# IOO Knowledge Base Pilot Report

Generated: 2026-05-19

## Summary

- Knowledge database tables: completed in `data/ioo_product_test.db`
- Allowlist file: `source_allowlist.yaml`
- Taxonomy file: `knowledge_taxonomy.yaml`
- Pilot documents saved: 26
- Knowledge cards generated: 26
- Knowledge chunks generated: 26
- Knowledge sources registered: 7
- Approved documents: 0
- Pending review documents: 26
- OpenAI dependency: optional; current extraction used local fallback mode

## Crawl Result

The local Codex runtime attempted the allowlisted crawl with `crawl_knowledge.py --limit 30`.
The live HTTP fetches failed in this environment, so the crawler used the internal
pilot fallback file `knowledge_seed_documents.jsonl`.

The fallback records are short, source-linked curated notes for internal testing.
They are not full third-party articles and are all marked pending review with
unknown license status.

## Source Coverage

- Advanced Illumination
- Smart Vision Lights
- Edmund Optics
- Cognex
- Basler
- LUCID Vision Labs
- STEMMER IMAGING

Vision Systems Design is listed in the allowlist as manual-review-only and was
not included in the pilot data.

## Main Topic Distribution

Top generated tags from `extract_knowledge.py`:

- ring_light: 9
- surface_inspection: 9
- reflective_surface: 8
- backlight: 7
- metal: 7
- working_distance: 7
- edge_detection: 6
- measurement: 6
- polarized_light: 6
- bright_field: 5
- dark_field: 5
- dome_light: 5
- exposure: 5
- field_of_view: 5

## Quality Report

Generated files:

- `knowledge_quality_report.md`
- `knowledge_issues.csv`

Current quality issues:

- 26 `license_unknown` issues
- 1 `missing_tags` issue
- 1 `low_quality_score` issue
- 1 `short_body` issue

These are acceptable for an internal pilot but must be reviewed before broader
external use.

## Streamlit Integration

The app now includes:

- `Product QA` tab for product database questions
- `Knowledge Search` tab for knowledge cards and source documents
- `Combined Answer` tab that retrieves knowledge first, then product candidates

Combined answers separate:

- Knowledge Sources
- Product Sources
- Missing / Uncertain information

## Known Risks

- Live crawling could not be verified in the current local runtime because web
  requests failed; deployment/runtime with normal network access should rerun
  `crawl_knowledge.py --limit 30`.
- Pilot notes are pending human review and license status is unknown.
- Knowledge extraction is rule-based without embeddings, so recall is useful but
  not complete.
- Chinese answers may retrieve the right cards but still show some English
  source-card text until a bilingual summarization layer is added.

## Next Steps

1. Run the crawler in a network-enabled environment and replace fallback notes
   with extracted public-page records where robots rules allow.
2. Manually review source licenses and mark approved documents.
3. Add manual expert-reviewed knowledge cards for common applications such as
   metal scratch inspection, glass scratch inspection, transparent edge
   detection, PCB inspection, and reflective packaging.
4. Add embeddings after the content review workflow is stable.
5. Consider OpenAI summarization only after source governance and citation rules
   are locked down.
