# Research and Manuscript Workflows

Load this reference for literature reviews and for manuscript introduction, methods, or discussion research. It refines the shared [Literature Research](../SKILL.md#literature-research) steps and [reading scope](../SKILL.md#reading-scope); library commands are in [literature-memory.md](literature-memory.md).

## Evidence Standard for Writing

Manuscript claims rest on complete readings. A citation often targets one specific result: a measurement, a fitted value, a derived constraint, a model prediction, or one inference in the paper's argument, wherever it appears in the article. Complete digests record each of these as a finding with its locator, so a sentence that states what a paper measured, fitted, assumed, predicted, observed, or inferred cites that finding and article version. Abstracts and metadata serve discovery and screening; when a cited paper is still at the abstract level, read it fully before the claim enters the manuscript, or flag the claim as abstract-level with the access gap.

Numbers in a manuscript come from stored values or from the article itself, never from memory or an abstract paraphrase.

## Cite Specific Results

Find the target with `findings` for statements and inferences, or `parameters` for numbers; [query stored evidence](literature-memory.md#query-stored-evidence) lists the filters. For each cited result:

1. Match the sentence to the row's evidential status: a `measured` value as a measurement, a `fitted` value with its `model`, an `interpretation` as the authors' inference, a `prediction` with the model that produces it, and a limit as a limit.
2. Carry the value with its `uncertainty`, `unit`, `qualifier`, and `condition`, and keep the `dataset`, `method`, and `model` that bound it in the sentence or its caveats.
3. A row with `cited_from` restates another work's result. Read and cite that original source; cite the restating paper for its own use or reanalysis of the result.
4. Before the sentence is final, run `passage "<citekey>" --finding "<finding_id>"`, since digests store paraphrases, and check the number, sign, exponent, and the authors' wording of the inference in the returned paragraph. Add `--context 1` or read the `--section` when the paragraph lacks the needed setup.
5. When the needed result is absent from a complete digest, find it with `passage --grep`, read its complete section with `passage --section`, and merge it as a [targeted reading](digest-schema.md#validation-and-ingest) before citing it.
6. An `assessment` point is the reader's evaluation of the paper. A manuscript states it as its own argument, supported by the findings it rests on.

## Plan the Search

State the scientific question, population or physical regime, time range, required evidence, and target manuscript section. Search existing summaries, findings, methods, entities, and parameters first; reuse verified versions and cached citations. Search SciX for missing coverage, newly published work, updated versions, and citation relationships.

Record queries, filters, dates, pagination, screening rules, and the searched source. Track selections and exclusions so the synthesis scope and any unfinished reading stay traceable; `runs` shows retrieval counts and summary progress.

## Review

Choose query families that cover the terminology, physical mechanisms, observations, methods, and competing explanations in scope. Include foundational, representative, contradictory, and method-defining work. Compare questions, samples, data, methods, findings, uncertainties, limitations, and exact versions; an evidence matrix built from `findings` and `parameters` rows keeps substantial comparisons consistent. Group the synthesis around scientific questions and explain agreement, disagreement, and coverage gaps with traceable evidence. A comprehensive or systematic review states its coverage and screening protocol.

## Introduction

Assign the `intro` role. Retrieve foundational results, the current observational or theoretical state, competing explanations, and the specific open question the manuscript addresses. Check the primary papers behind decisive historical or quantitative claims, connect each planned claim to its evidence, and state the scope over which it holds.

## Methods

Assign the `methods` role. Retrieve original algorithms, calibration and preprocessing procedures, estimator definitions, assumptions, validation studies, and known failure conditions. Inspect equations, units, parameter choices, selection functions, and implementation details in the stored article, and compare the intended use with the conditions validated in the cited work. Digest `methods` entries and `fixed` or `assumed` values make these conditions queryable.

## Discussion

Assign the `discussion` or `comparison` role. Before comparing reported values, compare samples, observational coverage, preprocessing, estimators, models, uncertainties, and selection effects; the `dataset`, `method`, `model`, and `condition` fields of each value support this. Separate measurements, author interpretations, model-dependent predictions, and the present manuscript's inference. Retrieve contrary evidence and state unresolved differences; `findings "<work>" --kind comparison` lists stored comparisons with a given work, which `compared_with` names.

## Claim-to-Evidence Handoff

For drafting, give the writer, or a manuscript-writing skill, one record per planned claim:

| Field | Source |
|---|---|
| Claim | The sentence or point the manuscript makes |
| Evidence | The `findings` row, and the `parameters` row for each number |
| Evidential status | Finding `kind` and value `status`, such as fitted value or author inference |
| Locator and version | Finding `locator` and `finding_id`, version kind, reading status, and whether the passage was rechecked |
| Citation key | `citekey` of the paper, or of the original source for rows with `cited_from` |
| Scope and caveats | Sample, model, condition, and limitations that bound the claim |

Export the matching bibliography with `citations --collection "<manuscript collection>" --output <file.bib>` or by identifiers; fetch official entries with `--fetch` before submission. Keep project-specific relevance in notes and the manuscript collection; reusable scientific evidence stays in each paper's digest. Apply the shared [completion and handoff](../SKILL.md#completion-and-handoff) criteria.
