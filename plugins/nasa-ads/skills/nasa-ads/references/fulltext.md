# Full-Text Retrieval and Reading

Load this reference for literature reviews, claim checks, paper summaries, or any task whose answer depends on article content beyond metadata and abstracts. Abstracts support triage. Material papers require a full-text attempt.

## Material-Paper Rule

A paper is material when the final answer uses it to support, weaken, or qualify a scientific claim; compares its method or result; includes it in an evidence table; or identifies it as a central or representative work.

- Retrieve and read full text for every material paper when a lawful accessible copy exists.
- Use abstracts to exclude clearly irrelevant candidates and to prioritize retrieval order.
- Label a result `abstract_only` when every full-text candidate fails. State the reason and avoid claim-level conclusions that require unseen article content.
- A search-result count, title, abstract, or resolver label cannot establish that the article body was read.

## Bundled Full-Text CLI

Resolve `scripts/fulltext.py` relative to `SKILL.md`. Use the same working Python 3 command selected for `ads_api.py`.

Fetch one or more ADS bibcodes, DOIs, arXiv IDs, or arXiv URLs:

```bash
python3 "<skill-dir>/scripts/fulltext.py" fetch \
  2019MNRAS.489..176M \
  arXiv:1602.03837
```

ADS bibcodes require `ADS_API_TOKEN` or `ADS_DEV_KEY`. A direct arXiv ID or URL can be fetched without an ADS token; metadata enrichment is skipped when credentials are absent.

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

`--format auto` prefers validated structured HTML within the best available version and falls back to PDF. Use `--format pdf` when equations, figures, tables, pagination, or a visual-reading test require the PDF artifact even though HTML is available. Explicit HTML and PDF requests use separate cache manifests and reject a server response whose actual content format does not match the request.

`--use-unpaywall` requires `UNPAYWALL_EMAIL`. The email is sent only to the Unpaywall API as its required query parameter. It is never sent to ADS or article hosts.

The default cache root is `%LOCALAPPDATA%\nasa-ads\fulltext` on Windows and `${XDG_CACHE_HOME:-~/.cache}/nasa-ads/fulltext` elsewhere. `NASA_ADS_CACHE_DIR` overrides it. Downloaded objects use content-hash filenames so a failed or lower-authority refresh cannot overwrite the artifact referenced by an existing valid manifest. A cached manifest is reusable only while its artifact and extracted-text files exist and their recorded hashes match; modified or incomplete cache entries trigger fresh discovery. Use `--refresh` when a current source check is required. A transient refresh cannot replace a valid cached published or accepted version with a lower-authority source; the returned `refresh` record explains the failed or downgraded attempt.

## Source Discovery and Ranking

The CLI uses ADS metadata and resolver records for identity and candidate discovery. It constructs official arXiv paths directly from every normalized arXiv ID:

```text
https://arxiv.org/html/<arxiv-id>
https://arxiv.org/pdf/<arxiv-id>
```

`https://arxiv.org/abs/<arxiv-id>` is metadata only and never counts as full text. Preserve an explicit arXiv version suffix such as `v2`.

Automatic ranking follows two dimensions:

1. Version authority: open published version, accepted author manuscript, submitted/preprint version, ADS scan.
2. Machine readability within a version: structured HTML, text-bearing PDF, scan requiring visual reading.

Every candidate is validated after download. The CLI rejects unsupported content, access/login/challenge pages, weak HTML landing pages, title mismatches, oversized responses, unsafe URLs, and failed PDF extractions. A resolver link is a candidate, not proof of access.

The CLI sends the ADS bearer token only to `api.adsabs.harvard.edu`. External article requests contain no ADS authorization header. It uses public HTTPS, follows bounded safe redirects, and does not bypass authentication or paywalls.

## Manifest Status

The command prints a JSON object with one entry per input under `results`. Read each entry before opening files.

### `fulltext`

