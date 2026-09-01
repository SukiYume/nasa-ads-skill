# Full-Text Retrieval and Reading

Load this reference when a task fetches or reads article content. Load [literature-memory.md](literature-memory.md) before opening content and load [digest-schema.md](digest-schema.md) when the exact version requires ingest.

## Bundled Full-Text CLI

Resolve `scripts/fulltext.py` relative to `SKILL.md`. Use the working Python 3 command selected for the bundled CLIs.

Fetch ADS bibcodes, DOIs, arXiv IDs, or arXiv URLs:

```bash
python3 "<skill-dir>/scripts/fulltext.py" fetch \
  2019MNRAS.489..176M \
  arXiv:1602.03837
```

ADS bibcodes require `ADS_API_TOKEN` or `ADS_DEV_KEY`. Direct arXiv identifiers use public arXiv metadata and article services without an ADS token.

Useful options:

```text
--source auto|publisher|author|arxiv|ads
--format auto|html|pdf
--cache-dir <directory>
--refresh
--timeout <seconds>
--max-mib <MiB>
--use-unpaywall
```

`--format auto` selects validated structured HTML within the best available version and falls back to PDF. Use `--format pdf` for equations, figures, tables, pagination, or visual review. Explicit format requests validate the response format.

After a text-bearing fetch, inventory the article structure:

```bash
python3 "<skill-dir>/scripts/fulltext.py" outline \
  "<selected.text_path>" \
  --limit 200
```

The outline reports inferred headings. Reconcile noisy, duplicated, or missing headings against the artifact. It supplies the reading map and section names for digest coverage.

`--use-unpaywall` requires `UNPAYWALL_EMAIL`. The address is sent to the Unpaywall API as its required query parameter.

The default cache root is `%LOCALAPPDATA%\nasa-ads\fulltext` on Windows and `${XDG_CACHE_HOME:-~/.cache}/nasa-ads/fulltext` elsewhere. `NASA_ADS_CACHE_DIR` selects another root. Content-hash filenames preserve every validated artifact. Cached manifests remain reusable while their artifact and extracted-text hashes verify. `--refresh` performs a current source check and reports failed or lower-authority refresh attempts without displacing a stronger cached result.

## Source Discovery and Ranking

ADS metadata and resolver records supply identity and candidate discovery. Normalized arXiv IDs produce official article paths directly:

```text
https://arxiv.org/html/<arxiv-id>
https://arxiv.org/pdf/<arxiv-id>
```

`https://arxiv.org/abs/<arxiv-id>` supplies metadata. Preserve explicit arXiv version suffixes such as `v2`.

Automatic ranking uses two dimensions:

1. Version authority: open published version, accepted author manuscript, submitted/preprint version, ADS scan.
2. Machine readability within that version: structured HTML, text-bearing PDF, scan requiring visual reading.

The CLI validates every downloaded candidate. Validation covers content type, size, safe HTTPS redirects, access or challenge pages, landing-page strength, title identity, and PDF extraction. Resolver links remain candidates until validation succeeds.

ADS bearer credentials travel only to `api.adsabs.harvard.edu`. External article requests carry no ADS authorization header. Retrieval uses lawful public access and bounded redirects.

## Manifest Results

`fetch` prints one JSON result per input. Inspect `status`, selected version, provenance, hashes, artifact path, text path, and attempts before reading files.

### `fulltext`

`selected.text_path` contains prepared article text. `selected.artifact_path` supports checks of figures, equations, tables, pagination, and extraction ambiguities.

`selected.sha256` identifies the downloaded artifact bytes. `selected.text_sha256` identifies extracted text. `selected.content_sha256` identifies normalized scientific content and lets the database recognize an unchanged article inside a refreshed HTML shell or PDF container.

The manifest records version authority. `selected_fulltext_is_preprint` marks preprint-derived evidence. Decisive publication-specific claims use the published version when lawful access exists.

### `needs_visual_reading`

The PDF is available and its text layer is sparse, missing, or unusable.

1. Read `selected.statistics.pages` and `selected.artifact_path`.
2. Use the host's native PDF vision reader when available.
3. Render bounded page ranges when page images are needed:

```bash
python3 "<skill-dir>/scripts/fulltext.py" render \
  "<selected.artifact_path>" \
  --pages 1-20
```

4. Inspect every content-bearing page in order for a new exact-version record. Process ranges of at most twenty pages.
5. For targeted verification of a complete stored version, inspect the relevant section and its surrounding context, method, result, and limitation statements.
6. Record all visually inspected page ranges and recheck exact values, symbols, table cells, and short quotations at sufficient resolution.

Model vision supplies the default scan-reading path when the host supports local PDF or page-image inspection. Page images remain authoritative for exact transcription because OCR can omit characters and flatten table structure. A host without visual capability reports `visual_reading_unavailable` and keeps the article outside claim-level evidence.

### `abstract_only`

All full-text candidates failed. Report sources and errors from `attempts`. The abstract supports relevance triage and clearly labeled abstract-level statements. Claims about unseen methods, limitations, appendices, tables, or negative content remain unsupported.

### `error`

Identifier, credential, network, or input processing failed before a complete manifest was produced. Correct the reported cause and rerun the bundled CLI.

## Reading Procedure

For an exact version requiring complete ingest:

1. Confirm title, authorship, identifiers, document type, and selected version.
2. Run `outline` and reconcile headings with the artifact.
3. Read the abstract for orientation, followed by every applicable introduction, data, methods, results, discussion, conclusions, limitations, material appendices, references, and data/code statement.
4. Search prepared text for task terms and read their complete surrounding sections.
5. Verify decisive numerical values, equations, figures, tables, and layout-sensitive evidence in the artifact.
6. Separate measurements, interpretations, assumptions, cited background, and future work in the digest.
7. Record exact article headings, evidence locators, selected version, and complete section-to-facet coverage.
8. Follow `digest-schema.md` to validate and ingest the record before using article details.

For a broad review, select the central, representative, contradictory, and method-defining material papers. State the selection rule and identify material papers that remained abstract-only.

## Optional Local Helpers

The CLI uses the Python standard library and detects these optional helpers:

- `pdftotext` for PDF text extraction;
- `pdfinfo` for page counts;
- `pdftoppm` for page rendering;
- `pypdf` as a Python extraction and page-count fallback.

`NASA_ADS_PDFTOTEXT`, `NASA_ADS_PDFINFO`, and `NASA_ADS_PDFTOPPM` override executable discovery. Missing helpers produce manifest warnings and route suitable PDFs to visual reading.

Routine retrieval uses official arXiv HTML or PDF. Source archives can contain multi-file trees and executable build steps, so this workflow leaves source compilation outside the bundled CLI.
