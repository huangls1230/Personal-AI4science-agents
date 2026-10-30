"""Offline checks of the schema's used keywords; not a full JSON Schema implementation."""

import copy
import hashlib
import json
from pathlib import Path
import re
import unittest

TEAM = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((TEAM / "review-finding.schema.json").read_text())
CASES = json.loads((TEAM / "fixtures/findings.example.json").read_text())


def valid(value, schema):
    """Evaluate only the keywords used by this schema, rejecting unknown ones."""
    supported = {"$schema", "$defs", "$ref", "title", "description", "type", "additionalProperties",
                 "required", "properties", "const", "enum", "minLength", "pattern", "items",
                 "minItems", "allOf", "if", "then"}
    if set(schema) - supported:
        raise AssertionError(f"Unsupported schema keywords: {set(schema) - supported}")
    if "$ref" in schema:
        node = SCHEMA
        for part in schema["$ref"].removeprefix("#/").split("/"):
            node = node[part]
        return valid(value, node)
    kind = schema.get("type")
    if kind and not isinstance(value, {"object": dict, "array": list, "string": str}[kind]):
        return False
    if "const" in schema and value != schema["const"]:
        return False
    if "enum" in schema and value not in schema["enum"]:
        return False
    if isinstance(value, str) and (len(value) < schema.get("minLength", 0) or
                                   ("pattern" in schema and not re.search(schema["pattern"], value))):
        return False
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            return False
        if "items" in schema and not all(valid(item, schema["items"]) for item in value):
            return False
    if isinstance(value, dict):
        if not set(schema.get("required", [])) <= set(value):
            return False
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False and set(value) - set(properties):
            return False
        if not all(valid(v, properties[k]) for k, v in value.items() if k in properties):
            return False
    if not all(valid(value, part) for part in schema.get("allOf", [])):
        return False
    if "if" in schema and valid(value, schema["if"]) and "then" in schema and not valid(value, schema["then"]):
        return False
    return True


class FindingChecks(unittest.TestCase):
    def test_all_four_statuses(self):
        self.assertEqual({c["verification_status"] for c in CASES},
                         {"verified", "potential", "insufficient_information", "not_checked"})
        for case in CASES:
            with self.subTest(status=case["verification_status"]):
                self.assertTrue(valid(case, SCHEMA))

    def test_evidence_required_for_verified_and_potential(self):
        for case in CASES[:2]:
            bad = copy.deepcopy(case)
            bad["evidence_location"] = []
            self.assertFalse(valid(bad, SCHEMA))

    def test_invalid_fields(self):
        for field, value in [("verification_status", "replicated"), ("reviewer_role", "review_lead"),
                             ("severity", "severe"), ("reasoning", " ")]:
            bad = copy.deepcopy(CASES[0])
            bad[field] = value
            self.assertFalse(valid(bad, SCHEMA), field)
        bad = copy.deepcopy(CASES[0])
        bad["evidence_location"][0]["artifact"]["sha256"] = "not-a-digest"
        self.assertFalse(valid(bad, SCHEMA))
        bad = copy.deepcopy(CASES[0])
        del bad["evidence_location"][0]["locator"]
        self.assertFalse(valid(bad, SCHEMA))

    def test_fixture_hash_and_locations(self):
        paper = (TEAM / "fixtures/manuscript.md").read_bytes()
        digest = hashlib.sha256(paper).hexdigest()
        for case in CASES[:2]:
            self.assertEqual(case["evidence_location"][0]["artifact"]["sha256"], digest)
            self.assertIn("Experiments", case["source_location"])

    def test_report_template_fields(self):
        report = (TEAM / "templates/review-report-template.md").read_text()
        for field in ("finding_id", "verification status", "Source location", "Evidence references",
                      "Verification method", "Reasoning and impact", "Recommended action",
                      "Additional material required", "actual execution mode"):
            self.assertIn(field, report)


if __name__ == "__main__":
    unittest.main()