`selected.text_path` contains extracted article text. Read it before using the paper as evidence. Use `selected.artifact_path` to verify figures, equations, tables, page layout, or extraction ambiguities.

`selected.sha256` verifies the exact downloaded PDF or HTML bytes. `selected.text_sha256` verifies the extracted text file. `selected.content_sha256` is a whitespace- and Unicode-normalized scientific-content fingerprint used by the literature database to recognize the same article text when a publisher changes only the HTML shell or PDF container metadata. Preserve all three when present.

The manifest identifies the selected version. When `selected_fulltext_is_preprint` appears, describe the evidence as preprint-derived. Check the published version for decisive numbers or claims when it is lawfully accessible.

### `needs_visual_reading`

The PDF was downloaded, while its text layer is sparse, missing, or unavailable to the installed extractor.

1. Read `selected.statistics.pages` and `selected.artifact_path`.
2. Use the host's native PDF vision reader when it can inspect local PDF pages.
3. When page images are required, render one range of at most twenty pages:

```bash
python3 "<skill-dir>/scripts/fulltext.py" render \
  "<selected.artifact_path>" \
  --pages 1-20
```

4. Inspect every content-bearing page for a central paper, in page order and bounded batches. For a claim-specific peripheral paper, inspect the complete relevant section plus surrounding context, methods, result, and limitation statements.
5. Record the inspected page ranges. Recheck exact values, symbols, table cells, and short quotations against the rendered page at sufficient resolution.
6. When no native PDF or image-vision capability is available, report `visual_reading_unavailable`. Keep the paper out of claim-level evidence.

Model vision is the default OCR/reading path for scans when the host provides it; no task-specific OCR downloader or converter should be written. It may omit characters or flatten table structure. Treat the page image as the authority for exact transcription, and record every visually inspected page range in the digest.

### `abstract_only`

No candidate produced readable full text. Report the attempted sources and errors from `attempts`. The abstract may support relevance triage and a clearly labeled abstract-level statement. It cannot support assertions about unmentioned methods, limitations, appendices, tables, or negative content claims.

### `error`

The identifier, ADS credentials, network, or input failed before a complete manifest could be produced. Correct the stated error and rerun. Do not replace a supported call with temporary download code.

## Reading Standard

For each material paper:

1. Confirm the title, authorship, identifier, document type, and selected version.
2. Read the abstract for orientation, then inspect the full paper's introduction, methods/data, results, discussion/conclusion, limitations, and data/code statements when present.
3. Search the extracted text for terms tied to the research question and read their complete surrounding sections.
4. Verify decisive numerical values, equations, figures, and tables in the original HTML or PDF artifact.
5. Separate the authors' measurements from interpretation, assumptions, cited background, and future work.
6. Record evidence with a section or page locator and the selected version.

For a focused review, full-text reading applies to the manageable material set. For broad reviews, retrieve the central, representative, contradictory, and method-defining papers; state the selection rule and any material paper that remained abstract-only.

## Final Method Note

Report:

- ADS query families, filters, sorting, pagination, and search date.
- Number of deduplicated material papers.
- Number read from published full text, accepted manuscripts, and preprints.
- Number requiring visual reading and page ranges inspected.
- Number left abstract-only, with reasons.
- Version or access limitations that affect the conclusion.

## Optional Local Helpers

The CLI itself uses the Python standard library. It detects these optional helpers:

- `pdftotext` for PDF text extraction.
- `pdfinfo` for page counts.
- `pdftoppm` for page rendering.
- `pypdf` as an optional Python text-extraction and page-count fallback.

Override executable discovery with `NASA_ADS_PDFTOTEXT`, `NASA_ADS_PDFINFO`, or `NASA_ADS_PDFTOPPM`. A missing helper produces an explicit manifest warning and routes the paper to visual reading when possible.

The workflow does not fetch or compile arXiv source archives. Article source can contain multiple files, unusual archive layouts, and executable build steps. Use official arXiv HTML or PDF for routine research.
