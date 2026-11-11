from __future__ import annotations

import hashlib
import importlib
import importlib.util
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "plugins" / "nasa-ads" / "skills" / "nasa-ads" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "literature_db.py"
sys.path.insert(0, str(SCRIPTS_DIR))
SPEC = importlib.util.spec_from_file_location("nasa_ads_literature_db", SCRIPT_PATH)
assert SPEC and SPEC.loader
literature_db = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = literature_db
SPEC.loader.exec_module(literature_db)


def sample_digest(*, facets: list[dict] | None = None) -> dict:
    default_facets = [
        {
            "key": "activity-event-rate",
            "label": "活跃性与事件率",
            "aliases": ["activity", "burst rate", "event rate", "事件率"],
            "summary": "The source was highly active during the observing campaign.",
            "keywords": ["repeater", "rate"],
            "findings": [
                {
                    "statement": (
                        "The campaign detected 1076 bursts and reached 390 per hour."
                    ),
                    "kind": "measurement",
                    "confidence": "high",
                    "locator": {"section": "3.1", "figure": "1"},
                    "quote": "we detected 1076 bursts in total",
                    "values": [
                        {"name": "burst count", "value": 1076, "unit": "bursts"},
                        {"name": "maximum rate", "value": 390, "unit": "hr^-1"},
                    ],
                    "keywords": ["burst count", "maximum event rate"],
                },
                {
                    "statement": "The activity varied strongly between sessions.",
                    "kind": "measurement",
                    "confidence": "high",
                    "locator": {"section": "3.1", "table": "1"},
                    "quote": "the burst rate varied strongly between sessions",
                    "values": [],
                    "keywords": ["session variability"],
                },
            ],
            "methods": ["burst search"],
        },
        {
            "key": "circular-polarization",
            "label": "圆偏振属性",
            "aliases": ["circular polarization", "Stokes V", "圆偏振"],
            "summary": (
                "Many bursts showed strong and morphologically complex "
                "circular polarization."
            ),
            "keywords": ["polarimetry", "radiation mechanism"],
            "findings": [
                {
                    "statement": (
                        "Circular polarization can reverse sign across time "
                        "or frequency."
                    ),
                    "kind": "measurement",
                    "confidence": "high",
                    "locator": {"section": "3.3", "figure": "9"},
                    "quote": "circular polarization reverses sign",
                    "values": [],
                    "keywords": ["sign reversal", "time-frequency morphology"],
                },
                {
                    "statement": "The high-quality RM sample remained near zero.",
                    "kind": "measurement",
                    "confidence": "high",
                    "locator": {"section": "3.3", "figure": "1"},
                    "quote": "the rotation measure stays close to zero",
                    "values": [{"name": "mean RM", "value": -0.08, "unit": "rad m^-2"}],
                    "keywords": ["rotation measure"],
                },
            ],
            "methods": ["RM synthesis"],
        },
    ]
    chosen_facets = facets if facets is not None else default_facets
    gists = {
        "1": "Repeater activity and polarization constrain emission models.",
        "2": "FAST L-band observing setup and the burst search.",
        "3.1": "Burst detections and the event rate across sessions.",
        "3.2": "Waiting times and spectral bandwidths of the bursts.",
        "3.3": "Polarization measurements and rotation measures.",
        "4": "Implications for the emission mechanism and the local environment.",
        "5": "Summary of the campaign and its main results.",
    }
    digest = {
        "schema_version": literature_db.DIGEST_SCHEMA_VERSION,
        "language": "zh-CN",
        "overview": {
            "tldr": "FAST measured the activity and polarization of FRB 20220912A.",
            "summary": (
                "FAST measured burst statistics and polarization for FRB 20220912A."
            ),
            "questions": [
                "What controls repeater activity?",
                "What do the polarization measurements imply?",
            ],
            "study_types": ["observational"],
        },
        "keywords": ["fast radio burst", "FAST", "FRB 20220912A"],
        "entities": [
            {
                "name": "FRB 20220912A",
                "type": "source",
                "description": "An active localized repeater.",
                "aliases": ["FRB20220912A"],
            }
        ],
        "datasets": [
            {
                "name": "FAST 2022 campaign",
                "type": "observation",
                "description": (
                    "Seventeen FAST L-band observations at 1-1.5 GHz in 2022 "
                    "October-December, yielding 1076 bursts."
                ),
                "identifiers": ["ScienceDB 10.57760/sciencedb.08058"],
            }
        ],
        "methods": [
            {
                "name": "burst search",
                "description": "A classifier cross-checked with PRESTO detects bursts.",
            },
            {
                "name": "RM synthesis",
                "description": "Faraday rotation fitting of calibrated spectra.",
            },
        ],
        "facets": chosen_facets,
        "global_limitations": ["The observations cover only the FAST L band."],
        "assessment": [],
        "data_products": [
            {
                "name": "Burst property table",
                "type": "table",
                "url": "https://doi.org/10.57760/sciencedb.08058",
                "availability": "Machine-readable table",
                "locator": "Table 1",
            }
        ],
        "reading": {
            "status": "full",
            "sections": [
                {"heading": heading, "gist": gist} for heading, gist in gists.items()
            ],
            "notes": "Publisher HTML was read in full.",
        },
    }
    # Fixture facets name their methods freely and omit value statuses.
    known_methods = {method["name"].casefold() for method in digest["methods"]}
    for facet in digest["facets"]:
        for name in facet.get("methods", []):
            if name.casefold() not in known_methods:
                digest["methods"].append({"name": name})
                known_methods.add(name.casefold())
        for finding in facet["findings"]:
            for value in finding.get("values", []):
                value.setdefault("status", "measured")
    return digest


def schema3_digest() -> dict:
    """A schema 3 record as the previous release stored it."""
    digest = sample_digest()
    digest["schema_version"] = 3
    tldr = digest["overview"].pop("tldr")
    digest["overview"]["summary"] = tldr + " The campaign also measured rotation measures."
    digest["overview"]["significance"] = "It links activity and polarization."
    digest["datasets"][0].update(instrument="FAST", frequency="1-1.5 GHz")
    digest["methods"][0].update(purpose="Detect bursts.", keywords=["PRESTO"])
    for facet in digest["facets"]:
        facet.setdefault("aliases", [])
        for finding in facet["findings"]:
            finding.pop("quote", None)
            finding.setdefault("keywords", [])
    sections = [
        section["heading"] if isinstance(section, dict) else section
        for section in digest["reading"]["sections"]
    ]
    facet_keys = [facet["key"] for facet in digest["facets"]]
    digest["reading"].update(
        sections=[*sections, "References"],
        page_ranges=[],
        visual_page_ranges=[],
        unread_sections=[],
        coverage=[
            *(
                {
                    "section": section,
                    "role": "scientific" if section in {"3.1", "3.3"} else "context",
                    "facet_keys": facet_keys if section in {"3.1", "3.3"} else [],
                    "notes": "" if section in {"3.1", "3.3"} else "Read and reviewed.",
                }
                for section in sections
            ),
            {
                "section": "References",
                "role": "references",
                "facet_keys": [],
                "notes": "Checked cited works.",
            },
        ],
    )
    return digest


def legacy_digest() -> dict:
    """A schema 2 record as earlier releases stored it."""
    digest = schema3_digest()
    digest["schema_version"] = 2
    digest["overview"].pop("study_types")
    digest.pop("assessment")
    digest["entities"][0]["type"] = "repeating FRB"
    digest["datasets"][0].pop("type")
    digest["facets"][0]["limitations"] = [
        "The measured rate depends on observing cadence."
    ]
    digest["facets"][1]["methods"] = ["polarization calibration", "RM synthesis"]
    for facet in digest["facets"]:
        for finding in facet["findings"]:
            for value in finding["values"]:
                value.pop("status", None)
    digest["facets"][1]["findings"][1]["values"].append(
        {"name": "RM upper limit", "value": 0.1, "qualifier": "3 sigma upper limit"}
    )
    return digest


def in_chinese(digest: dict) -> dict:
    """Mark the fixture's prose as Chinese, as the authoring commands require."""

    def mark(text: str) -> str:
        return "中文：" + text

    digest["language"] = "zh-CN"
    overview = digest.get("overview", {})
    for field in ("tldr", "summary"):
        if overview.get(field):
            overview[field] = mark(overview[field])
    overview["questions"] = [mark(item) for item in overview.get("questions", [])]
    for layer in ("datasets", "methods"):
        for record in digest.get(layer, []):
            if record.get("description"):
                record["description"] = mark(record["description"])
    for facet in digest["facets"]:
        facet["summary"] = mark(facet["summary"])
        for finding in facet["findings"]:
            finding["statement"] = mark(finding["statement"])
    for section in digest["reading"]["sections"]:
        if isinstance(section, dict) and section.get("gist"):
            section["gist"] = mark(section["gist"])
    for field in ("global_limitations", "assessment"):
        digest[field] = [mark(item) for item in digest.get(field, [])]
    return digest


def current_digest(*, facets: list[dict] | None = None) -> dict:
    """The shared fixture with an assessment, mixed statuses, and a limitation."""
    digest = sample_digest(facets=facets)
    digest["assessment"] = [
        "The RM sample is restricted to high signal-to-noise bursts."
    ]
    if facets is None:
        statuses = iter(["measured", "measured", "derived"])
        for facet in digest["facets"]:
            for finding in facet["findings"]:
                for value in finding["values"]:
                    value["status"] = next(statuses)
        digest["facets"][0]["findings"].append(
            {
                "statement": "The measured rate depends on observing cadence.",
                "kind": "limitation",
                "confidence": "high",
                "locator": {"section": "4"},
                "quote": "the measured rate depends on the observing cadence",
                "values": [],
                "keywords": ["cadence"],
            }
        )
    return digest


def sample_manifest(
    root: Path,
    *,
    body: bytes = b"<html>article one</html>",
    text_body: str = (
        "This full article contains a unique micropulse avalanche discussion.\n"
        "It also reports waiting times, spectral bandwidth, and polarization."
    ),
) -> dict:
    artifact = root / "publisher.html"
    text = root / "publisher.txt"
    artifact.write_bytes(body)
    text.write_text(text_body, encoding="utf-8")
    artifact_hash = hashlib.sha256(body).hexdigest()
    return {
        "schema_version": 1,
        "tool_version": "1.12.0",
        "status": "fulltext",
        "created_at": "2026-08-25T00:00:00Z",
        "input": "2023ApJ...955..142Z",
        "input_type": "bibcode",
        "normalized_identifier": "2023ApJ...955..142Z",
        "bibcode": "2023ApJ...955..142Z",
        "title": "FAST Observations of FRB 20220912A",
        "author": ["Zhang, Y. K.", "Li, D."],
        "abstract": "FAST detected many bursts and measured their polarization.",
        "doi": ["10.3847/1538-4357/aced0b", "10.48550/arXiv.2304.14665"],
        "arxiv_ids": ["2304.14665"],
        "property": ["REFEREED", "OPENACCESS"],
        "doctype": "article",
        "year": "2023",
        "pub": "The Astrophysical Journal",
        "citation_count": 122,
        "read_count": 266,
        "selected": {
            "candidate": {
                "source": "publisher",
                "version": "published",
                "format": "html",
            },
            "actual_format": "html",
            "final_url": "https://example.org/article",
            "artifact_path": str(artifact),
            "text_path": str(text),
            "sha256": artifact_hash,
            "retrieved_at": "2026-08-25T00:00:00Z",
            "status": "fulltext",
            "statistics": {"words": 7000, "pages": None},
        },
        "warnings": [],
    }


