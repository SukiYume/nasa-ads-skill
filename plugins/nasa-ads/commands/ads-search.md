---
description: "Search NASA ADS for papers by keyword, author, title, bibcode, or arxiv ID and display results with metadata"
argument-hint: '<search query, e.g. "author:Einstein gravitational waves">'
allowed-tools:
  - Bash
  - Read
  - Write
---

# NASA ADS Search

Search the NASA Astrophysics Data System for academic papers.

## Arguments

The user's search query: $ARGUMENTS

## Instructions

1. Read `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/references/ads-cli.md`, then use its bundled CLI, launch order, token boundary, and failure handling.

2. Parse the user's query from `$ARGUMENTS`. Interpret natural language:
   - "papers by Einstein on relativity" -> `q=author:"Einstein" title:"relativity"`
   - "gravitational waves 2020-2024" -> `q=gravitational waves year:2020-2024`
   - A bibcode like "2016PhRvL.116f1102A" -> `q=bibcode:2016PhRvL.116f1102A`
   - An arxiv ID like "1602.03837" -> `q=arxiv:1602.03837`
   - "refereed papers about dark matter" -> `q=dark matter` plus `fq=property:refereed`
   - "papers citing 2016PhRvL.116f1102A" -> `q=citations(bibcode:2016PhRvL.116f1102A)`

3. Run the bundled CLI; it preserves native ADS syntax and encodes every parameter.
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/scripts/ads_api.py" search \
  --query '<ads_query>' \
  --fields 'bibcode,title,author,abstract,year,pub,doi,identifier,citation_count' \
  --rows 10 \
  --sort 'citation_count desc'
```
Repeat `--fq '<filter>'` for filters.

4. For each result, display in a clean format:
   - **Title**
   - **Authors** (first 5, then "et al." if more)
   - **Year** | **Journal** | **Citations**: count
   - **ADS**: `https://ui.adsabs.harvard.edu/abs/<bibcode>`
   - **arXiv**: extract from identifier array if available
   - **DOI**: if available

5. If the user asks for BibTeX, run the bundled CLI’s `export` subcommand for the selected bibcodes.

6. For literature research or claim checks, try useful synonyms and independent query variants, deduplicate by bibcode, and use abstracts only for triage. Read `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/references/literature-memory.md` and run `literature_db.py lookup` for every prospective material paper with the requested topics. Reuse only exact stored versions with matching facet coverage.

7. For database misses, changed versions, or uncovered facets, read `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/references/fulltext.md`; fetch and read the article, then validate and ingest a multi-facet digest. Capture all material scientific dimensions encountered during full reading, not only the current query. Use `ingest --merge` after targeted reading.

8. Present results clearly in markdown format. Include published/preprint/visual/abstract-only coverage and reused/verified/augmented/new/version-refreshed database counts for literature research. If no records match, state the queries and filters used, then describe the outcome as "no matching records found for these queries."
