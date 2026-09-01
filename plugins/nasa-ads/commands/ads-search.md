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

6. For literature research or claim checks, use independent query variants, deduplicate by bibcode, and triage with metadata and abstracts. When a paper becomes prospective material evidence, read `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/references/literature-memory.md` and run `lookup` with the requested topics before opening article content.

7. For every opened exact version requiring complete ingest or facet expansion, read `references/fulltext.md` and `references/digest-schema.md`, then finish the routed reading and storage workflow before using article details.

8. Present results clearly in markdown format. Include published/preprint/visual/abstract-only coverage and reused/verified/augmented/new/version-refreshed database counts for literature research. If no records match, state the queries and filters used, then describe the outcome as "no matching records found for these queries."