class DigestValidationTests(unittest.TestCase):
    def test_rich_digest_is_valid(self):
        digest = literature_db.validate_digest(sample_digest())
        self.assertEqual(len(digest["facets"]), 2)
        self.assertEqual(digest["reading"]["status"], "full")

    def test_facet_requires_atomic_findings_and_locator(self):
        digest = sample_digest()
        digest["facets"][0]["findings"] = []
        with self.assertRaises(literature_db.LiteratureError):
            literature_db.validate_digest(digest)

    def test_unknown_nested_fields_are_rejected(self):
        digest = sample_digest()
        digest["facets"][0]["sumary"] = "misspelled summary"
        with self.assertRaisesRegex(
            literature_db.LiteratureError, "unsupported fields: sumary"
        ):
            literature_db.validate_digest(digest)

    def test_equation_locator_is_accepted(self):
        digest = sample_digest()
        digest["facets"][0]["findings"][0]["locator"] = {
            "section": "Methods",
            "equation": "Equation 7",
        }

        validated = literature_db.validate_digest(digest)

        self.assertEqual(
            validated["facets"][0]["findings"][0]["locator"]["equation"],
            "Equation 7",
        )

    def test_scientific_latex_math_environment_is_accepted(self):
        digest = sample_digest()
        digest["facets"][0]["findings"][0]["statement"] = (
            r"The fitted relation is represented by \begin{aligned} y=ax+b \end{aligned}."
        )
        validated = literature_db.validate_digest(digest)
        self.assertIn(
            r"\begin{aligned}",
            validated["facets"][0]["findings"][0]["statement"],
        )

    def test_full_reading_requires_a_research_question(self):
        digest = sample_digest()
        digest["overview"]["questions"] = []
        with self.assertRaisesRegex(
            literature_db.LiteratureError, "at least one research question"
        ):
            literature_db.validate_digest(digest)

    def test_complete_narrow_digest_is_valid(self):
        digest = sample_digest(facets=[sample_digest()["facets"][0]])
        digest["facets"][0]["findings"] = digest["facets"][0]["findings"][:1]
        digest["overview"]["questions"] = digest["overview"]["questions"][:1]
        digest["global_limitations"] = []

        validated = literature_db.validate_digest(digest)

        self.assertEqual(len(validated["overview"]["questions"]), 1)
        self.assertEqual(len(validated["facets"]), 1)
        self.assertEqual(len(validated["facets"][0]["findings"]), 1)
        self.assertEqual(validated["global_limitations"], [])

    def test_complete_digest_rejects_unread_sections(self):
        digest = sample_digest()
        digest["reading"]["unread_sections"] = ["Appendix A"]
        with self.assertRaisesRegex(
            literature_db.LiteratureError, "cannot list unread sections"
        ):
            literature_db.validate_digest(digest)

    def test_legacy_digest_is_rejected(self):
        digest = sample_digest()
        digest["schema_version"] = 1
        with self.assertRaisesRegex(
            literature_db.LiteratureError, "schema_version must be 4"
        ):
            literature_db.validate_digest(digest)

    def test_facets_are_domain_agnostic_and_not_a_fixed_ontology(self):
        digest = sample_digest(
            facets=[
                {
                    "key": "simulation-convergence",
                    "label": "Numerical convergence",
                    "aliases": ["resolution convergence", "收敛性"],
                    "summary": (
                        "The inferred structure is stable above the stated resolution."
                    ),
                    "keywords": ["simulation", "resolution study"],
                    "findings": [
                        {
                            "statement": (
                                "The target observable changes by less than "
                                "3% between the two highest-resolution runs."
                            ),
                            "kind": "constraint",
                            "confidence": "high",
                            "locator": {"section": "4.2", "table": "3"},
                            "values": [
                                {
                                    "name": "relative change",
                                    "value": 3,
                                    "unit": "%",
                                    "qualifier": "upper bound",
                                }
                            ],
                            "keywords": ["convergence test", "numerical resolution"],
                        }
                    ],
                    "methods": ["resolution study"],
                },
                {
                    "key": "observable-predictions",
                    "label": "Observable predictions",
                    "aliases": ["testable predictions", "观测预言"],
                    "summary": "The model predicts a separately testable signature.",
                    "keywords": ["theory", "future test"],
                    "findings": [
                        {
                            "statement": (
                                "The signature should appear only inside the "
                                "specified parameter regime."
                            ),
                            "kind": "interpretation",
                            "confidence": "medium",
                            "locator": {"section": "5"},
                            "values": [],
                            "keywords": ["parameter regime", "prediction"],
                        }
                    ],
                    "methods": ["analytic model"],
                },
            ]
        )
        digest["overview"] = {
            "summary": (
                "A numerical and analytic study of an arbitrary physical system."
            ),
            "questions": ["Are the results converged?", "How can the model be tested?"],
            "study_types": ["simulation", "theoretical"],
        }
        digest["keywords"] = ["numerical simulation", "analytic theory"]
        digest["entities"] = []
        digest["datasets"] = []
        digest["methods"] = [
            {
                "name": "resolution study",
                "description": "Three numerical resolutions were compared.",
            }
        ]
        digest["reading"].update(
            {
                "status": "targeted",
                "unread_sections": ["Other scientific dimensions"],
            }
        )
        validated = literature_db.validate_digest(digest)
        self.assertEqual(
            [facet["key"] for facet in validated["facets"]],
            ["simulation-convergence", "observable-predictions"],
        )

        digest = sample_digest()
        digest["facets"][0]["findings"][0]["locator"] = {}
        with self.assertRaises(literature_db.LiteratureError):
            literature_db.validate_digest(digest)

    def test_template_is_intentionally_incomplete(self):
        template = literature_db.digest_template()
        self.assertEqual(
            template["schema_version"], literature_db.DIGEST_SCHEMA_VERSION
        )
        with self.assertRaises(literature_db.LiteratureError):
            literature_db.validate_digest(template)

    def test_experiment_and_fit_parameter_fields_are_accepted(self):
        digest = sample_digest()
        digest["datasets"][0].update(
            type="observation", description="19-beam receiver, 49.152 us sampling."
        )
        digest["methods"][0].update(assumptions=["Bursts are independent events."])
        digest["facets"][0]["findings"][0]["values"].append(
            {
                "name": "Weibull shape",
                "symbol": "k",
                "value": 0.75,
                "uncertainty": "+0.05/-0.04",
                "qualifier": "68% credible interval",
                "status": "fitted",
                "model": "Weibull waiting-time distribution",
                "dataset": "FAST 2022 campaign",
                "method": "burst search",
                "condition": "1-1.5 GHz",
            }
        )
        validated = literature_db.validate_digest(digest)
        value = validated["facets"][0]["findings"][0]["values"][-1]
        self.assertEqual(value["status"], "fitted")
        self.assertEqual(validated["methods"][0]["assumptions"], ["Bursts are independent events."])

    def test_value_status_uses_a_controlled_vocabulary(self):
        digest = sample_digest()
        digest["facets"][0]["findings"][0]["values"][0]["status"] = "guessed"
        with self.assertRaises(literature_db.LiteratureError):
            literature_db.validate_digest(digest)

    def test_blank_optional_fields_from_the_template_are_dropped(self):
        digest = sample_digest()
        digest["entities"][0]["description"] = ""
        digest["facets"][0]["findings"][0]["values"][0].update(
            symbol="", qualifier="", model="  "
        )
        validated = literature_db.validate_digest(digest)
        self.assertNotIn("description", validated["entities"][0])
        value = validated["facets"][0]["findings"][0]["values"][0]
        for field in ("symbol", "qualifier", "model"):
            self.assertNotIn(field, value)

    def test_findings_accept_predictions_and_attribution(self):
        digest = sample_digest()
        finding = digest["facets"][0]["findings"][0]
        finding.update(kind="prediction", cited_from="Zhou et al. 2022")
        finding["values"][0]["cited_from"] = "2022RAA....22l4001Z"
        digest["facets"][0]["findings"][1]["cited_from"] = " "
        validated = literature_db.validate_digest(digest)
        first, second = validated["facets"][0]["findings"]
        self.assertEqual(first["kind"], "prediction")
        self.assertEqual(first["cited_from"], "Zhou et al. 2022")
        self.assertEqual(first["values"][0]["cited_from"], "2022RAA....22l4001Z")
        self.assertNotIn("cited_from", second)


class DigestSchemaFourTests(unittest.TestCase):
    def test_schema_four_is_the_authoring_standard(self):
        digest = literature_db.validate_digest(current_digest())
        self.assertEqual(digest["schema_version"], 4)
        self.assertNotIn("limitations", digest["facets"][0])
        self.assertEqual(literature_db.digest_warnings(digest), [])
        template = literature_db.digest_template()
        self.assertEqual(template["schema_version"], literature_db.DIGEST_SCHEMA_VERSION)
        self.assertIn("assessment", template)
        self.assertNotIn("limitations", template["facets"][0])

    def test_schema_four_rejects_legacy_shortcuts(self):
        cases = [
            (lambda d: d["overview"].pop("study_types"), "study_types"),
            (lambda d: d["overview"].update(study_types=["opinion"]), "study_types"),
            (lambda d: d["overview"].pop("tldr"), "overview.tldr"),
            (lambda d: d["reading"].update(coverage=[]), "unsupported fields: coverage"),
            (lambda d: d["overview"].update(significance="x"), "unsupported fields: significance"),
            (lambda d: d["datasets"][0].update(instrument="FAST"), "unsupported fields: instrument"),
            (
                lambda d: d["entities"][0].update(type="repeating FRB"),
                r"entities\[0\]\.type",
            ),
            (lambda d: d["datasets"][0].pop("type"), r"datasets\[0\]\.type"),
            (lambda d: d["facets"][0].update(limitations=["x"]), "unsupported fields: limitations"),
            (
                lambda d: d["facets"][1].update(methods=["polarization calibration"]),
                "digest.methods",
            ),
            (
                lambda d: d["facets"][0]["findings"][0]["values"][0].pop("status"),
                "status is required",
            ),
            (
                lambda d: d["facets"][0]["findings"][0]["values"][0].update(
                    dataset="GBT archive"
                ),
                "digest.datasets",
            ),
        ]
        for change, message in cases:
            with self.subTest(message=message):
                digest = current_digest()
                change(digest)
                with self.assertRaisesRegex(literature_db.LiteratureError, message):
                    literature_db.validate_digest(digest)

    def test_values_accept_ranges_and_resolve_references(self):
        digest = current_digest()
        values = digest["facets"][0]["findings"][0]["values"]
        values.append(
            {
                "name": "dispersion measure span",
                "value": "",
                "range": [100, 400],
                "unit": "pc cm^-3",
                "status": "measured",
                "dataset": "fast 2022 campaign",
                "method": "Burst Search",
            }
        )
        added = literature_db.validate_digest(digest)["facets"][0]["findings"][0][
            "values"
        ][-1]
        self.assertEqual(added["range"], [100, 400])
        self.assertNotIn("value", added)
        self.assertEqual(
            literature_db.value_text(added),
            "dispersion measure span = [100, 400] pc cm^-3 [measured]",
        )
        # Bounds written as strings keep their printed digits.
        values[-1]["range"] = [" 57175.743510388", "5.7176e4"]
        printed = literature_db.validate_digest(digest)["facets"][0]["findings"][0][
            "values"
        ][-1]
        self.assertEqual(printed["range"], ["57175.743510388", "5.7176e4"])
        self.assertIn("[57175.743510388, 5.7176e4]", literature_db.value_text(printed))
        for bad in (
            [400, 100],
            ["6e-3", "5e-3"],
            [1],
            [1, "about 2"],
            ["nan", 1],
            [True, 2],
            "100-400",
        ):
            with self.subTest(bad=bad):
                values[-1]["range"] = bad
                with self.assertRaisesRegex(literature_db.LiteratureError, "range"):
                    literature_db.validate_digest(digest)
        values[-1] = {"name": "dispersion measure", "status": "measured"}
        with self.assertRaisesRegex(literature_db.LiteratureError, "give a range"):
            literature_db.validate_digest(digest)

    def test_attribution_and_locators_on_datasets_and_methods(self):
        digest = current_digest()
        digest["datasets"][0].update(
            locator={"section": "2.1", "table": "1"}, cited_from="Zhang et al. 2023"
        )
        digest["methods"][0].update(locator={"section": ""}, cited_from="")
        digest["facets"][1]["findings"][1]["compared_with"] = [
            "Hilmarsson et al. 2021",
            " ",
        ][:1]
        validated = literature_db.validate_digest(digest)
        self.assertEqual(validated["datasets"][0]["locator"], {"section": "2.1", "table": "1"})
        self.assertNotIn("locator", validated["methods"][0])
        self.assertNotIn("cited_from", validated["methods"][0])
        self.assertEqual(
            validated["facets"][1]["findings"][1]["compared_with"],
            ["Hilmarsson et al. 2021"],
        )

    def test_targeted_digests_defer_reference_checks(self):
        digest = current_digest()
        digest["reading"].update(status="targeted", unread_sections=["Earlier sections"])
        digest["datasets"] = []
        digest["facets"][0]["findings"][0]["values"][0]["dataset"] = "FAST 2022 campaign"
        literature_db.validate_digest(digest)
        with self.assertRaisesRegex(literature_db.LiteratureError, "digest.datasets"):
            literature_db.validate_digest(digest, check_references=True)

    def test_warnings_keep_digests_at_citation_level(self):
        digest = current_digest()
        finding = digest["facets"][0]["findings"][0]
        finding["locator"] = {"section": "3.1; Table 2"}
        finding["cited_from"] = "Zhou et al. 2022; Li et al. 2021"
        finding["values"][0].update(status="fitted", value=7.399999999999999e27)
        finding["values"].extend(
            {"name": f"burst {index} DM", "value": 560, "status": "measured"}
            for index in range(15)
        )
        messages = {
            warning["message"]
            for warning in literature_db.digest_warnings(
                literature_db.validate_digest(digest)
            )
        }
        for expected in (
            "summarize long tables",
            "own locator fields",
            "split findings",
            "Copy the value as printed",
            "Name the model",
        ):
            with self.subTest(expected=expected):
                self.assertTrue(any(expected in message for message in messages))
        digest = current_digest()
        digest["facets"][1]["findings"][1]["values"] = [
            {"name": f"row {index}", "value": index, "status": "measured"}
            for index in range(151)
        ]
        paths = [
            warning["path"]
            for warning in literature_db.digest_warnings(
                literature_db.validate_digest(digest)
            )
        ]
        self.assertIn("facets", paths)

    def test_labels_and_expressions_are_not_numbers_left_in_prose(self):
        digest = current_digest()
        findings = digest["facets"][1]["findings"]

        def flagged(statement):
            findings[0]["statement"] = statement
            findings[0].pop("values", None)
            return "facets[1].findings[0]" in [
                warning["path"]
                for warning in literature_db.digest_warnings(
                    literature_db.validate_digest(json.loads(json.dumps(digest)))
                )
            ]

        for statement in (
            "式 2 的折断幂律拟合累计分布，图 3 给出结果。",
            "第 3 阶段没有硬 X 射线对应体，耀斑主要来自 AR 12241。",
            "Abell 370 相对标度关系偏暗；高能渐近斜率为 β+1。",
            "Stage 3 lacks a hard X-ray counterpart.",
        ):
            self.assertFalse(flagged(statement), statement)
        self.assertTrue(flagged("平均 RM 为 -411 rad/m2。"))
        self.assertTrue(flagged("上限为 6%（1652 个爆发）。"))

    def test_warnings_flag_numbers_left_in_prose(self):
        digest = current_digest()
        findings = digest["facets"][1]["findings"]
        findings[0]["statement"] = "About 40 percent of bursts in Figure 9 reverse sign."
        findings[1]["values"] = [
            {"name": "RM limit", "value": "<0.1", "unit": "rad m^-2", "status": "upper-limit"},
            {"name": "RM", "value": "0.49 +/- 0.08", "status": "measured"},
            {"name": "DM span", "value": "100-400", "status": "measured"},
            {"name": "widths", "value": "0.23, 0.22", "status": "measured"},
            {"name": "rate", "value": 2, "qualifier": "plus or minus 0.5", "status": "measured"},
            {"name": "precise", "value": "1.2e-3", "status": "measured"},
            {"name": "count", "value": "1,076", "status": "measured"},
        ]
        warnings = literature_db.digest_warnings(literature_db.validate_digest(digest))
        self.assertEqual(
            [warning["path"] for warning in warnings],
            [
                "facets[1].findings[0]",
                *[f"facets[1].findings[1].values[{index}]" for index in range(5)],
            ],
        )


class LibraryWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.library = self.root / "library"
        self.source = self.root / "source"
        self.source.mkdir()
        self.connection, self.fts5 = literature_db.connect_library(self.library)

    def tearDown(self):
        self.connection.close()
        self.temporary.cleanup()

    def ingest(
        self,
        *,
        manifest: dict | None = None,
        digest: dict | None = None,
        merge=False,
        replace_digest=False,
    ):
        chosen_manifest = manifest or sample_manifest(self.source)
        chosen_digest = digest or sample_digest()
        return literature_db.ingest_record(
            self.connection,
            self.fts5,
            self.library,
            chosen_manifest,
            chosen_digest,
            merge=merge,
            replace_digest=replace_digest,
        )

    def test_ingest_copies_fulltext_and_resolves_all_aliases(self):
        result = self.ingest()
        self.assertEqual(result["status"], "ingested")
        self.assertTrue(Path(result["object_paths"]["artifact"]).is_file())
        self.assertTrue(Path(result["object_paths"]["text"]).is_file())
        for identifier in (
            "2023ApJ...955..142Z",
            "10.3847/1538-4357/aced0b",
            "arXiv:2304.14665",
        ):
            lookup = literature_db.lookup_one(
                self.connection,
                identifier,
                topics=[],
                artifact_hash=None,
                include_digest=False,
            )
            self.assertTrue(lookup["found"])
            self.assertEqual(lookup["reuse_status"], "reusable")
            self.assertEqual(lookup["open_gate_action"], "reuse_complete_record")
            self.assertFalse(lookup["complete_ingest_required"])

    def test_lookup_exposes_per_article_open_gate(self):
        missing = literature_db.lookup_one(
            self.connection,
            "2023ApJ...955..142Z",
            topics=["one requested figure"],
            artifact_hash=None,
            include_digest=False,
        )
        self.assertEqual(missing["reuse_status"], "not_found")
        self.assertEqual(missing["open_gate_action"], "complete_ingest")
        self.assertTrue(missing["complete_ingest_required"])

        self.ingest()
        uncovered = literature_db.lookup_one(
            self.connection,
            "2023ApJ...955..142Z",
            topics=["energy distribution"],
            artifact_hash=None,
            include_digest=False,
        )
        self.assertEqual(uncovered["reuse_status"], "targeted_reading")
        self.assertEqual(uncovered["open_gate_action"], "targeted_merge")
        self.assertFalse(uncovered["complete_ingest_required"])

    def test_lookup_topics_match_values_quotes_and_named_objects(self):
        digest = sample_digest()
        digest["facets"][0]["findings"][0]["values"].append(
            {
                "name": "spin-down timescale",
                "value": "5e-3",
                "unit": "s",
                "status": "predicted",
                "model": "pair cascade",
            }
        )
        self.ingest(digest=digest)
        for topic in ("spin-down", "pair cascade", "1076 bursts in total", "FRB 20220912A"):
            with self.subTest(topic=topic):
                result = literature_db.lookup_one(
                    self.connection,
                    "2023ApJ...955..142Z",
                    topics=[topic],
                    artifact_hash=None,
                    include_digest=False,
                )
                self.assertEqual(result["reuse_status"], "reusable")
                self.assertEqual(result["matched_topics"], [topic])

    def test_quote_anchors_ignore_exponent_markup(self):
        self.assertEqual(
            literature_db.text_skeleton("2 × 10^{16} G s^{−1}")[0],
            literature_db.text_skeleton("2 × 1016 G s−1")[0],
        )

    def test_visual_ingest_keeps_raw_artifact_content_identity(self):
        manifest = sample_manifest(self.source)
        artifact = Path(manifest["selected"]["artifact_path"])
        artifact.write_bytes(b"%PDF-1.7\nscanned pages")
        artifact_hash = literature_db.fulltext.sha256_file(artifact)
        manifest["status"] = "needs_visual_reading"
        manifest["selected"].update(
            {
                "candidate": {
                    "source": "ads",
                    "version": "scan",
                    "format": "pdf",
                },
                "actual_format": "pdf",
                "sha256": artifact_hash,
                "content_sha256": artifact_hash,
                "status": "needs_visual_reading",
                "statistics": {"words": 2, "pages": 12},
            }
        )
        digest = sample_digest()
        digest["reading"].update(
            {
                "status": "visual",
                "sections": [{"heading": "Pages 1-12 scientific content"}],
                "visual_page_ranges": ["1-12"],
                "notes": "All twelve rendered pages were inspected.",
            }
        )

        result = self.ingest(manifest=manifest, digest=digest)

        self.assertEqual(result["content_sha256"], artifact_hash)
        version = literature_db.preferred_version(
            self.connection, int(result["paper_id"])
        )
        self.assertIsNotNone(version)
        self.assertEqual(version["content_sha256"], artifact_hash)
        self.assertEqual(version["reading_status"], "visual")
        audit = literature_db.audit_library(
            self.connection,
            self.fts5,
            self.library,
            verify_hashes=True,
        )
        self.assertEqual(audit["errors"], [])

    def test_new_paper_rejects_targeted_first_ingest(self):
        digest = sample_digest()
        digest["reading"].update(
            {
                "status": "targeted",
                "unread_sections": ["Sections unrelated to the current claim"],
            }
        )
        with self.assertRaisesRegex(
            literature_db.LiteratureError, "exact article version"
        ):
            self.ingest(digest=digest)
        stats = literature_db.library_stats(self.connection, self.fts5, self.library)
        self.assertEqual(stats["counts"]["papers"], 0)
        self.assertEqual(list((self.library / "objects").rglob("*")), [])

    def test_targeted_ingest_rejects_paper_without_complete_digest(self):
        manifest = sample_manifest(self.source)
        targeted = sample_digest()
        targeted["reading"].update(
            {
                "status": "targeted",
                "unread_sections": ["Remaining article sections"],
            }
        )
        targeted = literature_db.validate_digest(targeted)
        literature_db.validate_ingest_manifest(manifest, targeted)
        stored = literature_db.store_objects(self.library, manifest)
        aliases = literature_db.aliases_from_manifest(manifest)
        self.connection.execute("BEGIN IMMEDIATE")
        paper_id = literature_db.upsert_paper(self.connection, manifest, aliases)
        version_id, _created = literature_db.upsert_version(
            self.connection, paper_id, manifest, stored
        )
        literature_db.insert_digest(self.connection, version_id, targeted)
        self.connection.commit()

        lookup = literature_db.lookup_one(
            self.connection,
            "2023ApJ...955..142Z",
            topics=["event rate"],
            artifact_hash=None,
            include_digest=False,
        )
        self.assertEqual(lookup["reuse_status"], "needs_reading")
        self.assertEqual(lookup["open_gate_action"], "complete_ingest")
        self.assertTrue(lookup["complete_ingest_required"])

        with self.assertRaisesRegex(
            literature_db.LiteratureError, "exact article version"
        ):
            self.ingest(manifest=manifest, digest=targeted, merge=True)

    def test_ingest_accepts_narrow_complete_digest_with_full_coverage(self):
        digest = sample_digest(facets=[sample_digest()["facets"][0]])
        digest["facets"][0]["findings"] = digest["facets"][0]["findings"][:1]
        digest["overview"]["questions"] = digest["overview"]["questions"][:1]
        digest["global_limitations"] = []

        result = self.ingest(digest=digest)

        self.assertEqual(result["status"], "ingested")
        stats = literature_db.library_stats(self.connection, self.fts5, self.library)
        self.assertEqual(stats["counts"]["papers"], 1)

    def test_missing_title_is_rejected_before_object_copy(self):
        manifest = sample_manifest(self.source)
        manifest["title"] = ""
        with self.assertRaisesRegex(literature_db.LiteratureError, "manifest.title"):
            self.ingest(manifest=manifest)
        self.assertEqual(list((self.library / "objects").rglob("*")), [])

    def test_existing_arxiv_record_can_receive_ads_metadata(self):
        initial = sample_manifest(self.source)
        initial.update(
            {
                "input": "arXiv:2304.14665",
                "input_type": "arxiv",
                "normalized_identifier": "2304.14665",
                "bibcode": None,
                "author": [],
                "abstract": None,
                "year": None,
                "pub": None,
            }
        )
        result = self.ingest(manifest=initial)
        stored_before = {
            path.relative_to(self.library)
            for path in (self.library / "objects").rglob("*")
        }
        enriched_manifest = sample_manifest(self.source)
        enriched_manifest["doi"] = ["10.5555/new-metadata-record"]
        enriched = literature_db.enrich_paper_metadata(
            self.connection, self.fts5, enriched_manifest
        )
        stored_after = {
            path.relative_to(self.library)
            for path in (self.library / "objects").rglob("*")
        }
        self.assertEqual(enriched["paper_id"], result["paper_id"])
        self.assertEqual(enriched["bibcode"], "2023ApJ...955..142Z")
        self.assertEqual(enriched["authors"], 2)
        self.assertTrue(enriched["abstract"])
        self.assertEqual(stored_after, stored_before)
        shown = literature_db.show_paper(
            self.connection,
            "2023ApJ...955..142Z",
            include_fulltext=False,
        )
        self.assertIn("10.3847/1538-4357/aced0b", shown["paper"]["metadata"]["doi"])
        self.assertIn("10.5555/new-metadata-record", shown["paper"]["metadata"]["doi"])
        preserved = literature_db.enrich_paper_metadata(
            self.connection, self.fts5, initial
        )
        self.assertEqual(preserved["bibcode"], "2023ApJ...955..142Z")
        self.assertEqual(preserved["authors"], 2)
        self.assertTrue(preserved["abstract"])
        shown = literature_db.show_paper(
            self.connection,
            "2023ApJ...955..142Z",
            include_fulltext=False,
        )
        self.assertIn("10.5555/new-metadata-record", shown["paper"]["metadata"]["doi"])

    def test_enrich_refreshes_current_metadata_and_old_ingest_preserves_it(self):
        original = sample_manifest(self.source)
        self.ingest(manifest=original)
        conflict_root = self.root / "conflicting-metadata"
        conflict_root.mkdir()
        incoming = sample_manifest(conflict_root)
        incoming.update(
            {
                "title": "Conflicting replacement title",
                "author": ["Replacement, A."],
                "abstract": "Conflicting replacement abstract.",
                "year": "2025",
                "pub": "Replacement Journal",
                "doctype": "replacement",
                "doi": ["10.5555/new-metadata-record"],
            }
        )

        literature_db.enrich_paper_metadata(self.connection, self.fts5, incoming)
        shown = literature_db.show_paper(
            self.connection,
            "2023ApJ...955..142Z",
            include_fulltext=False,
        )

        self.assertEqual(shown["paper"]["title"], incoming["title"])
        self.assertEqual(shown["paper"]["authors"], incoming["author"])
        self.assertEqual(shown["paper"]["abstract"], incoming["abstract"])
        self.assertEqual(shown["paper"]["year"], int(incoming["year"]))
        self.assertEqual(shown["paper"]["pub"], incoming["pub"])
        self.assertEqual(shown["paper"]["doctype"], incoming["doctype"])
        self.assertIn("10.5555/new-metadata-record", shown["paper"]["metadata"]["doi"])
        self.ingest(manifest=original)
        reused = literature_db.show_paper(
            self.connection, "2023ApJ...955..142Z", include_fulltext=False
        )
        self.assertEqual(reused["paper"]["title"], incoming["title"])
        self.assertEqual(reused["paper"]["abstract"], incoming["abstract"])

    def test_new_article_rejects_schema1_digest_before_object_copy(self):
        digest = sample_digest()
        digest["schema_version"] = 1
        with self.assertRaisesRegex(
            literature_db.LiteratureError, "schema_version must be 4"
        ):
            self.ingest(digest=digest)
        self.assertEqual(list((self.library / "objects").rglob("*")), [])

    def test_long_narrow_article_uses_structural_coverage(self):
        manifest = sample_manifest(
            self.source,
            text_body="word " * 12000,
        )
        digest = sample_digest(facets=[sample_digest()["facets"][0]])
        digest["facets"][0]["findings"] = digest["facets"][0]["findings"][:1]
        digest["overview"]["questions"] = digest["overview"]["questions"][:1]
        digest["global_limitations"] = []

        result = self.ingest(manifest=manifest, digest=digest)

        self.assertEqual(result["status"], "ingested")

    def test_fresh_arxiv_record_without_ads_bibcode_is_informational(self):
        manifest = sample_manifest(self.source)
        manifest.update(
            {
                "input": "arXiv:2608.31161",
                "input_type": "arxiv",
                "normalized_identifier": "2608.31161",
                "bibcode": None,
                "doi": [],
                "arxiv_ids": ["2608.31161"],
            }
        )
        self.ingest(manifest=manifest)
        audit = literature_db.audit_library(
            self.connection,
            self.fts5,
            self.library,
            verify_hashes=False,
        )
        warning_kinds = {item["kind"] for item in audit["warnings"]}
        self.assertNotIn("incomplete_metadata", warning_kinds)
        self.assertEqual(
            audit["information"]["arxiv_records_awaiting_ads_bibcode"],
            ["arxiv:2608.31161"],
        )

    def test_record_text_order_is_deterministic(self):
        first = {"z": "last", "a": "first", "nested": {"b": "two", "a": "one"}}
        second = {"nested": {"a": "one", "b": "two"}, "a": "first", "z": "last"}
        self.assertEqual(
            literature_db.join_record_text([first]),
            literature_db.join_record_text([second]),
        )

    def test_backup_is_consistent_and_audit_reports_quality(self):
        result = self.ingest()
        literature_db.library_catalog.annotate_paper(
            self.connection, result["paper_id"], collections=["Radio astronomy"]
        )
        self.connection.commit()
        destination = self.root / "backup"
        result = literature_db.create_library_backup(
            self.connection, self.fts5, self.library, str(destination)
        )
        self.assertEqual(result["status"], "created")
        self.assertTrue((destination / "literature.sqlite3").is_file())
        self.assertTrue((destination / "backup.json").is_file())
        backup_manifest = json.loads(
            (destination / "backup.json").read_text(encoding="utf-8")
        )
        self.assertEqual(backup_manifest["backup_schema_version"], 1)
        self.assertEqual(
            backup_manifest["database_schema_version"],
            literature_db.DATABASE_SCHEMA_VERSION,
        )
        backup_connection = sqlite3.connect(destination / "literature.sqlite3")
        try:
            self.assertEqual(
                backup_connection.execute("PRAGMA integrity_check").fetchone()[0],
                "ok",
            )
            self.assertEqual(
                backup_connection.execute("SELECT COUNT(*) FROM papers").fetchone()[0],
                1,
            )
        finally:
            backup_connection.close()
        audit = literature_db.audit_library(
            self.connection,
            self.fts5,
            self.library,
            verify_hashes=True,
        )
        self.assertEqual(audit["errors"], [])
        self.assertEqual(audit["warnings"], [])

    def test_audit_requires_text_path_for_fulltext_versions(self):
        self.ingest()
        self.connection.execute("UPDATE versions SET text_path = NULL")
        self.connection.commit()
        audit = literature_db.audit_library(
            self.connection,
            self.fts5,
            self.library,
            verify_hashes=False,
        )
        integrity = next(
            item for item in audit["errors"] if item["kind"] == "object_integrity"
        )
        self.assertIn(
            "missing_text_path",
            {item["kind"] for item in integrity["items"]},
        )

    def test_invalid_digest_does_not_make_its_objects_look_orphaned(self):
        result = self.ingest()
        row = self.connection.execute(
            "SELECT digest_json FROM digests WHERE id = ?", (result["digest_id"],)
        ).fetchone()
        digest = json.loads(row["digest_json"])
        digest["reading"]["unread_sections"] = ["Appendix A"]
        self.connection.execute(
            "UPDATE digests SET digest_json = ? WHERE id = ?",
            (literature_db.json_text(digest), result["digest_id"]),
        )
        self.connection.commit()

        audit = literature_db.audit_library(
            self.connection, self.fts5, self.library, verify_hashes=False
        )

        self.assertIn(
            "invalid_digests", {item["kind"] for item in audit["errors"]}
        )
        self.assertNotIn(
            "orphan_object_directories",
            {item["kind"] for item in audit["warnings"]},
        )

    def test_topic_coverage_controls_reuse(self):
        self.ingest()
        covered = literature_db.lookup_one(
            self.connection,
            "2023ApJ...955..142Z",
            topics=["event rate", "圆偏振"],
            artifact_hash=None,
            include_digest=True,
        )
        self.assertEqual(covered["reuse_status"], "reusable")
        self.assertEqual(len(covered["matched_topics"]), 2)
        self.assertIn("digest", covered)

    def test_section_summaries_cover_lookup_topics(self):
        self.ingest()

        def lookup(topic):
            return literature_db.lookup_one(
                self.connection,
                "2023ApJ...955..142Z",
                topics=[topic],
                artifact_hash=None,
                include_digest=False,
            )

        self.assertEqual(lookup("spectral bandwidths")["reuse_status"], "reusable")
        # Words spread over the summaries of different sections cover no topic.
        self.assertEqual(lookup("observing environment")["reuse_status"], "targeted_reading")

    def test_audit_rejects_schema1_digest(self):
        result = self.ingest()
        row = self.connection.execute(
            "SELECT digest_json FROM digests WHERE id = ?", (result["digest_id"],)
        ).fetchone()
        digest = json.loads(row["digest_json"])
        digest["schema_version"] = 1
        self.connection.execute(
            "UPDATE digests SET digest_json = ? WHERE id = ?",
            (literature_db.json_text(digest), result["digest_id"]),
        )
        self.connection.commit()

        audit = literature_db.audit_library(
            self.connection, self.fts5, self.library, verify_hashes=False
        )
        self.assertIn(
            "invalid_digests", {item["kind"] for item in audit["errors"]}
        )
        self.assertFalse(literature_db.topic_match(sample_digest()["facets"][0], ""))

    def test_audit_rejects_incomplete_stored_reading(self):
        result = self.ingest()
        row = self.connection.execute(
            "SELECT digest_json FROM digests WHERE id = ?", (result["digest_id"],)
        ).fetchone()
        digest = json.loads(row["digest_json"])
        digest["reading"].update(
            {"status": "targeted", "unread_sections": ["Remaining sections"]}
        )
        digest = literature_db.validate_digest(digest)
        self.connection.execute(
            "UPDATE digests SET reading_status = 'targeted', digest_json = ? WHERE id = ?",
            (literature_db.json_text(digest), result["digest_id"]),
        )
        self.connection.commit()

        audit = literature_db.audit_library(
            self.connection, self.fts5, self.library, verify_hashes=False
        )

        self.assertIn(
            "incomplete_reading_digests",
            {item["kind"] for item in audit["errors"]},
        )

    def test_search_covers_summary_metadata_and_fulltext(self):
        self.ingest()
        summary = literature_db.search_library(
            self.connection,
            self.fts5,
            "circular polarization",
            scope="summary",
            mode="terms",
            topics=[],
            year_from=None,
            year_to=None,
            limit=10,
        )
        self.assertEqual(summary["count"], 1)
        self.assertEqual(
            summary["results"][0]["matched_facets"][0]["key"],
            "circular-polarization",
        )
        self.assertEqual(
            summary["results"][0]["matched_facets"][0]["findings"][0]["kind"],
            "measurement",
        )

        metadata = literature_db.search_library(
            self.connection,
            self.fts5,
            "FAST 20220912A",
            scope="metadata",
            mode="terms",
            topics=[],
            year_from=2023,
            year_to=2023,
            limit=10,
        )
        self.assertEqual(metadata["count"], 1)

        article = literature_db.search_library(
            self.connection,
            self.fts5,
            "micropulse avalanche",
            scope="fulltext",
            mode="terms",
            topics=[],
            year_from=None,
            year_to=None,
            limit=10,
        )
        self.assertEqual(article["count"], 1)

        chinese = literature_db.search_library(
            self.connection,
            self.fts5,
            "圆偏振 属性",
            scope="summary",
            mode="terms",
            topics=[],
            year_from=None,
            year_to=None,
            limit=10,
        )
        self.assertEqual(chinese["count"], 1)
        self.assertEqual(chinese["search_engine"], "substring")

        cross_facet = literature_db.search_library(
            self.connection,
            self.fts5,
            "event reversal",
            scope="summary",
            mode="terms",
            topics=[],
            year_from=None,
            year_to=None,
            limit=10,
        )
        self.assertEqual(cross_facet["count"], 1)
        matched_keys = {
            facet["key"] for facet in cross_facet["results"][0]["matched_facets"]
        }
        self.assertEqual(
            matched_keys,
            {"activity-event-rate", "circular-polarization"},
        )

    def test_topic_filter_is_independent_of_free_text_query(self):
        self.ingest()
        result = literature_db.search_library(
            self.connection,
            self.fts5,
            "FAST",
            scope="all",
            mode="terms",
            topics=["Stokes V"],
            year_from=None,
            year_to=None,
            limit=10,
        )
        self.assertEqual(result["count"], 1)

        absent = literature_db.search_library(
            self.connection,
            self.fts5,
            "FAST",
            scope="all",
            mode="terms",
            topics=["gravitational lensing"],
            year_from=None,
            year_to=None,
            limit=10,
        )
        self.assertEqual(absent["count"], 0)

    def test_topic_filter_scans_past_early_nonmatching_candidates(self):
        for index in range(6):
            manifest = sample_manifest(
                self.source,
                body=f"<html>commonterm paper {index}</html>".encode(),
                text_body=f"commonterm scientific content for paper {index}",
            )
            bibcode = f"2026TEST{index:011d}A"
            manifest.update(
                {
                    "input": bibcode,
                    "normalized_identifier": bibcode,
                    "bibcode": bibcode,
                    "title": f"Commonterm paper {index}",
                    "doi": [f"10.5555/commonterm.{index}"],
                    "arxiv_ids": [],
                }
            )
            digest = sample_digest()
            if index == 5:
                digest["facets"][0]["aliases"].append("late-topic")
            self.ingest(manifest=manifest, digest=digest)

        result = literature_db.search_library(
            self.connection,
            False,
            "commonterm",
            scope="all",
            mode="terms",
            topics=["late-topic"],
            year_from=None,
            year_to=None,
            limit=1,
        )

        self.assertEqual(result["count"], 1)
        self.assertEqual(result["results"][0]["title"], "Commonterm paper 5")

    def test_empty_search_query_is_rejected(self):
        self.ingest()
        with self.assertRaisesRegex(literature_db.LiteratureError, "cannot be empty"):
            literature_db.search_library(
                self.connection,
                self.fts5,
                "   ",
                scope="all",
                mode="terms",
                topics=[],
                year_from=None,
                year_to=None,
                limit=10,
            )

    def test_list_uses_the_preferred_article_version(self):
        preprint_manifest = sample_manifest(self.source, body=b"preprint shell")
        preprint_manifest["selected"]["candidate"]["version"] = "preprint"
        self.ingest(manifest=preprint_manifest)

        published_root = self.root / "published"
        published_root.mkdir()
        published_manifest = sample_manifest(
            published_root,
            body=b"published shell",
            text_body="The published article contains revised full text.",
        )
        self.ingest(manifest=published_manifest)

        listed = literature_db.list_library(
            self.connection,
            topics=[],
            year_from=None,
            year_to=None,
            limit=10,
        )
        self.assertEqual(listed["count"], 1)
        self.assertEqual(listed["results"][0]["version_kind"], "published")

    def test_parameters_flatten_values_with_locators_and_citekeys(self):
        digest = sample_digest()
        digest["facets"][1]["findings"][1]["values"][0].update(
            symbol="RM", status="fitted", dataset="FAST 2022 campaign"
        )
        self.ingest(digest=digest)

        everything = literature_db.evidence_table(self.connection, "values")
        self.assertEqual(everything["count"], 3)
        self.assertEqual(everything["papers_scanned"], 1)

        rm = literature_db.evidence_table(self.connection, "values", query="RM")
        self.assertEqual(rm["count"], 1)
        row = rm["results"][0]
        self.assertEqual(row["value"], -0.08)
        self.assertEqual(row["unit"], "rad m^-2")
        self.assertEqual(row["locator"], {"section": "3.3", "figure": "1"})
        self.assertEqual(row["citekey"], "2023ApJ...955..142Z")
        self.assertEqual(row["reading_status"], "full")
        self.assertEqual(row["facet"], "circular-polarization")

        measured = literature_db.evidence_table(
            self.connection, "values", statuses=["fitted"]
        )
        self.assertEqual(measured["count"], 1)
        self.assertEqual(
            literature_db.evidence_table(
                self.connection, "values", entity="FRB 20220912A"
            )["count"],
            3,
        )
        self.assertEqual(
            literature_db.evidence_table(self.connection, "values", entity="Crab")["count"],
            0,
        )
        limited = literature_db.evidence_table(self.connection, "values", limit=2)
        self.assertEqual(limited["count"], 2)
        self.assertTrue(limited["truncated"])

        rate = literature_db.evidence_table(self.connection, "values", query="rate")
        self.assertEqual(
            [(row["name"], row["match"]) for row in rate["results"]],
            [("maximum rate", "value"), ("burst count", "context")],
        )
        self.assertEqual(
            literature_db.evidence_table(self.connection, "values", query="ate")["count"], 0
        )
        self.assertEqual(
            literature_db.evidence_table(self.connection, "values", query="事件率")["count"], 2
        )

        csv_text = literature_db.evidence_csv(rm)
        header, first = csv_text.splitlines()[:2]
        self.assertIn("citekey", header)
        self.assertIn("section 3.3; figure 1", first)

    def test_findings_are_citable_rows_with_attribution(self):
        digest = sample_digest()
        rate_finding = digest["facets"][0]["findings"][0]
        rate_finding["cited_from"] = "Zhou et al. 2022"
        rate_finding["values"][1]["status"] = "fitted"
        digest["facets"][1]["findings"][1]["values"][0]["cited_from"] = (
            "2021ApJ...908L..10H"
        )
        digest["facets"][1]["findings"].append(
            {
                "statement": "The sign reversals favor a magnetospheric origin.",
                "kind": "interpretation",
                "confidence": "medium",
                "locator": {"section": "4.2"},
                "values": [],
                "keywords": ["radiation mechanism"],
            }
        )
        self.ingest(digest=digest)

        everything = literature_db.evidence_table(self.connection, "findings")
        self.assertEqual(everything["count"], 5)
        self.assertEqual(everything["unit"], "findings")

        inference = literature_db.evidence_table(
            self.connection, "findings", kinds=["interpretation"]
        )
        self.assertEqual(inference["count"], 1)
        row = inference["results"][0]
        self.assertEqual(row["locator"], {"section": "4.2"})
        self.assertEqual(row["citekey"], "2023ApJ...955..142Z")
        self.assertEqual(row["values"], [])
        self.assertIsNone(row["cited_from"])

        origin = literature_db.evidence_table(
            self.connection, "findings", query="magnetospheric"
        )
        self.assertEqual([row["match"] for row in origin["results"]], ["finding"])
        fitted = literature_db.evidence_table(
            self.connection, "findings", statuses=["fitted"]
        )
        self.assertEqual(fitted["count"], 1)
        self.assertEqual(fitted["results"][0]["cited_from"], "Zhou et al. 2022")

        values = literature_db.evidence_table(self.connection, "values")
        attribution = {row["name"]: row["cited_from"] for row in values["results"]}
        self.assertEqual(
            attribution,
            {
                "burst count": "Zhou et al. 2022",
                "maximum rate": "Zhou et al. 2022",
                "mean RM": "2021ApJ...908L..10H",
            },
        )
        self.assertEqual(
            literature_db.evidence_table(
                self.connection, "values", kinds=["interpretation"]
            )["count"],
            0,
        )

        csv_text = literature_db.evidence_csv(fitted)
        header, first = csv_text.splitlines()[:2]
        self.assertTrue(
            header.startswith("bibcode,citekey,year,title,facet,finding_id,kind")
        )
        self.assertIn("maximum rate = 390 hr^-1 [fitted]", first)
        self.assertIn("Zhou et al. 2022", first)

    def test_schema_four_digest_ingests_and_counts(self):
        result = self.ingest(digest=current_digest())
        self.assertEqual(result["status"], "ingested")
        stats = literature_db.library_stats(self.connection, self.fts5, self.library)
        self.assertEqual(stats["digest_schema_version"], 4)
        self.assertEqual(stats["counts"]["complete_digests"], 1)
        limitation = literature_db.evidence_table(
            self.connection, "findings", kinds=["limitation"]
        )
        self.assertEqual(limitation["results"][0]["statement"], "The measured rate depends on observing cadence.")

    def test_parameters_report_unknown_and_unread_papers(self):
        self.ingest()
        table = literature_db.evidence_table(
            self.connection, "values", identifiers=["2023ApJ...955..142Z", "2099ApJ...1..1X"]
        )
        self.assertEqual(table["missing"], ["2099ApJ...1..1X"])
        self.assertEqual(table["count"], 3)

    def test_duplicate_ingest_is_unchanged(self):
        manifest = sample_manifest(self.source)
        first = self.ingest(manifest=manifest)
        second = self.ingest(manifest=manifest)
        self.assertTrue(first["digest_created"])
        self.assertFalse(second["digest_created"])
        stats = literature_db.library_stats(self.connection, self.fts5, self.library)
        self.assertEqual(stats["counts"]["papers"], 1)
        self.assertEqual(stats["counts"]["versions"], 1)
        self.assertEqual(stats["counts"]["digests"], 1)

    def test_merge_adds_a_facet_in_place(self):
        manifest = sample_manifest(self.source)
        original = self.ingest(manifest=manifest)
        new_facet = {
            "key": "waiting-time",
            "label": "等待时间分布",
            "aliases": ["waiting time"],
            "summary": "The distribution is bimodal.",
            "keywords": ["lognormal"],
            "findings": [
                {
                    "statement": "The two waiting-time peaks are near 18 s and 51 ms.",
                    "kind": "measurement",
                    "confidence": "high",
                    "locator": {"section": "3.1", "figure": "2"},
                    "values": [
                        {"name": "long peak", "value": 18, "unit": "s"},
                        {"name": "short peak", "value": 51, "unit": "ms"},
                    ],
                    "keywords": ["bimodal"],
                }
            ],
            "methods": ["two-lognormal fit"],
        }
        incoming = sample_digest(facets=[new_facet])
        incoming["reading"].update(
            {
                "status": "targeted",
                "unread_sections": ["Previously covered dimensions"],
            }
        )
        result = self.ingest(manifest=manifest, digest=incoming, merge=True)
        self.assertEqual(result["status"], "updated")
        self.assertEqual(result["digest_id"], original["digest_id"])
        self.assertEqual(len(result["facets"]), 3)
        shown = literature_db.show_paper(
            self.connection,
            "2023ApJ...955..142Z",
            include_fulltext=False,
        )
        self.assertEqual(
            len(shown["versions"][0]["digest"]["digest"]["facets"]), 3
        )

    def test_replace_digest_updates_the_single_digest_in_place(self):
        manifest = sample_manifest(self.source)
        original = self.ingest(manifest=manifest)
        replacement_facet = {
            "key": "waiting-time-distribution",
            "label": "Waiting-time distribution",
            "aliases": ["waiting time"],
            "summary": "The complete analysis identifies two waiting-time regimes.",
            "keywords": ["bimodal waiting time"],
            "findings": [
                {
                    "statement": "The two fitted peaks occur near 18 s and 51 ms.",
                    "kind": "measurement",
                    "confidence": "high",
                    "locator": {"section": "3.2", "figure": "2"},
                    "values": [
                        {"name": "long-timescale peak", "value": 18, "unit": "s"},
                        {"name": "short-timescale peak", "value": 51, "unit": "ms"},
                    ],
                    "keywords": ["waiting-time peaks"],
                }
            ],
            "methods": ["two-lognormal fit"],
        }
        replacement_facet["findings"].append(
            {
                "statement": "Intervals longer than one second are near Poissonian.",
                "kind": "interpretation",
                "confidence": "medium",
                "locator": {"section": "3.2"},
                "values": [],
                "keywords": ["Poisson process"],
            }
        )
        supporting = sample_digest()["facets"][1]
        replacement = sample_digest(facets=[replacement_facet, supporting])

        result = self.ingest(
            manifest=manifest,
            digest=replacement,
            replace_digest=True,
        )

        self.assertEqual(result["status"], "updated")
        self.assertEqual(result["digest_id"], original["digest_id"])
        self.assertEqual(
            result["facets"],
            ["waiting-time-distribution", "circular-polarization"],
        )
        shown = literature_db.show_paper(
            self.connection,
            "2023ApJ...955..142Z",
            include_fulltext=False,
        )
        stored = shown["versions"][0]["digest"]
        self.assertIsNotNone(stored)
        self.assertEqual(
            [facet["key"] for facet in stored["digest"]["facets"]],
            ["waiting-time-distribution", "circular-polarization"],
        )
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM digests").fetchone()[0],
            1,
        )

    def test_replace_digest_requires_existing_digest(self):
        with self.assertRaisesRegex(
            literature_db.LiteratureError, "requires an existing paper"
        ):
            self.ingest(replace_digest=True)

    def test_replace_digest_rejects_new_version_before_copy(self):
        self.ingest()
        before = {
            path.relative_to(self.library)
            for path in (self.library / "objects").rglob("*")
        }
        changed_manifest = sample_manifest(
            self.source,
            body=b"<html>article two</html>",
            text_body="A scientifically distinct second article version.",
        )
        with self.assertRaisesRegex(
            literature_db.LiteratureError, "this exact article version"
        ):
            self.ingest(
                manifest=changed_manifest,
                replace_digest=True,
            )
        after = {
            path.relative_to(self.library)
            for path in (self.library / "objects").rglob("*")
        }
        self.assertEqual(after, before)

    def test_replace_digest_rejects_targeted_replacement(self):
        manifest = sample_manifest(self.source)
        self.ingest(manifest=manifest)
        targeted = sample_digest()
        targeted["reading"].update(
            {
                "status": "targeted",
                "unread_sections": ["Remaining article sections"],
            }
        )
        with self.assertRaisesRegex(
            literature_db.LiteratureError, "requires a complete full"
        ):
            self.ingest(
                manifest=manifest,
                digest=targeted,
                replace_digest=True,
            )

    def test_changed_digest_requires_merge_to_prevent_facet_loss(self):
        manifest = sample_manifest(self.source)
        self.ingest(manifest=manifest)
        reduced = sample_digest(facets=[sample_digest()["facets"][0]])
        reduced["reading"].update(
            {
                "status": "targeted",
                "unread_sections": ["Polarization dimensions"],
            }
        )
        with self.assertRaises(literature_db.LiteratureError):
            self.ingest(manifest=manifest, digest=reduced, merge=False)
        stats = literature_db.library_stats(self.connection, self.fts5, self.library)
        self.assertEqual(stats["counts"]["digests"], 1)

    def test_digest_conflict_is_rejected_before_a_new_wrapper_is_copied(self):
        self.ingest(manifest=sample_manifest(self.source, body=b"<html>first</html>"))
        refreshed_root = self.root / "refreshed-wrapper"
        refreshed_root.mkdir()
        refreshed = sample_manifest(refreshed_root, body=b"<html>second</html>")
        reduced = sample_digest(facets=[sample_digest()["facets"][0]])
        reduced["reading"].update(
            {"status": "targeted", "unread_sections": ["Polarization dimensions"]}
        )
        artifact_hash = refreshed["selected"]["sha256"]
        object_dir = self.library / "objects" / artifact_hash[:2] / artifact_hash

        with self.assertRaisesRegex(
            literature_db.LiteratureError, "already has a different digest"
        ):
            self.ingest(manifest=refreshed, digest=reduced, merge=False)

        self.assertFalse(object_dir.exists())

    def test_new_article_content_creates_a_new_version(self):
        first_manifest = sample_manifest(self.source, body=b"<html>version one</html>")
        self.ingest(manifest=first_manifest)
        second_root = self.root / "second"
        second_root.mkdir()
        second_manifest = sample_manifest(
            second_root,
            body=b"<html>version two</html>",
            text_body="The scientific article now contains a revised result.",
        )
        second = self.ingest(manifest=second_manifest)
        self.assertTrue(second["version_created"])
        stats = literature_db.library_stats(self.connection, self.fts5, self.library)
        self.assertEqual(stats["counts"]["versions"], 2)
        changed = literature_db.lookup_one(
            self.connection,
            "2023ApJ...955..142Z",
            topics=[],
            artifact_hash="0" * 64,
            include_digest=False,
        )
        self.assertEqual(changed["reuse_status"], "version_changed")
        self.assertEqual(changed["open_gate_action"], "complete_ingest")
        self.assertTrue(changed["complete_ingest_required"])

    def test_changed_article_rejects_targeted_first_digest(self):
        first_manifest = sample_manifest(self.source, body=b"<html>version one</html>")
        self.ingest(manifest=first_manifest)
        second_root = self.root / "targeted-second-version"
        second_root.mkdir()
        second_manifest = sample_manifest(
            second_root,
            body=b"<html>version two</html>",
            text_body="The scientific article now contains a revised result.",
        )
        targeted = sample_digest()
        targeted["reading"].update(
            {
                "status": "targeted",
                "unread_sections": ["Sections outside the requested facet"],
            }
        )
        artifact_hash = second_manifest["selected"]["sha256"]
        object_dir = self.library / "objects" / artifact_hash[:2] / artifact_hash

        with self.assertRaisesRegex(
            literature_db.LiteratureError, "exact article version"
        ):
            self.ingest(manifest=second_manifest, digest=targeted)

        stats = literature_db.library_stats(self.connection, self.fts5, self.library)
        self.assertEqual(stats["counts"]["versions"], 1)
        self.assertFalse(object_dir.exists())

    def test_changed_html_wrapper_with_same_text_reuses_the_version(self):
        first_manifest = sample_manifest(self.source, body=b"<html>shell one</html>")
        first = self.ingest(manifest=first_manifest)
        second_root = self.root / "wrapper-refresh"
        second_root.mkdir()
        second_manifest = sample_manifest(
            second_root,
            body=b"<html data-request-id='new'>shell two</html>",
        )
        second = self.ingest(manifest=second_manifest)
        self.assertFalse(second["version_created"])
        self.assertEqual(second["version_id"], first["version_id"])
        self.assertEqual(second["content_sha256"], first["content_sha256"])
        self.assertNotEqual(second["artifact_sha256"], first["artifact_sha256"])
        stats = literature_db.library_stats(self.connection, self.fts5, self.library)
        self.assertEqual(stats["counts"]["versions"], 1)
        self.assertEqual(stats["counts"]["artifacts"], 2)
        reused = literature_db.lookup_one(
            self.connection,
            "2023ApJ...955..142Z",
            topics=[],
            artifact_hash=second["content_sha256"],
            include_digest=False,
        )
        self.assertEqual(reused["reuse_status"], "reusable")
        self.assertEqual(reused["open_gate_action"], "reuse_complete_record")
        self.assertFalse(reused["complete_ingest_required"])
        shown = literature_db.show_paper(
            self.connection,
            "2023ApJ...955..142Z",
            include_fulltext=False,
        )
        self.assertEqual(len(shown["versions"][0]["artifacts"]), 2)

    def test_hash_mismatch_is_rejected(self):
        manifest = sample_manifest(self.source)
        manifest["selected"]["sha256"] = "0" * 64
        with self.assertRaises(literature_db.LiteratureError):
            self.ingest(manifest=manifest)

    def test_reindex_restores_search_documents(self):
        self.ingest()
        self.connection.execute("DELETE FROM search_documents")
        self.connection.commit()
        rebuilt = literature_db.rebuild_index(self.connection, self.fts5)
        self.assertEqual(rebuilt["documents"], 1)
        result = literature_db.search_library(
            self.connection,
            self.fts5,
            "micropulse",
            scope="fulltext",
            mode="terms",
            topics=[],
            year_from=None,
            year_to=None,
            limit=10,
        )
        self.assertEqual(result["count"], 1)


