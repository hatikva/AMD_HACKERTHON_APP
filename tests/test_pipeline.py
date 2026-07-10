from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from amd_hackathon_app.env import load_dotenv
from amd_hackathon_app import pipeline as pipeline_module
from amd_hackathon_app.benchmarks import (
    BENCHMARK_SUITE_ID,
    CANONICAL_BENCHMARK_PATH,
    CANONICAL_CATEGORIES,
    evaluate_output,
    load_category_benchmark,
    model_visible_task,
    run_category_benchmark,
)
from amd_hackathon_app.pipeline import (
    LlamaCppProvider,
    ProviderResult,
    Task,
    local_certification_for,
    parse_allowed_models,
    route_task,
    run_task,
    run_scenario,
    run_tasks_file,
)
from amd_hackathon_app.ui import summarize_records


class PipelineTests(unittest.TestCase):
    def test_load_dotenv_sets_missing_values_without_overriding_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "ALLOWED_MODELS=accounts/fireworks/models/minimax-m3",
                        "FIREWORKS_BASE_URL=https://example.invalid/v1",
                        "EXPLICIT_VALUE=from-file",
                        "QUOTED_VALUE='quoted content'",
                    ]
                ),
                encoding="utf-8",
            )
            env_keys = [
                "ALLOWED_MODELS",
                "FIREWORKS_BASE_URL",
                "EXPLICIT_VALUE",
                "QUOTED_VALUE",
            ]
            old_values = {key: os.environ.get(key) for key in env_keys}
            try:
                for key in old_values:
                    os.environ.pop(key, None)
                os.environ["EXPLICIT_VALUE"] = "from-environment"

                load_dotenv(env_path)

                self.assertEqual(os.environ["ALLOWED_MODELS"], "accounts/fireworks/models/minimax-m3")
                self.assertEqual(os.environ["FIREWORKS_BASE_URL"], "https://example.invalid/v1")
                self.assertEqual(os.environ["EXPLICIT_VALUE"], "from-environment")
                self.assertEqual(os.environ["QUOTED_VALUE"], "quoted content")
            finally:
                for key, value in old_values.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value

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

    def test_llama_cpp_provider_command_uses_configured_limits(self) -> None:
        provider = LlamaCppProvider()
        provider.binary = "/app/bin/llama-cli"
        provider.context_length = 2048
        provider.threads = 2
        provider.max_tokens = 128

        command = provider.command_for("Return yes.", "/app/models/model.gguf")

        self.assertEqual(command[0], "/app/bin/llama-cli")
        self.assertIn("/app/models/model.gguf", command)
        self.assertIn("2048", command)
        self.assertIn("2", command)
        self.assertIn("128", command)

    def test_llama_cpp_provider_timeout_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = root / "llama-cli"
            model = root / "model.gguf"
            binary.write_text("#!/usr/bin/env sh\nsleep 2\n", encoding="utf-8")
            binary.chmod(0o755)
            model.write_text("not-a-real-model", encoding="utf-8")

            provider = LlamaCppProvider()
            provider.binary = str(binary)
            provider.timeout_seconds = 1

            with self.assertRaisesRegex(RuntimeError, "llama.cpp timed out"):
                provider.complete("Return yes.", str(model))

    def test_version5_local_validation_failure_falls_back_without_losing_candidate_identity(self) -> None:
        original = dict(pipeline_module.VERSION_5_LOCAL_CERTIFICATION["SENTIMENT_CLASSIFICATION"])

        class FakeLocalProvider:
            def complete(self, prompt: str, model: str) -> ProviderResult:
                return ProviderResult(text="not json", token_usage={"total_tokens": 0}, latency_ms=5)

        class FakeFireworksProvider:
            def complete(self, prompt: str, model: str) -> ProviderResult:
                return ProviderResult(
                    text='{"label":"neutral"}',
                    token_usage={"prompt_tokens": 11, "completion_tokens": 3, "total_tokens": 14},
                    latency_ms=9,
                )

        def fake_provider_for(name: str) -> object:
            if name == "llama-cpp":
                return FakeLocalProvider()
            if name == "fireworks":
                return FakeFireworksProvider()
            raise AssertionError(name)

        try:
            pipeline_module.VERSION_5_LOCAL_CERTIFICATION["SENTIMENT_CLASSIFICATION"] = {
                "local_status": "LOCAL_CERTIFIED",
                "fallback": "FIREWORKS_ON_VALIDATION_FAILURE",
                "validator_coverage": "high",
            }
            task = Task(
                id="sentiment-local-fallback",
                prompt="Classify sentiment: fine",
                task_family="sentiment",
                expected_format="json",
            )
            with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
                pipeline_module, "provider_for", side_effect=fake_provider_for
            ):
                record = run_task(
                    task,
                    provider_override="version5",
                    allowed_models=["allowed-fireworks-model"],
                    run_dir=Path(tmp),
                )
        finally:
            pipeline_module.VERSION_5_LOCAL_CERTIFICATION["SENTIMENT_CLASSIFICATION"] = original

        self.assertEqual(record["candidate_version"], "version_5")
        self.assertEqual(record["selected_provider"], "fireworks")
        self.assertEqual(record["selected_path"], "local_then_fireworks_fallback")
        self.assertEqual(record["selected_model"], "allowed-fireworks-model")
        self.assertTrue(record["local_attempted"])
        self.assertFalse(record["local_success"])
        self.assertEqual(record["retry_count"], 1)
        self.assertEqual(record["fireworks_token_usage"]["total_tokens"], 14)
        self.assertEqual(record["local_certification"]["local_status"], "LOCAL_CERTIFIED")
        self.assertTrue(record["validation_result"]["passed"])

    def test_version5_public_docs_exist(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.assertTrue((root / "docs" / "version5-local-first-candidate.json").exists())
        self.assertTrue((root / "Dockerfile.version5").exists())

    def test_canonical_version5_category_benchmark_loads_with_expected_integrity(self) -> None:
        suite = load_category_benchmark()

        self.assertEqual(suite.suite_id, BENCHMARK_SUITE_ID)
        self.assertEqual(len(suite.tasks), 40)
        self.assertEqual({row["id"] for row in suite.payload["categories"]}, set(CANONICAL_CATEGORIES))
        self.assertEqual(len({row["id"] for row in suite.tasks}), 40)
        self.assertEqual(len({row["prompt"] for row in suite.tasks}), 40)
        self.assertEqual(len(suite.content_hash), 64)

        for category in CANONICAL_CATEGORIES:
            rows = [row for row in suite.tasks if row["task_category"] == category]
            self.assertEqual(len(rows), 5)
            self.assertEqual(sorted(row["difficulty_hint"] for row in rows), [1, 2, 3, 4, 5])
            self.assertTrue(all("evaluation" in row for row in rows))

    def test_benchmark_model_visible_projection_excludes_evaluation_metadata(self) -> None:
        task = load_category_benchmark().tasks[0]
        visible = model_visible_task(task)

        self.assertIn("prompt", visible)
        self.assertIn("task_category", visible)
        self.assertNotIn("evaluation", visible)
        self.assertNotIn("accepted_answers", json.dumps(visible).lower())
        self.assertNotIn("reference_solution", json.dumps(visible).lower())

    def test_category_benchmark_mock_run_records_qualification_metadata_without_authorizing(self) -> None:
        before = dict(pipeline_module.VERSION_5_LOCAL_CERTIFICATION)
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "qualification" / "mock-results.json"
            result = run_category_benchmark(provider="mock", output_path=output_path)
            self.assertTrue(output_path.exists())

        self.assertEqual(result["benchmark_suite"], BENCHMARK_SUITE_ID)
        self.assertEqual(result["benchmark_hash"], load_category_benchmark().content_hash)
        self.assertEqual(result["candidate"], {"provider": "mock", "model": "mock-model"})
        self.assertEqual(result["qualification_status"], "PENDING_POLICY_REVIEW")
        self.assertFalse(result["authorization_registry_mutated"])
        self.assertEqual(pipeline_module.VERSION_5_LOCAL_CERTIFICATION, before)
        self.assertEqual(len(result["results"]), 40)
        self.assertIn("FACTUAL_KNOWLEDGE", result["summary"]["by_category"])
        self.assertIn("5", result["summary"]["by_difficulty"])

    def test_benchmark_result_keeps_local_and_fireworks_token_accounting_separate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_category_benchmark(provider="mock", output_path=Path(tmp) / "mock-results.json")

        first = result["results"][0]
        self.assertEqual(first["judged_fireworks_tokens"], 0)
        self.assertEqual(first["local_estimated_input_tokens"], 0)
        self.assertEqual(first["local_estimated_output_tokens"], 0)
        self.assertEqual(first["route_record"]["fireworks_token_usage"]["total_tokens"], 0)

    def test_unsupported_evaluator_type_fails_clearly(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported evaluator type"):
            evaluate_output("anything", {"type": "unknown_evaluator"})

    def test_code_evaluator_is_blocked_without_executing_model_code(self) -> None:
        result = evaluate_output(
            "def is_even(number):\n    while True:\n        pass",
            {"type": "python_unit_tests", "entrypoint": "is_even", "tests": [{"args": [2], "expected": True}]},
        )

        self.assertFalse(result["implemented"])
        self.assertFalse(result["passed"])
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(result["syntax_valid"])
        self.assertTrue(result["function_exists"])
        self.assertFalse(result["timeout"])

    def test_live_task_execution_does_not_run_category_benchmark_or_mutate_authorization(self) -> None:
        before = dict(pipeline_module.VERSION_5_LOCAL_CERTIFICATION)
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

        self.assertEqual(payload["schema"], "amd_hackathon.results.v3")
        self.assertNotIn("benchmark_suite", payload)
        self.assertEqual(pipeline_module.VERSION_5_LOCAL_CERTIFICATION, before)

    def test_canonical_benchmark_path_uses_version2_not_version1(self) -> None:
        self.assertEqual(CANONICAL_BENCHMARK_PATH.name, "version5_local_category_benchmarks_v2.json")
        self.assertNotIn("v1", str(CANONICAL_BENCHMARK_PATH))

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
