from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from amd_hackathon_app.pipeline import parse_allowed_models, run_scenario, run_tasks_file


class PipelineTests(unittest.TestCase):
    def test_mock_classification_vertical_slice_records_required_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            record = run_scenario("classification-basic", provider_override="mock", run_dir=Path(tmp))

        for field in [
            "task_id",
            "task_family",
            "work_jurisdiction",
            "answer_schema",
            "selected_evidence_refs",
            "omitted_context_reason",
            "compiled_prompt",
            "estimated_input_tokens",
            "token_budget",
            "selected_provider",
            "selected_model",
            "routing_reason",
            "final_mode_compliant",
            "validation_result",
            "repair",
            "token_usage",
            "latency",
        ]:
            self.assertIn(field, record)

        self.assertEqual(record["selected_provider"], "mock")
        self.assertIn(record["work_jurisdiction"], {"CONTEXT_SELECTION", "ANSWER_SCHEMA_SELECTION", "PROMPT_OPTIMIZATION"})
        self.assertTrue(record["validation_result"]["passed"])
        self.assertGreater(record["token_usage"]["total_tokens"], 0)

    def test_json_validation_scenario(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            record = run_scenario("json-extraction-basic", provider_override="mock", run_dir=Path(tmp))
        self.assertTrue(record["validation_result"]["passed"])
        self.assertEqual(json.loads(record["output"])["track"], "AMD Hackathon Track 1")

    def test_allowed_models_parses_comma_and_json_values(self) -> None:
        self.assertEqual(parse_allowed_models("model-a, model-b"), ["model-a", "model-b"])
        self.assertEqual(parse_allowed_models('["model-a", "model-b"]'), ["model-a", "model-b"])

    def test_run_tasks_file_writes_results_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "input" / "tasks.json"
            output_path = root / "output" / "results.json"
            input_path.parent.mkdir()
            input_path.write_text(
                json.dumps({"tasks": [{"id": "one", "prompt": "Classify sentiment: fine", "expected_format": "json"}]}),
                encoding="utf-8",
            )
            payload = run_tasks_file(input_path=input_path, output_path=output_path, provider_override="mock")
            self.assertTrue(output_path.exists())

        self.assertEqual(payload["schema"], "amd_hackathon.results.v3")
        self.assertEqual(payload["results"][0]["selected_provider"], "mock")


if __name__ == "__main__":
    unittest.main()