ARTICLE_TEXT = """FAST Observations of FRB 20220912A
Y. K. Zhang and D. Li

Abstract
We report FAST observations of the repeating FRB 20220912A.

1 Introduction
Repeating fast radio bursts probe magnetized environments.

3.1 Burst detections
Across seventeen sessions we detected 1076 bursts in total, and the peak
rate reached 390 bursts per hour.

The burst rate varied strongly be-
tween sessions, as Table 1 lists.

3.3 Polarization
In many bursts the circular polarization reverses sign across time or frequency.

The rotation measure stays close to zero for the high-quality sample (Figure 1).

4 Discussion
The measured rate depends on the observing cadence, which limits comparisons.

References
Hilmarsson, G. et al. 2021, ApJL, 908, L10
"""


def minimal_digest() -> dict:
    """The smallest complete schema 4 digest: only required layers."""
    return {
        "schema_version": literature_db.DIGEST_SCHEMA_VERSION,
        "language": "en",
        "overview": {
            "tldr": "FAST detected 1076 bursts from FRB 20220912A.",
            "summary": "A FAST campaign measured the burst count of FRB 20220912A.",
            "questions": ["How active is FRB 20220912A?"],
            "study_types": ["observational"],
        },
        "facets": [
            {
                "key": "activity",
                "label": "Activity",
                "summary": "The source was highly active.",
                "findings": [
                    {
                        "statement": "The campaign detected 1076 bursts.",
                        "kind": "measurement",
                        "confidence": "high",
                        "locator": {"section": "3.1"},
                        "quote": "we detected 1076 bursts in total",
                        "values": [
                            {"name": "burst count", "value": 1076, "status": "measured"}
                        ],
                    }
                ],
            }
        ],
        "reading": {"status": "full", "sections": ["3.1 Burst detections"]},
    }


