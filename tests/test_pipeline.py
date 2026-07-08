from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from amd_hackathon_app.pipeline import (
    LlamaCppProvider,
    local_certification_for,
    parse_allowed_models,
    route_task,
    run_scenario,
    run_tasks_file,
)
from amd_hackathon_app.ui import summarize_records


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

    def test_version5_certification_is_conservative_until_model_artifact_exists(self) -> None:
        certification = local_certification_for("SENTIMENT_CLASSIFICATION")
        self.assertEqual(certification["local_status"], "LOCAL_DENIED")
        self.assertEqual(certification["fireworks_policy"], "ALLOWED_MODELS_ONLY")
        self.assertEqual(certification["benchmark_status"], "blocked_until_model_artifact_and_tests_exist")

    def test_version5_routes_to_fireworks_when_local_is_not_certified(self) -> None:
        decision = route_task(
            task_family="sentiment",
            jurisdiction="SENTIMENT_CLASSIFICATION",
            provider_override="version5",
            allowed_models=["allowed-model-a"],
        )
        self.assertEqual(decision.candidate_version, "version_5")
        self.assertEqual(decision.provider, "fireworks")
        self.assertEqual(decision.selected_path, "fireworks")
        self.assertEqual(decision.model, "allowed-model-a")

    def test_llama_cpp_provider_reports_missing_binary(self) -> None:
        provider = LlamaCppProvider()
        provider.binary = "/tmp/amd-hackathon-missing-llama-cli"
        with self.assertRaisesRegex(RuntimeError, "llama.cpp binary not found"):
            provider.complete("Return yes.", "/tmp/amd-hackathon-missing-model.gguf")

    def test_ui_summary_separates_judged_fireworks_tokens(self) -> None:
        summary = summarize_records(
            [
                {
                    "status": "completed",
                    "selected_provider": "fireworks",
                    "selected_model": "allowed-model-a",
                    "token_usage": {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13},
                    "latency": {"milliseconds": 50},
                    "validation_result": {"passed": True},
                },
                {
                    "status": "completed",
                    "selected_provider": "ollama-demo",
                    "selected_model": "qwen2.5-coder:3b",
                    "token_usage": {"prompt_tokens": 7, "completion_tokens": 2, "total_tokens": 9},
                    "latency": {"milliseconds": 25},
                    "validation_result": {"passed": True},
                },
            ]
        )
        self.assertEqual(summary["total_tokens"], 22)
        self.assertEqual(summary["judged_fireworks_tokens"], 13)
        self.assertEqual(summary["local_or_demo_tokens"], 9)


if __name__ == "__main__":
    unittest.main()
