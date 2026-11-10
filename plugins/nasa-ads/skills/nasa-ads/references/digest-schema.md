# Article Digest and Ingest

Contents: [What a digest retains](#what-a-digest-retains) · [Granularity](#granularity) · [Template](#template) · [Overview and context layers](#overview-and-context-layers) · [Facets and findings](#facets-and-findings) · [Values](#values) · [Limitations, assessment, and data products](#limitations-assessment-and-data-products) · [Reading coverage](#reading-coverage) · [Validation and ingest](#validation-and-ingest)

Load this reference when an investigated article version needs a new digest, a targeted merge, validation, ingest, or an approved replacement. Apply the shared [reading scope](../SKILL.md#reading-scope). Under the no-write opt-out in [Core Invariants](../SKILL.md#core-invariants), keep the same reading coverage and evidence traceability in the answer and skip ingest.

## What a Digest Retains

A digest is the reusable record of one complete reading of one exact article version. Its layers let later work stop at the depth a task needs:

| Layer | Fields | Answers |
|---|---|---|
| 1 | `overview.tldr` | Whether the paper matters for a question, in one sentence |
| 2 | `overview.summary`, `questions`, `study_types` | What the paper did and found, in one paragraph with its headline numbers |
| 3 | `reading.sections` with gists | Where each topic sits in the article; the map for later passage reads |
| 4 | `facets` → `findings` → `values` | What a manuscript can cite, with a locator and a verbatim quote of the stating passage |
| Context | `entities`, `datasets`, `methods`, `global_limitations`, `assessment`, `data_products` | Object filters and the data, procedures, and caveats that bound the results |

The stored article keeps every other detail. [`passage`](literature-memory.md#read-stored-passages) returns the paragraph that a finding's quote anchors, one section, or the paragraphs matching a term, so rechecking a citation or answering a new question reads a paragraph or a section of the stored text.

The digest keeps three kinds of content apart:

- **The article's own content**, attributable to the paper and traced to article locations.
- **Content the article takes from other work.** `cited_from` names the original source of a restated result, adopted value, reused dataset, or borrowed method, so a citation reaches that source. `compared_with` lists the works a result is compared against.
- **The reader's assessment** in `assessment`: robustness, untested assumptions, and concerns the authors leave unstated. It informs judgment and is never attributed to the paper.

Digests hold paraphrases plus short anchor quotes. Bibliographic metadata lives in the paper record, and manuscript placement or comparisons with the user's work belong in [roles and notes](literature-memory.md#classification-and-manuscript-roles).

## Granularity

A finding is a result that a manuscript sentence would cite. Record:

- the paper's results: measurements, fits, derived constraints, nondetections and their limits;
- each inference the authors draw, as its own step, so an argument can be cited where it is made;
- predictions together with the model that produces them;
- comparisons with named works or models;
- methodological facts that condition results: adopted inputs and priors, thresholds and cuts, validation, completeness;
- limitations the authors state.

The stored article keeps background restated from other work (unless the paper adopts or contests it), instrument and search configuration, observation logs, per-object table rows, intermediate fit statistics, and derivation steps; locators and `passage` reach them.

Merge statements that a manuscript would always cite together, and separate a measurement from the authors' interpretation of it. A statement takes one or two sentences. As a calibration, a letter yields about 4–10 findings, a research article 10–25, and a long survey or review up to about 40; values cover headline numbers and usually number zero to three per finding. Depth follows the paper's evidence structure, and the schema has no domain vocabulary or quota.

Digests are written in Chinese: `language` is `zh-CN`, and the prose fields (tldr, summaries, questions, gists, statements, descriptions, limitations, and assessment) are Chinese, so one library reads in one language. `validate-digest` and `ingest` reject another `language` and list the prose fields without Chinese. Quotes stay verbatim, and quantity names, symbols, units, model names, and dataset, method, and entity names keep the article's own terminology, usually English, so queries match the literature. The overview describes the paper's own contribution and limits, so the digest stays meaningful across projects.

## Template

`literature_db.py template` prints the schema 4 skeleton. Required fields are `schema_version`, `language`, `facets`, and `reading`, plus `overview` for `full` and `visual` readings. `keywords`, `entities`, `datasets`, `methods`, `global_limitations`, `assessment`, and `data_products` default to empty lists. Optional fields left blank are dropped during validation, and unknown keys are rejected so misspelled fields never reach storage.

## Overview and Context Layers

| Field | Contents |
|---|---|
| `overview.tldr` | One sentence: what the paper did and its main result |
| `overview.summary` | One paragraph: question, data and method, main results with headline numbers, significance, and scope |
| `overview.questions` | The research questions the paper addresses |
| `overview.study_types` | One or more of `observational`, `theoretical`, `simulation`, `laboratory`, `instrumentation`, `methods`, `catalog`, `review` |
| `keywords` | Retrieval terms; also saved as tags |
| `entities` | Named sources the paper analyzes or discusses substantively, and the instruments, surveys, catalogs, software, simulations, and models it relies on: `name`, `type`, and `aliases` (other designations and short names). Types are `source`, `instrument`, `survey`, `catalog`, `software`, `simulation`, `model`, and `other` |
| `datasets` | One entry per observation campaign, experiment, simulation suite, archival sample, or catalog the paper analyzes: `name` (a short label that values reference), `type` (`observation`, `survey`, `archival`, `catalog`, `simulation`, or `laboratory`), a one- or two-sentence `description` of instrument, configuration, sample, epochs, and band, `identifiers`, `locator`, and `cited_from` for reused data |
| `methods` | One entry per analysis, fitting, calibration, or modelling procedure that results depend on: `name` (the label that values and facets reference), `description`, `assumptions`, `locator`, and `cited_from` for an adopted procedure |

A `locator` object names at least one of `section`, `page`, `figure`, `table`, `equation`, `appendix`, and `paragraph`, using the article's real labels. `section` holds one section label; tables, figures, and equations go in their own fields, and a finding points to the most specific place that supports it.

## Facets and Findings

A facet groups the findings that answer one future scientific question with a distinguishable evidence chain: a distinct observable, population, regime, mechanism, prediction family, or method validation. Derive facets from the article. A facet has a lowercase ASCII slug `key`, a `label`, a one-sentence `summary`, and its `findings`; `aliases`, `keywords`, and `methods` (names of `methods` entries) are optional retrieval aids. A label can pair the Chinese name with the article's English term, and aliases carry the English forms a later query would use.

Each finding records one citable result:

| Field | Contents |
|---|---|
| `statement` | A concise paraphrase that names what the result rests on |
| `kind` | One of the kinds below |
| `confidence` | The authors' stated certainty: `high` for a result stated as established, `medium` for one stated as likely or suggestive, `low` for a tentative or speculative one |
| `locator` | Where the article states it |
| `quote` | 6–25 consecutive words copied verbatim from the prepared text where the result is stated, including its number when there is one |
| `values` | The headline quantities the statement reports |
| `cited_from` | The one work a restated or adopted result comes from, as the article cites it; empty for the paper's own results. A statement drawing on several works becomes several findings |
| `compared_with` | The works a comparison finding sets the result against |
| `keywords` | Optional retrieval terms |

| Kind | Records | Typical citing verb |
|---|---|---|
| `measurement` | A quantity or property measured from data | measured, found |
| `constraint` | A bound, allowed region, or exclusion inferred from data | constrained, ruled out |
| `nondetection` | A search without detection, with its limits | did not detect |
| `interpretation` | An inference the authors draw about cause or physical meaning | argued, inferred, suggested |
| `prediction` | A consequence of a model or simulation, with its assumptions | predicted |
| `comparison` | The paper's result set against other works or models | found consistent with, found in tension with |
| `method` | A methodological fact that conditions results | adopted, validated |
| `limitation` | A caveat or limitation the authors state | noted |

The quote anchors [`passage`](literature-memory.md#read-stored-passages): matching ignores case, spacing, line-break hyphenation, ligatures, and punctuation, and prefers the locator's section. Copy it from the prepared text while reading that section, including any TeX it carries; the `^{}` and `_{}` marks of exponents and indices can be kept or dropped. A scan read visually can leave quotes empty; its findings rely on page locators, and so do findings without a quote, which `passage` resolves through their section, table, figure, or equation.

Each finding is referenced as `<facet key>.<position>`, such as `polarization.2`. `findings` and `parameters` rows report this `finding_id`, and targeted merges append new findings so earlier ids stay valid.

## Values

Record the numbers a manuscript would quote, one quantity per entry: headline measured, fitted, and derived results, limits, predictions, the adopted inputs and priors that determine a cited result, and the significances and sample sizes that qualify a conclusion. A long table, burst list, or observation log becomes one finding with counts and ranges, its locator names the table, and the table is registered under `data_products`. Configuration such as bandwidth, sampling, channels, and trial grids belongs in the dataset or method description; record it as a value only when it defines a reported result, such as a detection threshold.

| Field | Use |
|---|---|
| `name` | Required; the quantity in the article's terminology |
| `symbol` | The article's symbol, such as `RM` or `α` |
| `value` | The reported number, or a string that preserves the written form, such as `"0.10"` or `"1.2e-3"` |
| `range` | `[low, high]` for an interval or span, each bound a number or a number written as a string; `value` is optional when `range` is given |
| `uncertainty` | As written: `"0.05"` for symmetric, `"+0.05/-0.04"` for asymmetric |
| `unit` | As written |
| `qualifier` | Interval type, confidence level, estimator, significance, or `approximately` |
| `status` | Required: `measured`, `fitted`, `derived`, `fixed`, `assumed`, `predicted`, `upper-limit`, or `lower-limit` |
| `model` | The fitted model or theoretical framework; every `fitted` value names it |
| `dataset`, `method` | Names of the matching `datasets` and `methods` entries |
| `condition` | Object, subsample, band, epoch, or regime the value applies to |
| `cited_from` | The work an adopted or restated value comes from; a value without one inherits its finding's `cited_from` |

These representation rules keep values comparable across papers:

- A limit uses `status` `upper-limit` or `lower-limit`, the bound as `value`, and the confidence level in `qualifier`.
- An uncertainty goes in `uncertainty`, and `value` holds the central value alone.
- An interval or span goes in `range`. A best fit with a credible interval can carry both `value` and `range`, with the interval type in `qualifier`.
- Several numbers become several entries, each with its `condition`.
- A value is copied as printed, in the article's units. Long decimals such as MJDs and numbers in scientific notation are strings, such as `"57175.743510388"` or `"7.4e27"`, so no digits are lost or invented; `range` bounds follow the same rule, such as `["5e-3", "6e-3"]`.

Values from the same fit share one finding so the parameter set stays together, with the table or equation in its locator.

## Limitations, Assessment, and Data Products

- `global_limitations` lists limitations the authors state for the whole paper. A limitation tied to one facet is a `limitation` finding with its locator.
- `assessment` lists the reader's evaluation in self-contained sentences: untested assumptions, unaddressed selection effects, robustness of the main results, internal inconsistencies, and reproducibility. Manuscript text that uses an assessment point presents it as the manuscript's own argument.
- `data_products` lists reusable tables, catalogs, data, code, and software with `name`, `type` (`data`, `code`, `catalog`, `table`, `software`, or `other`), `url`, `availability`, and a text `locator`.

## Reading Coverage

`reading.status` is one of:

- `full`: every body section and every appendix carrying results, validation, or data and code statements was read; the reference list was consulted for the entries that `cited_from` and `compared_with` name;
- `visual`: every page of a scan or sparse-text PDF was inspected, listed in `visual_page_ranges`;
- `targeted`: complete sections relevant to new topics were read for a version that already has a complete digest; `unread_sections` describes the rest.

`reading.sections` lists each read section with its article heading, copied with its number as printed so `passage --section` can locate it in the stored text, and an optional one-sentence `gist` of what it contributes, written when the heading alone leaves that unclear:

```json
"sections": [
  {"heading": "2 Observations and Data Reduction"},
  {"heading": "3 Results", "gist": "Burst rates, spectra, and polarization of the 1076 bursts."}
]
```

A plain heading string is accepted for a section without a gist. `reading.notes` records which version was read and how it was retrieved. `full` and `visual` digests keep `unread_sections` empty.

The structural minimum is a tldr, a summary, one research question, one study type, one facet with one finding carrying a real locator, and the list of read sections.

## Validation and Ingest

Before validating, review the draft against the article: each main result, inference, prediction, and stated limitation appears once at the right kind; numbers, signs, and exponents match the article; restated and adopted content carries `cited_from`; the reader's evaluation sits in `assessment`; quotes are verbatim. This content review complements the CLI's structural checks.

```bash
python3 "<skill-dir>/scripts/literature_db.py" validate-digest "<digest.json>" --text "<selected.text_path>"
python3 "<skill-dir>/scripts/literature_db.py" ingest --manifest "<manifest.json>" --digest "<digest.json>"
```

`--text` checks every quote against the prepared article text and reports `anchors` with the ids of quotes it cannot find. Validation and ingest report `warnings` for likely problems: a statement that reports a number without `values`; value strings or qualifiers that embed a limit, an uncertainty, an interval, or several numbers; a value whose digits look computed; a `fitted` value without `model`; a `section` locator holding a table, figure, or equation label; a `cited_from` naming several works; findings of a `full` reading without quotes, or quotes absent from the text; and excess detail, meaning a statement over 400 characters, a quote over 300, more than 8 values in one finding, more than 60 values, or more than 40 findings in one digest. Fix each warning in the digest, or confirm it is a false positive, before ingest. Dataset and method references are checked for complete readings; a targeted digest reports `references_checked: false`, and its references are checked against the merged record.

The first ingest of an exact version requires `full` or whole-document `visual` coverage. It verifies artifact, text, and canonical-content hashes, checks eligibility before copying objects, reconciles identifiers, commits one transaction, rebuilds the search document, and reports quote `anchors` against the stored text. `needs_visual_reading` manifests require `visual` status with page ranges covering every recorded page. `abstract_only` manifests supply metadata and abstract summaries through `capture` and cannot be ingested as complete readings.

For a later targeted reading of a version that already has a complete digest, find the relevant sections with `passage --outline` or `passage --grep`, read them completely with `passage --section`, write a targeted digest holding the new facets and findings, and merge it with the durable `manifest_path` that `lookup` returns:

```bash
python3 "<skill-dir>/scripts/literature_db.py" ingest --manifest "<manifest.json>" --digest "<targeted-digest.json>" --merge
```

A targeted digest needs only `schema_version`, `language`, `facets`, and `reading`. The merge keeps the paper-wide overview, accumulated records, and limitations; updates matching facet summaries; appends new findings, facets, and assessment points; merges sections and gists; and retries on concurrent changes. A merge with the same statement and locator replaces that finding in place, which also corrects a quote. Changed article content needs its own complete digest.

An approved repair starts with `backup`, rebuilds the complete digest from the stored article, and replaces it:

```bash
python3 "<skill-dir>/scripts/literature_db.py" ingest --manifest "<manifest.json>" --digest "<complete-replacement.json>" --replace-digest
```

Replacement requires an existing digest for that exact version and complete `full` or `visual` coverage. After ingest, inspect `classification_status` and assign missing topics with `annotate` or `organize` using the existing collection tree. Verify task completion with the checks in [Literature Research](../SKILL.md#literature-research); storage errors follow [failure routing](../SKILL.md#failure-routing).
