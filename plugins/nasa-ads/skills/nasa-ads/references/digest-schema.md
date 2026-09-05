# Layered Digest and Ingest

Load this reference when an investigated article version needs a new digest, a targeted merge, validation, ingest, or approved replacement. Apply the shared [reading scope](../SKILL.md#reading-scope).

Persistent tasks follow the complete digest and ingest procedure below. For an explicit no-library-write task, follow [SKILL.md](../SKILL.md#core-invariants): retain reading coverage and evidence traceability in the task's synthesis, and skip database ingest and replacement.

## Completion Standard

The library stores metadata records, abstract summaries, and complete article digests at distinct evidence levels. A complete article digest represents a completed reading of one exact article version. It contains verified artifact provenance plus a schema-version-2 digest. A complete digest covers every material scientific dimension found in the article and traces its claims to real article locations. Search-only records follow [literature-memory.md](literature-memory.md).

Digest depth follows the paper's evidence structure. Scientifically narrow articles can contain one principal question and one facet. Broad articles usually produce more facets and findings because their observables, samples, analyses, parameter regimes, result families, or inferential steps differ. The schema uses structural coverage and evidence traceability as its completion test.

The digest captures material dimensions across the paper so future work can retrieve them independently. Its depth and structure follow the article's evidence; the current research question guides the user-facing synthesis.

## Digest Layers

1. `overview`: paper-wide summary, significance, and research questions.
2. `keywords`: terms supporting later discovery.
3. `entities`: named sources, objects, surveys, instruments, simulations, catalogs, and aliases.
4. `datasets`: observing setup, sample, time span, spectral coverage, instruments, and identifiers.
5. `methods`: each major analysis method, its purpose, and retrieval terms.
6. `facets`: independently reusable scientific dimensions.
7. `findings`: atomic measurements, constraints, nondetections, interpretations, comparisons, methods, or limitations within each facet.
8. `global_limitations`: paper-wide selection effects, assumptions, and unresolved alternatives when present.
9. `data_products`: tables, catalogs, code, software, and availability information.
10. `reading`: reading status, sections, pages, visual ranges, unread sections, notes, and exact section coverage.

Generate the current skeleton:

```bash
python3 "<skill-dir>/scripts/literature_db.py" template
```

Required top-level fields are:

```text
schema_version
language
overview
keywords
entities
datasets
methods
facets
global_limitations
data_products
reading
```

The validator rejects unknown keys within structured records. This catches misspelled schema fields before storage.

## Facet Decomposition

Derive facets from the article. The schema has no domain vocabulary and no paper-length quota.

A facet answers an independent future scientific question and carries a distinguishable evidence chain. Separate facets when the paper uses materially different observables, samples, analyses, regimes, result families, mechanisms, predictions, or inferential steps. Combine statements that express the same result in different forms.

Apply this principle across paper types:

- observational work: distinct observables, populations, temporal or spectral behavior, correlations, constraints, and interpretations;
- theory: assumptions, derivations, regimes, mechanisms, predictions, degeneracies, and observational tests;
- simulations: setup, parameter dependence, convergence, emergent behavior, comparison with data, and failure modes;
- methods, instruments, and catalogs: inputs, algorithms, calibration, validation, performance, selection functions, products, and known failure cases;
- reviews: evidence clusters, competing explanations, agreements, disputed results, and open questions.

Entities, datasets, methods, and global limitations have dedicated layers. Create a facet when its scientific content benefits from independent retrieval. Use concise lowercase ASCII slugs for facet keys. Labels, aliases, summaries, and keywords can be multilingual.

## Atomic Findings

Every facet contains one or more findings. Each finding records:

- a concise paraphrased `statement`;
- `kind`: `measurement`, `constraint`, `interpretation`, `nondetection`, `method`, `comparison`, or `limitation`;
- `confidence`: `high`, `medium`, or `low`, calibrated to the article's evidence and wording;
- a `locator` containing at least one specific section, page, figure, table, equation, appendix, or paragraph hint;
- structured `values` with units, uncertainty, and qualifiers when relevant;
- retrieval `keywords`.

Record measurements and author interpretations as separate findings when their evidential status differs. Preserve uncertainty for tentative correlations, model preferences, and origin claims. Store concise paraphrases. Retrieve the article artifact for exact wording.

## Reading Coverage

`reading.status` accepts:

- `full`: all applicable introduction, data, methods, results, discussion, conclusions, limitations, appendices, references, and data/code statements were read;
- `visual`: every content-bearing page of a scan or sparse-text PDF was inspected, with explicit `visual_page_ranges`;
- `targeted`: complete sections relevant to requested topics were read for an exact version that already has a complete stored digest.

`full` and `visual` records keep `unread_sections` empty. `targeted` records describe remaining sections.

Every entry in `reading.sections` has exactly one matching `reading.coverage` record with these fields:

```text
section
role
facet_keys
notes
```

Use real article headings. Roles are `scientific`, `methods`, `context`, `limitations`, `data-products`, `references`, and `administrative`. Scientific sections list every facet they support. Methods, context, limitations, and data-product sections can also support facets. Each facet maps to at least one substantive section. References and administrative sections use an empty `facet_keys` list. Every section outside the scientific role includes a concise disposition note. Include the bibliography under `references` and record appendices or supplementary material according to their content.

The structural minimum for a complete digest consists of one research question, one facet, one finding in each facet, a real locator for every finding, complete section coverage, and an empty unread-section list. Additional content follows the article itself. `global_limitations` can remain empty when the article supplies no defensible paper-wide limitation.

## Validation and Ingest

Write the digest to a task-specific JSON file and validate it:

```bash
python3 "<skill-dir>/scripts/literature_db.py" validate-digest \
  "<digest.json>"
```

Ingest a newly completed exact version with the cache manifest produced by `fulltext.py`:

```bash
python3 "<skill-dir>/scripts/literature_db.py" ingest \
  --manifest "<manifest.json>" \
  --digest "<digest.json>"
```

The first complete ingest for an exact version accepts `full` or whole-document `visual` coverage. It verifies artifact, text, and canonical-content hashes when available, checks eligibility before object copying, reconciles identifiers, commits one SQLite transaction, and rebuilds the search document. `abstract_only` manifests can supply catalog metadata and abstract summaries through `capture`. Complete ingest requires readable full text or a visually read artifact. `needs_visual_reading` manifests require `visual` status and explicit page ranges covering every page within the recorded page count.

For a later targeted reading of an exact version with a complete digest, inspect the stored record, read the complete relevant sections, and merge the accumulated evidence:

```bash
python3 "<skill-dir>/scripts/literature_db.py" ingest \
  --manifest "<manifest.json>" \
  --digest "<targeted-digest.json>" \
  --merge
```

The merge preserves the existing paper-wide overview, accumulated record lists, detailed method descriptions, and limitations. It updates matching facet summaries, adds newly verified findings and facets, merges section coverage, and leaves one digest for the exact version. Concurrent changes trigger a retry. A changed canonical-content version requires its own complete `full` or `visual` digest. Use the durable `manifest_path` returned by `lookup` for local targeted reading and merge.

An approved repair starts with `literature_db.py backup`. Rebuild the complete digest from the stored article, then replace it:

```bash
python3 "<skill-dir>/scripts/literature_db.py" ingest \
  --manifest "<manifest.json>" \
  --digest "<complete-replacement.json>" \
  --replace-digest
```

Replacement requires an existing exact-version digest plus complete `full` or whole-document `visual` coverage. The backup supplies recovery.

Successful ingest stores the complete exact-version digest and saves its keywords as retrieval tags. Inspect `classification_status` and assign missing topic memberships through `annotate` or `organize`, using the existing collection tree. Verify task completion with the checks in [Literature Research](../SKILL.md#literature-research). Storage errors follow the shared [failure routing](../SKILL.md#failure-routing), which tracks verified scientific evidence and incomplete persistence separately.
