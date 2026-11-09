# Full-Text Retrieval and Reading

Contents: [Bundled full-text CLI](#bundled-full-text-cli) · [Import a local copy](#import-a-local-copy) · [Source discovery and ranking](#source-discovery-and-ranking) · [Manifest results](#manifest-results) · [Reading procedure](#reading-procedure) · [Optional local helpers](#optional-local-helpers)

Load this reference when a task fetches or reads article content. Run [local lookup](literature-memory.md#local-lookup-and-reading) first, apply the shared [reading scope](../SKILL.md#reading-scope), and load [digest-schema.md](digest-schema.md) when the exact version needs a digest.

## Bundled Full-Text CLI

Fetch bibcodes, DOIs, arXiv IDs, or arXiv URLs, each as a separate shell-quoted argument:

```bash
python3 "<skill-dir>/scripts/fulltext.py" fetch \
  2019MNRAS.489..176M \
  arXiv:1602.03837
```

Bibcodes require `ADS_API_TOKEN`. Direct arXiv identifiers use public arXiv metadata and article services without a SciX token.

Useful options:

```text
--source auto|publisher|author|arxiv|ads
--format auto|html|pdf
--cache-dir <directory>
--refresh
--timeout <seconds>
--max-mib <MiB>
--use-unpaywall
--library-dir <directory>
--no-store
```

`--format auto` selects validated structured HTML within the best available version and falls back to PDF. Use `--format pdf` for equations, figures, tables, pagination, or visual review. Explicit format requests validate the response format.

Fetch captures available article metadata and abstracts by default, including an abstract-only result. Complete [source summaries](literature-memory.md#automatic-capture-and-summary-completion) for each returned `literature.run_id`. A local persistence failure keeps the prepared files and exits nonzero; apply [failure routing](../SKILL.md#failure-routing). Under the no-write opt-out, preparation still uses the download cache.

After a text-bearing fetch, inventory the article structure:

```bash
python3 "<skill-dir>/scripts/fulltext.py" outline \
  "<manifest_path>" \
  --limit 200
```

Pass the result's `manifest_path` so the outline can use the headings of an HTML source, or `selected.text_path` for the text alone. The outline lists each inferred section with its `heading`, starting `line`, length in `lines`, and `words`; text before the first heading appears as `Front matter`. Reconcile noisy, duplicated, or missing headings against the artifact. The line numbers let a reader open one section at a time and skip the reference list, and the headings become the digest's `reading.sections`.

`--use-unpaywall` requires `UNPAYWALL_EMAIL`. The address is sent to the Unpaywall API as its required query parameter.

The default cache root is `%LOCALAPPDATA%\nasa-ads\fulltext` on Windows and `${XDG_CACHE_HOME:-~/.cache}/nasa-ads/fulltext` elsewhere. `NASA_ADS_CACHE_DIR` selects another root. Content-hash filenames preserve every validated artifact. Cached manifests remain reusable while their artifact and extracted-text hashes verify and their text comes from the current extraction. A cached artifact with text from an earlier extraction is prepared again from the cached file, with the warning `text_prepared_again_from_cached_artifact`; a selection that then fails validation is retrieved again. `--refresh` performs a current source check and reports failed or lower-authority refresh attempts without displacing a stronger cached result.

## Import a Local Copy

When lawful retrieval returns `abstract_only` or a weaker version, the user can supply a PDF or HTML copy obtained through their own access. Import it with the paper's identifier and the version the file holds:

```bash
python3 "<skill-dir>/scripts/fulltext.py" import "<paper.pdf>" \
  --identifier 2019MNRAS.489..176M \
  --version published \
  --source-url "https://doi.org/10.1093/mnras/stz1521"
```

`--version` is `published`, `accepted`, `preprint`, or `scan`; confirm it from the file itself, such as journal typesetting or an arXiv stamp. `--source-url` optionally records an HTTPS address the file came from. The file passes the same format, extraction, and title-identity checks as a download, and the result is a manifest with `selected.candidate.source` `user` and the warning `user_supplied_artifact`. Metadata capture, `outline`, reading, validation, and ingest then proceed as for `fetch`. Bibcodes and DOIs need `ADS_API_TOKEN` for metadata; the local file path stays out of the manifest.

## Source Discovery and Ranking

SciX metadata and resolver records supply identity and candidate discovery. Normalized arXiv IDs produce official article paths directly:

```text
https://arxiv.org/html/<arxiv-id>
https://arxiv.org/pdf/<arxiv-id>
```

`https://arxiv.org/abs/<arxiv-id>` supplies metadata. Preserve explicit arXiv version suffixes such as `v2`.

An explicit version selects matching metadata and article URLs. A failed exact-version lookup remains unresolved until that version is obtained. Stored versions are selected by authority and explicit version identity. An uncovered topic in a complete local record can be checked using its verified local artifact and durable manifest.

Automatic ranking uses two dimensions:

1. Version authority: open published version, accepted author manuscript, submitted/preprint version, ADS scan.
2. Machine readability within that version: structured HTML, text-bearing PDF, scan requiring visual reading.

The CLI validates every downloaded candidate. Validation covers content type, size, safe HTTPS redirects, access or challenge pages, subscription previews that show an abstract and references without the article body, landing pages that load the body separately, recognized by an abstract followed by too little body prose, landing-page strength, title identity, and PDF extraction. A rejected publisher page falls through to the next candidate, such as the arXiv preprint. Resolver links remain candidates until validation succeeds.

SciX bearer credentials travel only to `api.scixplorer.org`. External article requests carry no SciX authorization header. Retrieval uses lawful public access and bounded redirects.

## Manifest Results

`fetch` prints one JSON result per input. Inspect `status`, selected version, provenance, hashes, artifact path, text path, and attempts before reading files.

### `fulltext`

`selected.text_path` contains prepared article text. `selected.artifact_path` supports checks of figures, equations, tables, pagination, and extraction ambiguities.

Prepared HTML text marks superscripts as `^{...}` and subscripts as `_{...}`, so `2 × 10^{16} G` stays distinct from `1016`, and carries math as TeX: `$...$` inline and `$$...$$` on its own line for a displayed equation. Equations published only as images leave a gap in the text. PDF text keeps the characters of superscripts and subscripts on the line, so `10^{16}` can read as `1016`; check exponents and indices in the artifact.

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

For an exact version requiring complete ingest, read the body once and write the digest while reading:

1. Confirm title, authorship, identifiers, document type, and selected version.
2. Run `outline` and reconcile headings with the artifact.
3. Read the sections in order by line range: front matter and abstract, introduction, data, methods, results, discussion, conclusions, and every appendix carrying results, validation, or data and code statements. Skip the reference list, acknowledgments, author lists, and affiliations; look up a single reference entry when a finding needs `cited_from` or `compared_with`.
4. After each section, add its findings at [citation granularity](digest-schema.md#granularity), each with a locator and a quote copied from the text just read; the section heading with a gist where the heading is uninformative; and any new entity, dataset, or method. Keep restated content under `cited_from` and the reader's evaluation in `assessment`.
5. For tables and figures, read the captions and the rows or panels the text discusses. A long table becomes one finding with counts and ranges plus a `data_products` entry; only headline numbers become [values](digest-schema.md#values).
6. Open the artifact where text extraction leaves a decisive value, sign, exponent, equation, or table cell ambiguous, such as a PDF exponent read inline or an equation missing from HTML text, and copy the value as printed.
7. Write `overview.tldr` and `overview.summary` last, from the drafted findings.
8. Follow [digest-schema.md](digest-schema.md#validation-and-ingest) to review, validate with `--text`, and ingest the record.

Verify the task's investigation set with [reading-check](literature-memory.md#local-lookup-and-reading) and apply the shared [handoff criteria](../SKILL.md#completion-and-handoff).

## Optional Local Helpers

The CLI uses the Python standard library and detects these optional helpers:

- `pdftotext` for PDF text extraction in reading order, which keeps the columns of two-column pages in sequence;
- `pdfinfo` for page counts;
- `pdftoppm` for page rendering;
- `pypdf` as a Python extraction and page-count fallback.

`NASA_ADS_PDFTOTEXT`, `NASA_ADS_PDFINFO`, and `NASA_ADS_PDFTOPPM` override executable discovery. Missing helpers produce manifest warnings and route suitable PDFs to visual reading.

Routine retrieval uses official arXiv HTML or PDF. Source archives can contain multi-file trees and executable build steps, so this workflow leaves source compilation outside the bundled CLI.