class CompactDigestTests(unittest.TestCase):
    def test_minimal_digest_defaults_optional_layers_and_is_stable(self):
        validated = literature_db.validate_digest(minimal_digest())
        for field in literature_db.DIGEST_LIST_FIELDS:
            self.assertEqual(validated[field], [])
        self.assertEqual(
            validated["reading"]["sections"], [{"heading": "3.1 Burst detections"}]
        )
        self.assertNotIn("significance", validated["overview"])
        again = literature_db.validate_digest(json.loads(json.dumps(validated)))
        self.assertEqual(
            literature_db.stable_digest(again), literature_db.stable_digest(validated)
        )
        self.assertEqual(literature_db.digest_warnings(validated), [])

    def test_sections_accept_headings_and_gists(self):
        digest = minimal_digest()
        digest["reading"]["sections"] = [
            "2 Data",
            {"heading": "2  data", "gist": "FAST observations."},
            {"heading": "3.1 Burst detections", "gist": " "},
        ]
        sections = literature_db.validate_digest(digest)["reading"]["sections"]
        self.assertEqual(
            sections,
            [
                {"heading": "2 Data", "gist": "FAST observations."},
                {"heading": "3.1 Burst detections"},
            ],
        )
        for bad, message in (
            ([{"heading": "Full paper"}], "real article section"),
            ([{"heading": "2", "notes": "x"}], "unsupported fields: notes"),
            ([], "must list the sections"),
        ):
            with self.subTest(message=message):
                digest["reading"]["sections"] = bad
                with self.assertRaisesRegex(literature_db.LiteratureError, message):
                    literature_db.validate_digest(digest)

    def test_targeted_digest_needs_only_its_new_facets(self):
        digest = minimal_digest()
        digest.pop("overview")
        digest["reading"] = {
            "status": "targeted",
            "sections": ["4 Discussion"],
            "unread_sections": ["Earlier sections"],
        }
        validated = literature_db.validate_digest(digest)
        self.assertEqual(validated["overview"], {"questions": []})
        digest["reading"]["status"] = "full"
        digest["reading"]["unread_sections"] = []
        with self.assertRaisesRegex(literature_db.LiteratureError, "overview"):
            literature_db.validate_digest(digest)

    def test_warnings_flag_missing_quotes_and_excess_detail(self):
        digest = minimal_digest()
        finding = digest["facets"][0]["findings"][0]
        finding.pop("quote")
        finding["statement"] = "The campaign detected 1076 bursts. " * 15
        digest["facets"][0]["findings"].extend(
            {
                "statement": f"Result {index} is stated.",
                "kind": "interpretation",
                "confidence": "medium",
                "locator": {"section": "4"},
                "quote": "word " * 80,
            }
            for index in range(40)
        )
        warnings = literature_db.digest_warnings(literature_db.validate_digest(digest))
        messages = [warning["message"] for warning in warnings]
        self.assertTrue(any("shorten or split the statement" in m for m in messages))
        self.assertTrue(any("Shorten the quote" in m for m in messages))
        self.assertTrue(any("merge findings that are always cited" in m for m in messages))
        self.assertTrue(any(m.startswith("Add a short verbatim quote to activity.1 ") for m in messages))
        digest["reading"].update(status="visual", visual_page_ranges=["1-4"])
        visual = literature_db.digest_warnings(literature_db.validate_digest(digest))
        self.assertFalse(any("verbatim quote" in w["message"] for w in visual))

    def test_quotes_match_across_extraction_differences(self):
        text = (
            "The bursts show Faraday rotation measures bordering 9.3 × 104 rad m−2.\n"
            "The ﬁtted spectral in-\ndex is steep.\n"
        )
        skeleton = literature_db.text_skeleton(text)
        for quote in (
            "Faraday rotation measures bordering 9.3 x 10^4 rad m^-2",
            "the fitted spectral index is steep",
        ):
            with self.subTest(quote=quote):
                hit = literature_db.locate_quote(*skeleton, quote)
                self.assertIsNotNone(hit)
                self.assertTrue(hit[2])
        partial = literature_db.locate_quote(
            *skeleton, "Faraday rotation measures bordering an entirely different number"
        )
        self.assertEqual(partial[2], False)
        self.assertIsNone(literature_db.locate_quote(*skeleton, "rad m"))
        self.assertIsNone(literature_db.locate_quote(*skeleton, "a sentence the paper never wrote"))

    def test_quote_anchors_prefer_the_locator_section(self):
        text = "1 Introduction\nThe RM is near zero.\n\n3 Results\nThe RM is near zero.\n"
        sections = literature_db.article_sections(text)
        skeleton = literature_db.text_skeleton(text)
        results = literature_db.match_section(sections, "Sec. 3")
        start, _end, _exact = literature_db.locate_quote(
            *skeleton, "The RM is near zero", within=(results["start"], results["end"])
        )
        self.assertGreaterEqual(start, results["start"])
        digest = minimal_digest()
        digest["facets"][0]["findings"][0].update(
            quote="The RM is near zero", locator={"section": "3"}
        )
        anchors = literature_db.quote_anchors(literature_db.validate_digest(digest), text)
        self.assertEqual(anchors, {"quoted": 1, "located": 1, "unlocated": []})

    def test_section_labels_resolve_numbers_prefixes_and_titles(self):
        sections = literature_db.article_sections(ARTICLE_TEXT)
        self.assertEqual(sections[0]["heading"], "Front matter")
        cases = {
            "3.1": "3.1 Burst detections",
            "Section 3.3": "3.3 Polarization",
            "§4": "4 Discussion",
            "discussion": "4 Discussion",
            "Sect. 1 (Introduction)": "1 Introduction",
            "3.3 Polarization": "3.3 Polarization",
        }
        for label, heading in cases.items():
            with self.subTest(label=label):
                self.assertEqual(
                    literature_db.match_section(sections, label)["heading"], heading
                )
        self.assertEqual(
            literature_db.match_section(sections, "3")["heading"],
            "3.1 Burst detections",
        )
        self.assertIsNone(literature_db.match_section(sections, "7"))
        self.assertIsNone(literature_db.match_section(sections, ""))
        self.assertIsNone(literature_db.match_section(sections, "Table 1"))

    def test_paragraphs_rejoin_inline_math_split_by_extraction(self):
        text = (
            "4.2 Case studies\n\nThe data allow\n\n$N=5$\n\n–20 and dispersion\n\n"
            "$\\sigma_\\psi \\sim 22^\\circ$\n\n. Relaxing this gives fewer microshots.\n\n"
            "A second paragraph starts here.\n"
        )
        blocks = [text[a:b] for a, b in literature_db.paragraph_blocks(text, 0, len(text))]
        self.assertEqual(blocks[0], "4.2 Case studies")
        self.assertTrue(blocks[1].startswith("The data allow"))
        self.assertTrue(blocks[1].endswith("Relaxing this gives fewer microshots."))
        self.assertEqual(blocks[2], "A second paragraph starts here.")
        start = text.index("fewer")
        left, right = literature_db.paragraph_span(text, start, start + 5, 0, len(text), 0)
        self.assertIn("$N=5$", text[left:right])

    def test_compound_stored_locators_resolve_their_section(self):
        sections = literature_db.article_sections(ARTICLE_TEXT)
        cases = {
            "3.1; Table 1": "3.1 Burst detections",
            "Sections 3.3-4": "3.3 Polarization",
            "Main text and 4": "4 Discussion",
            "Table 2, 3.3": "3.3 Polarization",
        }
        for label, heading in cases.items():
            with self.subTest(label=label):
                self.assertEqual(
                    literature_db.match_section(sections, label)["heading"], heading
                )
        roman = literature_db.article_sections(
            "II Observations\nText.\n\nII.1 Arecibo\nMore.\n\nIII Results\nEnd.\n"
        )
        for label, heading in {
            "II.1": "II.1 Arecibo",
            "III–IV; Figure 1": "III Results",
            "Sec. II": "II Observations",
        }.items():
            with self.subTest(label=label):
                self.assertEqual(literature_db.match_section(roman, label)["heading"], heading)

    def test_digest_headings_locate_sections_the_outline_missed(self):
        # PDF text keeps a paragraph on one line, joining a heading to its prose.
        searches = (
            "V. SEARCHES We present the analysis of the coincident data, "
            + "and the false alarm rate bound follows from the background. " * 4
        )
        text = f"I. INTRODUCTION\nIntro text.\n{searches}\nVI. SOURCE DISCUSSION\nEnd.\n"
        digest = minimal_digest()
        digest["reading"]["sections"] = [
            {"heading": "I. Introduction"},
            {"heading": "V. Searches"},
            {"heading": "VI. Source Discussion"},
        ]
        digest["facets"][0]["findings"][0].update(
            quote="the false alarm rate bound follows from the background",
            locator={"section": "V. Searches"},
        )
        without = literature_db.article_sections(text)
        self.assertIsNone(literature_db.match_section(without, "Searches"))
        sections = literature_db.article_sections(text, None, digest)
        self.assertEqual(
            literature_db.match_section(sections, "Searches")["heading"], "V. Searches"
        )
        anchors = literature_db.quote_anchors(literature_db.validate_digest(digest), text)
        self.assertEqual(anchors["located"], 1)


class PassageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.library = self.root / "library"
        self.source = self.root / "source"
        self.source.mkdir()
        self.connection, self.fts5 = literature_db.connect_library(self.library)
        self.manifest = sample_manifest(self.source, text_body=ARTICLE_TEXT)
        self.digest = current_digest()
        self.result = literature_db.ingest_record(
            self.connection,
            self.fts5,
            self.library,
            self.manifest,
            self.digest,
            merge=False,
        )

    def tearDown(self):
        self.connection.close()
        self.temporary.cleanup()

    def passage(self, **kwargs):
        return literature_db.article_passages(
            self.connection, "2023ApJ...955..142Z", **kwargs
        )

    def test_ingest_reports_located_quotes(self):
        self.assertEqual(
            self.result["anchors"], {"quoted": 5, "located": 5, "unlocated": []}
        )
        self.assertEqual(self.result["section_summaries"], {"summarized": 4, "thin": []})
        self.assertEqual(self.result["warnings"], [])

    def test_finding_returns_its_paragraph(self):
        result = self.passage(findings=["activity-event-rate.2"])
        passage = result["passages"][0]
        self.assertEqual(passage["match"], "quote")
        self.assertEqual(passage["section"], "3.1 Burst detections")
        self.assertEqual(passage["text"], "The burst rate varied strongly be-\ntween sessions, as Table 1 lists.")
        self.assertEqual(passage["finding_id"], "activity-event-rate.2")
        self.assertFalse(passage["truncated"])
        self.assertEqual(result["paper"]["citekey"], "2023ApJ...955..142Z")
        wider = self.passage(findings=["activity-event-rate.2"], context=1)
        self.assertIn("1076 bursts in total", wider["passages"][0]["text"])

    def test_finding_without_quote_falls_back_to_its_locator(self):
        digest = json.loads(
            self.connection.execute(
                "SELECT digest_json FROM digests WHERE id = ?", (self.result["digest_id"],)
            ).fetchone()["digest_json"]
        )
        digest["facets"][0]["findings"][1].pop("quote")
        digest["facets"][0]["findings"][1]["locator"] = {"section": "3.1; Table 1"}
        digest["facets"][1]["findings"][0].pop("quote")
        digest["facets"][1]["findings"][0]["locator"] = {"section": "3.3"}
        self.connection.execute(
            "UPDATE digests SET digest_json = ? WHERE id = ?",
            (literature_db.json_text(digest), self.result["digest_id"]),
        )
        result = self.passage(
            findings=["activity-event-rate.2", "circular-polarization.1", "missing.9"]
        )
        table, section = result["passages"]
        self.assertEqual(table["match"], "table")
        self.assertIn("as Table 1 lists", table["text"])
        self.assertEqual(section["match"], "section")
        self.assertTrue(section["text"].startswith("3.3 Polarization"))
        self.assertEqual(result["unresolved"][0]["finding"], "missing.9")

    def test_sections_terms_and_outline_stay_bounded(self):
        result = self.passage(sections=["3.3", "Appendix Z"], terms=["rotation", "measure"])
        section, term = result["passages"]
        self.assertTrue(section["text"].startswith("3.3 Polarization"))
        self.assertNotIn("4 Discussion", section["text"])
        self.assertEqual(term["section"], "3.3 Polarization")
        self.assertEqual(term["match"], "terms")
        self.assertEqual(result["term_matches"], 1)
        self.assertEqual(result["unresolved"][0]["section"], "Appendix Z")
        clipped = self.passage(sections=["3.3"], max_chars=40)["passages"][0]
        self.assertTrue(clipped["truncated"])
        self.assertLessEqual(len(clipped["text"]), 40)
        self.assertEqual(clipped["section_lines"][0], 17)
        outline = self.passage()["outline"]
        headings = [entry["heading"] for entry in outline]
        self.assertEqual(headings[:3], ["Front matter", "Abstract", "1 Introduction"])
        gists = {entry["heading"]: entry.get("gist") for entry in outline}
        self.assertEqual(
            gists["3.1 Burst detections"],
            "Burst detections and the event rate across sessions.",
        )

    def test_evidence_rows_carry_finding_ids_and_quotes(self):
        rows = literature_db.evidence_table(self.connection, "findings")["results"]
        self.assertEqual(rows[0]["finding_id"], "activity-event-rate.1")
        self.assertEqual(rows[0]["quote"], "we detected 1076 bursts in total")
        values = literature_db.evidence_table(self.connection, "values")["results"]
        self.assertEqual(values[0]["finding_id"], "activity-event-rate.1")
        self.assertNotIn("quote", values[0])

    def test_changed_text_is_refused(self):
        Path(self.result["object_paths"]["text"]).write_text("tampered", encoding="utf-8")
        with self.assertRaisesRegex(literature_db.LiteratureError, "missing or has changed"):
            self.passage(sections=["3.1"])

    def test_cli_is_read_only(self):
        self.connection.close()
        self.connection, self.fts5 = literature_db.connect_library_readonly(self.library)
        output = io.StringIO()
        code = literature_db.run(
            [
                "--library-dir",
                str(self.library),
                "passage",
                "2023ApJ...955..142Z",
                "--finding",
                "circular-polarization.2",
            ],
            stdout=output,
        )
        self.assertEqual(code, 0)
        passage = json.loads(output.getvalue())["passages"][0]
        self.assertIn("rotation measure stays close to zero", passage["text"])

    def test_validate_digest_checks_quotes_against_text(self):
        digest = current_digest()
        digest["facets"][1]["findings"][0]["quote"] = "a sentence the paper never wrote"
        digest_path = self.root / "digest.json"
        digest_path.write_text(json.dumps(in_chinese(digest)), encoding="utf-8")
        output = io.StringIO()
        code = literature_db.run(
            [
                "--library-dir",
                str(self.root / "unused"),
                "validate-digest",
                str(digest_path),
                "--text",
                self.manifest["selected"]["text_path"],
            ],
            stdout=output,
        )
        self.assertEqual(code, 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report["anchors"]["unlocated"], ["circular-polarization.1"])
        self.assertTrue(
            any("circular-polarization.1 do not occur" in w["message"] for w in report["warnings"])
        )
        self.assertFalse((self.root / "unused").exists())

    def test_validate_digest_reads_the_text_and_headings_of_a_manifest(self):
        manifest_path = self.root / "manifest.json"
        manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")
        digest_path = self.root / "digest.json"
        digest_path.write_text(json.dumps(in_chinese(current_digest())), encoding="utf-8")
        output = io.StringIO()
        code = literature_db.run(
            ["validate-digest", str(digest_path), "--text", str(manifest_path)],
            stdout=output,
        )
        self.assertEqual(code, 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report["anchors"]["located"], 5)
        self.assertEqual(report["section_summaries"], {"summarized": 4, "thin": []})
        stderr = io.StringIO()
        code = literature_db.run(
            ["validate-digest", str(digest_path), "--text", str(self.root / "none.txt")],
            stdout=io.StringIO(),
            stderr=stderr,
        )
        self.assertEqual(code, 2)
        self.assertIn("does not exist", stderr.getvalue())

    def test_full_reading_must_summarize_every_article_section(self):
        body = " ".join(["The fitted model describes the observed burst energies well."] * 30)
        text = (
            "A Study of Bursts\n\nAbstract\nA short abstract.\n\n"
            f"1 Introduction\n{body}\n\n2 Observations\n{body}\n\n"
            f"3 Results\nA short section.\n\nReferences\n{body}\n"
        )
        digest = minimal_digest()
        digest["reading"]["sections"] = [
            {"heading": "1 Introduction", "gist": "背景。"},
            {"heading": "3 Results", "gist": "结果。"},
        ]
        with self.assertRaisesRegex(
            literature_db.LiteratureError, "each with its gist: 2 Observations[.]$"
        ):
            literature_db.section_coverage(literature_db.validate_digest(digest), text)

        digest["reading"]["sections"].append(
            {"heading": "2 Observations", "gist": "FAST 的 L 波段观测配置与爆发搜索流程。"}
        )
        coverage = literature_db.section_coverage(
            literature_db.validate_digest(digest), text
        )
        self.assertEqual(coverage, {"summarized": 3, "thin": ["1 Introduction"]})
        messages = [
            warning["message"]
            for warning in literature_db.digest_warnings(digest, None, coverage)
        ]
        self.assertTrue(any("1 Introduction" in m and "short" in m for m in messages))
        digest["reading"]["sections"][0]["gist"] = "综述重复暴的活动性与偏振如何约束辐射模型。"
        self.assertEqual(
            literature_db.section_coverage(literature_db.validate_digest(digest), text),
            {"summarized": 3, "thin": []},
        )

        # An HTML outline starts with the title, whose section holds the author list.
        authors = " ".join(["A. Author"] * 100)
        digest["reading"]["sections"] = digest["reading"]["sections"][:1]

        def coverage_of(front, headings, **kwargs):
            page = f"A Study of Bursts\n{authors}\n\n{front}1 Introduction\n{body}\n"
            manifest = {"selected": {"statistics": {"outline": headings}}}
            validated = literature_db.validate_digest(json.loads(json.dumps(digest)))
            return literature_db.section_coverage(
                validated,
                page,
                literature_db.article_sections(page, manifest, validated),
                **kwargs,
            )

        titled = ["A Study of Bursts", "1 Introduction"]
        with self.assertRaisesRegex(literature_db.LiteratureError, "A Study of Bursts"):
            coverage_of("", titled)
        self.assertEqual(coverage_of("", titled, title="A study of bursts")["summarized"], 1)
        with_abstract = ["A Study of Bursts", "Abstract", "1 Introduction"]
        self.assertEqual(
            coverage_of("Abstract\nShort.\n\n", with_abstract)["summarized"], 1
        )

        targeted = minimal_digest()
        targeted.pop("overview")
        targeted["reading"] = {
            "status": "targeted",
            "sections": [{"heading": "3 Results", "gist": "结果。"}],
            "unread_sections": ["Other sections"],
        }
        self.assertEqual(
            literature_db.section_coverage(literature_db.validate_digest(targeted), text),
            {"summarized": 1, "thin": []},
        )

    def test_ingest_rejects_a_full_reading_that_leaves_out_an_article_section(self):
        body = " ".join(["The fitted model describes the observed burst energies well."] * 30)
        source = self.root / "longer"
        source.mkdir()
        manifest = sample_manifest(
            source,
            body=b"<html>longer article</html>",
            text_body=ARTICLE_TEXT.replace(
                "References\n", f"6 Outlook\n{body}\n\nReferences\n"
            ),
        )
        digest = current_digest()
        with self.assertRaisesRegex(
            literature_db.LiteratureError, "each with its gist: 6 Outlook"
        ):
            literature_db.ingest_record(
                self.connection, self.fts5, self.library, manifest, digest, merge=False
            )
        artifact_hash = manifest["selected"]["sha256"]
        self.assertFalse(
            (self.library / "objects" / artifact_hash[:2] / artifact_hash).exists()
        )
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM versions").fetchone()[0], 1
        )
        digest["reading"]["sections"].append(
            {"heading": "6 Outlook", "gist": "Planned follow-up observations."}
        )
        result = literature_db.ingest_record(
            self.connection, self.fts5, self.library, manifest, digest, merge=False
        )
        self.assertEqual(result["section_summaries"], {"summarized": 5, "thin": []})

    def test_targeted_merge_fills_missing_section_summaries_and_keeps_stored_ones(self):
        stored = json.loads(
            self.connection.execute(
                "SELECT digest_json FROM digests WHERE id = ?", (self.result["digest_id"],)
            ).fetchone()["digest_json"]
        )
        for entry in stored["reading"]["sections"]:
            if entry["heading"] == "4":
                entry.pop("gist")
        self.connection.execute(
            "UPDATE digests SET digest_json = ? WHERE id = ?",
            (literature_db.json_text(stored), self.result["digest_id"]),
        )
        self.connection.commit()
        incoming = minimal_digest()
        incoming.pop("overview")
        incoming["facets"][0].update(key="cadence", label="Cadence")
        incoming["facets"][0]["findings"][0].update(
            statement="Comparisons are limited by cadence.",
            kind="limitation",
            locator={"section": "4"},
            quote="which limits comparisons",
            values=[],
        )
        incoming["reading"] = {
            "status": "targeted",
            "sections": [
                {"heading": "3.1", "gist": "A replaced gist."},
                {"heading": "4", "gist": "Cadence caveats."},
            ],
            "unread_sections": ["Other sections"],
        }
        result = literature_db.ingest_record(
            self.connection, self.fts5, self.library, self.manifest, incoming, merge=True
        )
        self.assertEqual(result["status"], "updated")
        self.assertEqual(result["anchors"]["located"], 1)
        stored = json.loads(
            self.connection.execute(
                "SELECT digest_json FROM digests WHERE id = ?", (self.result["digest_id"],)
            ).fetchone()["digest_json"]
        )
        sections = {entry["heading"]: entry.get("gist") for entry in stored["reading"]["sections"]}
        self.assertEqual(sections["3.1"], "Burst detections and the event rate across sessions.")
        self.assertEqual(sections["4"], "Cadence caveats.")
        self.assertEqual(stored["reading"]["status"], "full")
        self.assertEqual(stored["overview"]["tldr"], self.digest["overview"]["tldr"])
        found = self.passage(findings=["cadence.1"])["passages"][0]
        self.assertEqual(found["section"], "4 Discussion")



class SearchIndexTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.library = self.root / "library"
        self.source = self.root / "source"
        self.source.mkdir()
        self.connection, self.fts5 = literature_db.connect_library(self.library)
        if not self.fts5:
            self.skipTest("SQLite lacks FTS5")
        literature_db.ingest_record(
            self.connection, self.fts5, self.library, sample_manifest(self.source),
            sample_digest(), merge=False,
        )

    def tearDown(self):
        self.connection.close()
        self.temporary.cleanup()

    def matches(self, term):
        return self.connection.execute(
            "SELECT COUNT(*) FROM search_fts WHERE search_fts MATCH ?", (term,)
        ).fetchone()[0]

    def test_index_follows_search_documents_without_a_second_copy(self):
        self.assertEqual(self.matches("micropulse"), 1)
        document = dict(
            self.connection.execute("SELECT * FROM search_documents").fetchone()
        )
        document["full_text"] = "A replacement text about quasiperiodic oscillations."
        literature_db.replace_search_document(
            self.connection, {key: str(value) for key, value in document.items()}
        )
        self.assertEqual(self.matches("micropulse"), 0)
        self.assertEqual(self.matches("quasiperiodic"), 1)
        tables = {
            row[0]
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        self.assertNotIn("search_fts_content", tables)
        self.assertNotIn("facets", tables)
        self.assertNotIn("findings", tables)

    def test_audit_reports_index_rows_missing_from_the_index(self):
        audit = literature_db.audit_library(
            self.connection, self.fts5, self.library, verify_hashes=False
        )
        self.assertEqual(audit["errors"], [])
        row = self.connection.execute("SELECT * FROM search_documents").fetchone()
        columns = ", ".join(literature_db.SEARCH_COLUMNS)
        self.connection.execute(
            f"INSERT INTO search_fts(search_fts, rowid, {columns}) VALUES ('delete', ?, "
            + ", ".join("?" for _ in literature_db.SEARCH_COLUMNS)
            + ")",
            (row["id"], *(row[column] for column in literature_db.SEARCH_COLUMNS)),
        )
        self.connection.commit()
        audit = literature_db.audit_library(
            self.connection, self.fts5, self.library, verify_hashes=False
        )
        self.assertIn("fts_document_mismatch", [item["kind"] for item in audit["errors"]])
        literature_db.rebuild_index(self.connection, self.fts5)
        self.assertEqual(self.matches("micropulse"), 1)


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.library = self.root / "library"
        self.source = self.root / "source"
        self.source.mkdir()

    def tearDown(self):
        self.temporary.cleanup()

    def release_three_library(self, digest: dict) -> None:
        """A library laid out as release 2.0.1 stored it, holding ``digest``."""
        connection, fts5 = literature_db.connect_library(self.library)
        literature_db.ingest_record(
            connection, fts5, self.library, sample_manifest(self.source),
            sample_digest(), merge=False,
        )
        columns = ", ".join(literature_db.SEARCH_COLUMNS)
        connection.executescript(
            f"""
            DROP TRIGGER search_documents_insert;
            DROP TRIGGER search_documents_delete;
            DROP TRIGGER search_documents_update;
            DROP TABLE search_fts;
            CREATE VIRTUAL TABLE search_fts USING fts5({columns});
            INSERT INTO search_fts({columns}) SELECT {columns} FROM search_documents;
            CREATE TABLE facets (id INTEGER PRIMARY KEY, digest_id INTEGER, key TEXT);
            CREATE TABLE findings (id INTEGER PRIMARY KEY, facet_id INTEGER, statement TEXT);
            INSERT INTO facets(digest_id, key) SELECT id, 'activity' FROM digests;
            ALTER TABLE digests RENAME TO digests_current;
            CREATE TABLE digests (
                id INTEGER PRIMARY KEY,
                version_id INTEGER NOT NULL REFERENCES versions(id) ON DELETE CASCADE,
                schema_version INTEGER NOT NULL,
                language TEXT NOT NULL,
                overview TEXT NOT NULL,
                significance TEXT NOT NULL,
                reading_status TEXT NOT NULL,
                digest_hash TEXT NOT NULL,
                digest_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(version_id)
            );
            """
        )
        connection.execute(
            "INSERT INTO digests SELECT id, version_id, ?, 'zh-CN', ?, ?, reading_status, "
            "'legacy', ?, updated_at FROM digests_current",
            (
                digest["schema_version"],
                digest["overview"]["summary"],
                digest["overview"].get("significance", ""),
                literature_db.json_text(digest),
            ),
        )
        connection.execute("DROP TABLE digests_current")
        connection.execute("PRAGMA user_version = 3")
        connection.commit()
        connection.close()

    def stored_digest(self, connection) -> dict:
        return json.loads(
            connection.execute("SELECT digest_json FROM digests").fetchone()[0]
        )

    def test_migrate_converts_a_release_three_library(self):
        self.release_three_library(legacy_digest())
        with self.assertRaisesRegex(literature_db.LiteratureError, "run literature_db.py migrate"):
            literature_db.connect_library(self.library)
        output = io.StringIO()
        code = literature_db.run(
            [
                "--library-dir", str(self.library), "migrate",
                "--destination", str(self.root / "backup"),
            ],
            stdout=output,
        )
        self.assertEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "migrated")
        self.assertEqual(result["digests"], {"converted": 1, "by_source_schema": {"2": 1}})
        self.assertEqual(
            set(result["assigned_by_rule"]),
            {"value statuses", "entity types", "dataset types", "study types"},
        )
        self.assertEqual(result["integrity"], ["ok"])
        backup = sqlite3.connect(Path(result["backup"]) / "literature.sqlite3")
        self.assertEqual(backup.execute("PRAGMA user_version").fetchone()[0], 3)
        backup.close()

        connection, fts5 = literature_db.connect_library(self.library)
        try:
            columns = [row[1] for row in connection.execute("PRAGMA table_info(digests)")]
            self.assertEqual(
                columns,
                ["id", "version_id", "reading_status", "digest_hash", "digest_json", "updated_at"],
            )
            digest = self.stored_digest(connection)
            self.assertEqual(digest["schema_version"], 4)
            self.assertEqual(
                digest["overview"]["tldr"],
                "FAST measured the activity and polarization of FRB 20220912A.",
            )
            self.assertIn("It links activity and polarization.", digest["overview"]["summary"])
            self.assertNotIn("significance", digest["overview"])
            self.assertEqual(digest["overview"]["study_types"], ["observational"])
            self.assertEqual(digest["entities"][0]["type"], "source")
            self.assertEqual(digest["datasets"][0]["type"], "observation")
            self.assertIn("（仪器：FAST；波段：1-1.5 GHz）", digest["datasets"][0]["description"])
            self.assertTrue(digest["methods"][0]["description"].startswith("Detect bursts."))
            self.assertNotIn("PRESTO.", digest["methods"][0]["description"][-8:])
            self.assertIn("PRESTO", digest["keywords"])
            self.assertIn(
                "活跃性与事件率：The measured rate depends on observing cadence.",
                digest["global_limitations"],
            )
            polarization = digest["facets"][1]
            self.assertEqual(polarization["methods"], ["RM synthesis"])
            self.assertIn("polarization calibration", polarization["keywords"])
            statuses = {
                value["name"]: value["status"]
                for finding in polarization["findings"]
                for value in finding.get("values", [])
            }
            self.assertEqual(statuses, {"mean RM": "measured", "RM upper limit": "upper-limit"})
            headings = [section["heading"] for section in digest["reading"]["sections"]]
            self.assertNotIn("References", headings)
            self.assertIn("由 schema 2 迁移转换", digest["reading"]["notes"])
            self.assertIn("数值状态", digest["reading"]["notes"])
            self.assertNotIn("coverage", digest["reading"])
            found = literature_db.search_library(
                connection, fts5, "micropulse", scope="fulltext", mode="terms",
                topics=[], year_from=None, year_to=None, limit=10,
            )
            self.assertEqual(found["count"], 1)
            audit = literature_db.audit_library(connection, fts5, self.library, verify_hashes=True)
            self.assertEqual(audit["errors"], [])
        finally:
            connection.close()
        again = literature_db.run(["--library-dir", str(self.library), "migrate"], stdout=io.StringIO())
        self.assertEqual(again, 0)

    def test_schema_three_records_keep_their_content(self):
        library_migrate = importlib.import_module("library_migrate")
        digest, assigned = library_migrate.upgrade_digest(schema3_digest(), "A title")
        self.assertEqual(assigned, {})
        self.assertNotIn("Converted", digest["reading"].get("notes", ""))
        self.assertEqual(
            [section["heading"] for section in digest["reading"]["sections"]],
            ["1", "2", "3.1", "3.2", "3.3", "4", "5"],
        )
        self.assertEqual(literature_db.validate_digest(digest), digest)
        with self.assertRaisesRegex(literature_db.LiteratureError, "must be 4"):
            literature_db.validate_digest(schema3_digest())

    def test_first_sentence_skips_abbreviations(self):
        library_migrate = importlib.import_module("library_migrate")
        self.assertEqual(
            library_migrate.first_sentence(
                "Zhang et al. measured 1076 bursts. They also fit spectra."
            ),
            "Zhang et al. measured 1076 bursts.",
        )
        self.assertEqual(
            library_migrate.first_sentence("研究测量了暴发率。随后讨论偏振。"),
            "研究测量了暴发率。",
        )
        self.assertEqual(library_migrate.first_sentence("No terminal stop"), "No terminal stop")


