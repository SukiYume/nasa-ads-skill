# Article Digest and Ingest

Contents: [What a digest retains](#what-a-digest-retains) · [Fields](#fields) · [Findings](#findings) · [Values](#values) · [Reading coverage](#reading-coverage) · [Validation and ingest](#validation-and-ingest)

Load this reference when an investigated article version needs a new digest, a targeted merge, validation, ingest, or an approved replacement. Under the no-write opt-out in [Core Invariants](../SKILL.md#core-invariants), keep the same reading coverage and evidence traceability in the answer and skip ingest.

## What a Digest Retains

A digest is the reusable record of one complete reading of one exact article version. Its layers let later work stop at the depth a task needs:

| Layer | Fields | Answers |
|---|---|---|
| 1 | `overview.tldr` | Whether the paper matters for a question, in one sentence |
| 2 | `overview.summary`, `questions`, `study_types` | What the paper did and found, in one paragraph |
| 3 | `reading.sections`, each with its summary in `gist` | What every section says; also the map for later passage reads |
| 4 | `facets` → `findings` → `values` | What a manuscript can cite, each with a locator and a verbatim quote |
| Context | `entities`, `datasets`, `methods`, `global_limitations`, `assessment`, `data_products` | The objects, data, procedures, and caveats that bound the results |

The stored article keeps the full wording and all remaining detail, and [`passage`](literature-memory.md#read-stored-passages) returns the paragraph behind a finding, one section, or the paragraphs matching a term.

Three kinds of content stay apart: the article's own content, traced to where the article states it; content the article takes from other work, marked with `cited_from`, with `compared_with` for the works a result is set against; and the reader's own evaluation, kept in `assessment`.

Digests are written in Chinese: `language` is `zh-CN` and the prose fields are Chinese. Quotes stay verbatim, and names, symbols, units, and the article's technical terms stay as printed.

## Fields

`literature_db.py template` prints the skeleton. `schema_version`, `language`, `facets`, and `reading` are required, with `overview` for `full` and `visual` readings. The other lists may be empty, and unknown keys are rejected.

| Field | Contents |
|---|---|
| `overview.tldr` | One sentence: what the paper did and its main result |
| `overview.summary` | One paragraph: question, data and method, main results, significance, and scope |
| `overview.questions` | The research questions the paper addresses |
| `overview.study_types` | One or more of `observational`, `theoretical`, `simulation`, `laboratory`, `instrumentation`, `methods`, `catalog`, `review` |
| `keywords` | Retrieval terms; also saved as tags |
| `entities` | The objects, instruments, surveys, catalogs, software, simulations, and models the paper relies on: `name`, `type` (`source`, `instrument`, `survey`, `catalog`, `software`, `simulation`, `model`, or `other`), `aliases` |
| `datasets` | The data the paper analyzes: `name`, `type` (`observation`, `survey`, `archival`, `catalog`, `simulation`, or `laboratory`), `description`, `identifiers`, `locator`, `cited_from` |
| `methods` | The procedures its results depend on: `name`, `description`, `assumptions`, `locator`, `cited_from` |
| `facets` | Groups of findings on one scientific question: `key` (a lowercase slug), `label`, `summary`, `findings`, and optional `aliases`, `keywords`, `methods` |
| `global_limitations` | Limitations the authors state for the whole paper |
| `assessment` | The reader's evaluation, in self-contained sentences |
| `data_products` | Released tables, catalogs, data, and code: `name`, `type` (`data`, `code`, `catalog`, `table`, `software`, or `other`), `url`, `availability`, `locator` |
| `reading` | The coverage of this reading, described under [Reading coverage](#reading-coverage) |

A `locator` names at least one of `section`, `page`, `figure`, `table`, `equation`, `appendix`, and `paragraph`, using the article's own labels. Values and facets refer to datasets and methods by `name`.

## Findings

A finding is one result that a manuscript sentence would cite. Derive facets and findings from the article's own structure of evidence. Merge statements that would always be cited together, and keep a measurement apart from the authors' interpretation of it.

| Field | Contents |
|---|---|
| `statement` | A concise paraphrase of the result and what it rests on |
| `kind` | One of the kinds below |
| `confidence` | The authors' own certainty: `high`, `medium`, or `low` |
| `locator` | Where the article states it |
| `quote` | A short run of consecutive words copied verbatim from the prepared text where the result is stated |
| `values` | The headline quantities of the result, when it has any |
| `cited_from` | The work a restated or adopted result comes from, as text; empty for the paper's own results |
| `compared_with` | A list of the works a comparison sets the result against |
| `keywords` | An optional list of retrieval terms |

| Kind | Records |
|---|---|
| `measurement` | A quantity or property measured from data |
| `constraint` | A bound, allowed region, or exclusion inferred from data |
| `nondetection` | A search without detection, with its limits |
| `interpretation` | An inference the authors draw about cause or meaning |
| `prediction` | A consequence of a model or simulation |
| `comparison` | The result set against other works or models |
| `method` | A methodological fact that conditions results |
| `limitation` | A caveat the authors state |

The quote anchors [`passage`](literature-memory.md#read-stored-passages), which finds it in the stored text regardless of case, spacing, hyphenation, and punctuation. A scan read visually can leave quotes empty and rely on page locators. Each finding is referenced as `<facet key>.<position>`, and merges append findings so earlier references stay valid.

## Values

Values hold the headline numbers of a finding, copied as printed in the article's units. A number that only gives context can stay in the statement.

| Field | Use |
|---|---|
| `name`, `symbol` | The quantity and its symbol in the article's terminology; `name` is required |
| `value`, `range` | The reported number, or `[low, high]` for an interval; a string keeps a written form such as `"1.2e-3"` |
| `uncertainty`, `unit`, `qualifier` | As written; the qualifier holds a confidence level, an interval type, or `approximately` |
| `status` | Required: `measured`, `fitted`, `derived`, `fixed`, `assumed`, `predicted`, `upper-limit`, or `lower-limit` |
| `model`, `dataset`, `method`, `condition` | What the value depends on and where it applies |
| `cited_from` | The work an adopted value comes from |

A long table becomes one finding with counts and ranges, and the table is listed under `data_products`.

## Reading Coverage

`reading.status` is `full` when every body section and appendix was read and summarized, `visual` when every page of a scan was inspected and listed in `visual_page_ranges`, and `targeted` when complete sections were read for a version that already has a complete digest, with `unread_sections` describing the rest.

`reading.sections` holds one entry for each body section, subsection, and appendix read, in article order:

- `heading`: the article heading as printed, with its number, so `passage --section` can find it.
- `gist`: the summary of that section, written so it can stand in for the section when a later question touches it. State what the section says in its own terms, keep the names and numbers it turns on, and let the length follow the section, from one sentence to a short paragraph.

The title block, abstract, reference list, and acknowledgment, funding, and author statements need no entry. `reading.notes` records which version was read and how it was retrieved.

## Validation and Ingest

```bash
python3 "<skill-dir>/scripts/literature_db.py" validate-digest "<digest.json>" --text "<manifest_path>"
python3 "<skill-dir>/scripts/literature_db.py" ingest --manifest "<manifest.json>" --digest "<digest.json>"
```

Both commands reject a digest with a structural error, prose outside Chinese, a listed section without a summary, or, for a `full` reading, a substantial article section left without an entry. The error names what to fix. `--text` takes the fetch manifest, or `selected.text_path` for the text alone, and checks the digest against the prepared article as ingest does.

The report gives `anchors`, the quotes it cannot find in the text, and `section_summaries`, the summaries that are `thin` for their section; `warnings` lists both. Fix each one, or confirm it is a false positive, before ingest.

The first ingest of an exact version needs `full` or whole-document `visual` coverage. A `needs_visual_reading` manifest takes a `visual` digest whose page ranges cover every page, and an `abstract_only` manifest cannot be ingested. After ingest, assign a missing topic with `annotate` or `organize`.

When a later question needs a result the stored digest lacks, read the relevant complete sections with `passage --section` and merge a targeted digest that holds their summaries and the new facets and findings, using the durable `manifest_path` that `lookup` returns:

```bash
python3 "<skill-dir>/scripts/literature_db.py" ingest --manifest "<manifest.json>" --digest "<targeted-digest.json>" --merge
```

A targeted digest needs only `schema_version`, `language`, `facets`, and `reading`. The merge keeps the stored overview and records, appends new findings and facets, replaces a finding that has the same statement and locator, and gives a stored section its summary when it had none.

An approved repair starts with `backup`, rebuilds the complete digest from the stored article, and replaces it:

```bash
python3 "<skill-dir>/scripts/literature_db.py" ingest --manifest "<manifest.json>" --digest "<complete-replacement.json>" --replace-digest
```
