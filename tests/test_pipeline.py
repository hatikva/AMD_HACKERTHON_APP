from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from amd_hackathon_app.pipeline import run_scenario


class PipelineTests(unittest.TestCase):
    def test_mock_classification_vertical_slice_records_required_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            record = run_scenario("classification-basic", provider_override="mock", run_dir=Path(tmp))

        for field in [
            "task_id",
            "profile_id",
            "task_family",
            "difficulty_estimate",
            "router_confidence",
            "retrieval_query",
            "selected_memory_refs",
            "selected_evidence_refs",
            "omitted_context_reason",
            "compiled_prompt",
            "estimated_input_tokens",
            "selected_provider",
            "selected_model",
            "fallback_or_escalation_reason",
            "validation_result",
            "token_usage",
            "latency",
            "provenance",
        ]:
            self.assertIn(field, record)

        self.assertEqual(record["selected_provider"], "mock")
        self.assertTrue(record["validation_result"]["passed"])
        self.assertGreater(record["token_usage"]["total_tokens"], 0)

    def test_json_validation_scenario(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            record = run_scenario("json-extraction-basic", provider_override="mock", run_dir=Path(tmp))
        self.assertTrue(record["validation_result"]["passed"])
        self.assertEqual(json.loads(record["output"])["track"], "AMD Hackathon Track 1")


if __name__ == "__main__":
    unittest.main()