class CliTests(unittest.TestCase):
    def test_template_and_validation_do_not_create_a_database(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = io.StringIO()
            code = literature_db.run(
                ["--library-dir", temporary, "template"], stdout=output
            )
            self.assertEqual(code, 0)
            self.assertFalse((Path(temporary) / "literature.sqlite3").exists())

            digest_path = Path(temporary) / "digest.json"
            digest_path.write_text(
                json.dumps(in_chinese(sample_digest())), encoding="utf-8"
            )
            output = io.StringIO()
            code = literature_db.run(
                ["--library-dir", temporary, "validate-digest", str(digest_path)],
                stdout=output,
            )
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output.getvalue())["status"], "valid")
            self.assertFalse((Path(temporary) / "literature.sqlite3").exists())

    def test_authoring_commands_require_chinese_digests(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            english = sample_digest()
            mislabeled = in_chinese(sample_digest())
            mislabeled["language"] = "en"
            for name, digest, message in (
                ("english", english, "finding activity-event-rate.1"),
                ("mislabeled", mislabeled, "digest.language must be zh-CN"),
            ):
                digest_path = root / f"{name}.json"
                digest_path.write_text(json.dumps(digest), encoding="utf-8")
                stderr = io.StringIO()
                code = literature_db.run(
                    ["validate-digest", str(digest_path)],
                    stdout=io.StringIO(),
                    stderr=stderr,
                )
                self.assertEqual(code, 2)
                self.assertIn(message, stderr.getvalue())

            source = root / "source"
            source.mkdir()
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(sample_manifest(source)), encoding="utf-8"
            )
            library = root / "library"
            stderr = io.StringIO()
            code = literature_db.run(
                [
                    "--library-dir",
                    str(library),
                    "ingest",
                    "--manifest",
                    str(manifest_path),
                    "--digest",
                    str(root / "english.json"),
                ],
                stdout=io.StringIO(),
                stderr=stderr,
            )
            self.assertEqual(code, 2)
            self.assertIn("in Chinese", stderr.getvalue())

            chinese_path = root / "chinese.json"
            chinese_path.write_text(
                json.dumps(in_chinese(sample_digest())), encoding="utf-8"
            )
            output = io.StringIO()
            code = literature_db.run(
                [
                    "--library-dir",
                    str(library),
                    "ingest",
                    "--manifest",
                    str(manifest_path),
                    "--digest",
                    str(chinese_path),
                ],
                stdout=output,
            )
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output.getvalue())["status"], "ingested")

    def test_authoring_commands_require_a_summary_of_every_read_section(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            digest = in_chinese(sample_digest())
            digest["reading"]["sections"][1].pop("gist")
            digest["reading"]["sections"].append("6 Outlook")
            digest_path = root / "digest.json"
            digest_path.write_text(json.dumps(digest), encoding="utf-8")
            source = root / "source"
            source.mkdir()
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(sample_manifest(source)), encoding="utf-8"
            )
            for command in (
                ["validate-digest", str(digest_path)],
                [
                    "--library-dir",
                    str(root / "library"),
                    "ingest",
                    "--manifest",
                    str(manifest_path),
                    "--digest",
                    str(digest_path),
                ],
            ):
                with self.subTest(command=command[0]):
                    stderr = io.StringIO()
                    code = literature_db.run(
                        command, stdout=io.StringIO(), stderr=stderr
                    )
                    self.assertEqual(code, 2)
                    self.assertIn("Summarize each read section", stderr.getvalue())
                    self.assertIn("2, 6 Outlook", stderr.getvalue())

    def test_compact_returns_freed_pages_and_keeps_the_library_intact(self):
        with tempfile.TemporaryDirectory() as temporary:
            library = Path(temporary) / "library"
            connection, _fts5 = literature_db.connect_library(library)
            with connection:
                connection.execute("CREATE TABLE filler(body TEXT)")
                connection.executemany(
                    "INSERT INTO filler VALUES (?)", [("x" * 4000,)] * 500
                )
            with connection:
                connection.execute("DROP TABLE filler")
            connection.close()
            output = io.StringIO()
            code = literature_db.run(
                ["--library-dir", str(library), "compact"], stdout=output
            )
            self.assertEqual(code, 0)
            report = json.loads(output.getvalue())
            self.assertEqual(report["status"], "compacted")
            self.assertEqual(report["integrity"], ["ok"])
            self.assertGreater(report["bytes_freed"], 1_000_000)
            self.assertEqual(
                report["bytes_after"], (library / "literature.sqlite3").stat().st_size
            )

    def test_audit_uses_a_read_only_database_connection(self):
        with tempfile.TemporaryDirectory() as temporary:
            library = Path(temporary) / "library"
            stderr = io.StringIO()
            code = literature_db.run(
                ["--library-dir", str(library), "audit"], stderr=stderr
            )
            self.assertEqual(code, 2)
            self.assertIn("does not exist", stderr.getvalue())
            self.assertFalse((library / "literature.sqlite3").exists())

            connection, _fts5 = literature_db.connect_library(library)
            connection.close()
            database = library / "literature.sqlite3"
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            output = io.StringIO()
            code = literature_db.run(
                ["--library-dir", str(library), "audit"], stdout=output
            )
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output.getvalue())["status"], "healthy")
            after = hashlib.sha256(database.read_bytes()).hexdigest()
            self.assertEqual(after, before)

    def test_lookup_on_missing_library_is_read_only_and_returns_not_found(self):
        with tempfile.TemporaryDirectory() as temporary:
            library = Path(temporary) / "missing-library"
            output = io.StringIO()

            code = literature_db.run(
                [
                    "--library-dir",
                    str(library),
                    "lookup",
                    "2023ApJ...955..142Z",
                ],
                stdout=output,
            )

            self.assertEqual(code, 0)
            result = json.loads(output.getvalue())["results"][0]
            self.assertEqual(result["reuse_status"], "not_found")
            self.assertFalse(library.exists())

    def test_validate_digest_reports_warnings_and_reference_mode(self):
        with tempfile.TemporaryDirectory() as temporary:
            digest = current_digest()
            digest["facets"][1]["findings"][0]["statement"] = "About 40 percent reverse sign."
            digest_path = Path(temporary) / "digest.json"
            digest_path.write_text(json.dumps(in_chinese(digest)), encoding="utf-8")
            output = io.StringIO()
            code = literature_db.run(
                ["--library-dir", temporary, "validate-digest", str(digest_path)],
                stdout=output,
            )
            self.assertEqual(code, 0)
            report = json.loads(output.getvalue())
            self.assertEqual(report["schema_version"], 4)
            self.assertTrue(report["references_checked"])
            self.assertEqual(
                [warning["path"] for warning in report["warnings"]],
                ["facets[1].findings[0]"],
            )

    def test_parameters_cli_is_read_only_and_exports_csv(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            library = root / "library"
            output = io.StringIO()
            code = literature_db.run(
                ["--library-dir", str(library), "parameters", "RM"], stdout=output
            )
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output.getvalue())["count"], 0)
            self.assertFalse(library.exists())

            source = root / "source"
            source.mkdir()
            connection, fts5 = literature_db.connect_library(library)
            try:
                literature_db.ingest_record(
                    connection,
                    fts5,
                    library,
                    sample_manifest(source),
                    sample_digest(),
                    merge=False,
                    replace_digest=False,
                )
            finally:
                connection.close()
            database = library / "literature.sqlite3"
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            target = root / "parameters.csv"
            output = io.StringIO()
            code = literature_db.run(
                [
                    "--library-dir",
                    str(library),
                    "parameters",
                    "--format",
                    "csv",
                    "--output",
                    str(target),
                ],
                stdout=output,
            )
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output.getvalue())["count"], 3)
            text = target.read_text(encoding="utf-8-sig")
            self.assertTrue(text.startswith("bibcode,citekey"))
            output = io.StringIO()
            code = literature_db.run(
                [
                    "--library-dir",
                    str(library),
                    "findings",
                    "rotation measure",
                    "--kind",
                    "measurement",
                ],
                stdout=output,
            )
            self.assertEqual(code, 0)
            findings = json.loads(output.getvalue())
            self.assertEqual(findings["count"], 1)
            self.assertEqual(findings["results"][0]["match"], "finding")
            self.assertEqual(hashlib.sha256(database.read_bytes()).hexdigest(), before)

            stderr = io.StringIO()
            code = literature_db.run(
                [
                    "--library-dir",
                    str(library),
                    "parameters",
                    "--output",
                    str(library / "inside.json"),
                ],
                stderr=stderr,
            )
            self.assertEqual(code, 2)
            self.assertIn("outside the managed library", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
