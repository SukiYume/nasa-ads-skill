---
description: "Search NASA ADS for papers by keyword, author, title, bibcode, or arxiv ID and display results with metadata"
argument-hint: '<search query, e.g. "author:Einstein gravitational waves">'
allowed-tools:
  - Bash
---

# NASA ADS Search

Search the NASA Astrophysics Data System for academic papers.

## Arguments

The user's search query: $ARGUMENTS

## Instructions

1. Use the bundled Python CLI at `${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/scripts/ads_api.py`. It checks `ADS_API_TOKEN` and then `ADS_DEV_KEY`. If it reports that both are absent, point the user to https://ui.adsabs.harvard.edu/#user/settings/token, tell them to set one of those variables, and ask them to retry or provide a token for the current session. Never hardcode, print, or log the token.

2. Parse the user's query from `$ARGUMENTS`. Interpret natural language:
   - "papers by Einstein on relativity" -> `q=author:"Einstein" title:"relativity"`
   - "gravitational waves 2020-2024" -> `q=gravitational waves year:2020-2024`
   - A bibcode like "2016PhRvL.116f1102A" -> `q=bibcode:2016PhRvL.116f1102A`
   - An arxiv ID like "1602.03837" -> `q=arxiv:1602.03837`
   - "refereed papers about dark matter" -> `q=dark matter` plus `fq=property:refereed`
   - "papers citing 2016PhRvL.116f1102A" -> `q=citations(bibcode:2016PhRvL.116f1102A)`

3. Execute the search with the bundled CLI. Use `python3`; if that command is unavailable, try `python`, then `py -3`. The CLI preserves native ADS query syntax and URL-encodes every parameter.
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/nasa-ads/scripts/ads_api.py" search \
  --query '<ads_query>' \
  --fields 'bibcode,title,author,abstract,year,pub,doi,identifier,citation_count' \
  --rows 10 \
  --sort 'citation_count desc'
```
Add `--fq '<filter>'` for each filter. Use the direct HTTP fallback in the shared `SKILL.md` only when Python 3 is unavailable.

4. For each result, display in a clean format:
   - **Title**
   - **Authors** (first 5, then "et al." if more)
   - **Year** | **Journal** | **Citations**: count
   - **ADS**: `https://ui.adsabs.harvard.edu/abs/<bibcode>`
   - **arXiv**: extract from identifier array if available
   - **DOI**: if available

5. If the user asks for BibTeX, run the bundled CLI’s `export` subcommand for the selected bibcodes.

6. For literature research or claim checks, try useful synonyms and query variants, inspect abstracts before calling a paper direct evidence, and deduplicate by bibcode.

7. Present results clearly in markdown format. If no records match, state the queries and filters used, then describe the outcome as "no matching records found for these queries."
