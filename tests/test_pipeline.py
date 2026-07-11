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
    index_submission_results,
    load_category_benchmark,
    model_visible_task,
    run_category_benchmark,
)
from amd_hackathon_app.pipeline import (
    LlamaCppProvider,
    OLLAMA_CLOUD_MODEL_MAPPINGS,
    OllamaCloudStagingProvider,
    OllamaLocalProvider,
    ProviderResult,
    STAGING_REMOTE_PROVIDER_OLLAMA_CLOUD,
    Task,
    VERSION_5_LOCAL_PROVIDER,
    VERSION_6_LOCAL_PROVIDER,
    VERSION_6_PRODUCTION_PROVIDER,
    VERSION_6_STAGING_PROVIDER,
    VERSION_6_STAGING_REMOTE_BASELINE_PROVIDER,
    local_certification_for,
    parse_allowed_models,
    parse_staging_allowed_models,
    provider_for,
    load_version6_policy,
    resolve_ollama_cloud_model,
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

    def test_staging_allowed_models_are_separate_from_production_allowed_models(self) -> None:
        self.assertEqual(parse_staging_allowed_models("minimax-m3:cloud, gemma4:31b-cloud"), ["minimax-m3:cloud", "gemma4:31b-cloud"])
        self.assertEqual(parse_allowed_models("accounts/fireworks/models/minimax-m3"), ["accounts/fireworks/models/minimax-m3"])

    def test_run_tasks_file_writes_results_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "input" / "tasks.json"
            output_path = root / "output" / "results.json"
            input_path.parent.mkdir()
            input_path.write_text(
                json.dumps([{"task_id": "one", "prompt": "Classify sentiment: fine"}]),
                encoding="utf-8",
            )
            payload = run_tasks_file(input_path=input_path, output_path=output_path, provider_override="mock")
            self.assertTrue(output_path.exists())
            public_results = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["schema"], "amd_hackathon.submission_run.v1")
        self.assertEqual(public_results, [{"answer": '{"label":"neutral","confidence":0.74}', "task_id": "one"}])
        self.assertEqual(set(public_results[0]), {"task_id", "answer"})
        self.assertEqual(payload["audit_records"][0]["selected_provider"], "mock")

    def test_version5_certification_is_conservative_until_benchmarks_promote_model(self) -> None:
        certification = local_certification_for("SENTIMENT_CLASSIFICATION")
        self.assertEqual(certification["local_status"], "LOCAL_DENIED")
        self.assertEqual(certification["local_model"], "nemotron-3-nano:4b")
        self.assertEqual(
            certification["local_model_sha256"],
            "527db2cf6c705d8fabb95693d038d9c06b4a2b0b8b0a4bbdbd01212d37242970",
        )
        self.assertEqual(certification["runtime_certification"], "OLLAMA_CERTIFIED")
        self.assertEqual(certification["local_runtime_provider"], VERSION_5_LOCAL_PROVIDER)
        self.assertEqual(certification["fireworks_policy"], "ALLOWED_MODELS_ONLY")
        self.assertEqual(certification["benchmark_status"], "selected_model_pending_real_benchmark_promotion")

    def test_version5_has_no_local_certified_jurisdictions_by_default(self) -> None:
        statuses = {
            jurisdiction: local_certification_for(jurisdiction)["local_status"]
            for jurisdiction in pipeline_module.VERSION_5_WORK_JURISDICTIONS
        }
        self.assertNotIn("LOCAL_CERTIFIED", set(statuses.values()))

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

    def test_version6_staging_remote_baseline_routes_directly_to_ollama_cloud(self) -> None:
        old_allowed = os.environ.get("STAGING_ALLOWED_MODELS")
        old_model = os.environ.get("STAGING_INFERENCE_MODEL")
        try:
            os.environ["STAGING_ALLOWED_MODELS"] = "minimax-m3:cloud"
            os.environ["STAGING_INFERENCE_MODEL"] = "minimax-m3:cloud"
            decision = route_task(
                task_family="factual_qa",
                jurisdiction="STAGING_REMOTE_BASELINE",
                provider_override=VERSION_6_STAGING_REMOTE_BASELINE_PROVIDER,
                allowed_models=[],
            )
        finally:
            if old_allowed is None:
                os.environ.pop("STAGING_ALLOWED_MODELS", None)
            else:
                os.environ["STAGING_ALLOWED_MODELS"] = old_allowed
            if old_model is None:
                os.environ.pop("STAGING_INFERENCE_MODEL", None)
            else:
                os.environ["STAGING_INFERENCE_MODEL"] = old_model

        self.assertEqual(decision.candidate_version, "version_6")
        self.assertEqual(decision.provider, VERSION_6_STAGING_REMOTE_BASELINE_PROVIDER)
        self.assertEqual(decision.model, "minimax-m3")
        self.assertEqual(decision.selected_path, "staging_remote_baseline")
        self.assertEqual(decision.reason, "staging_remote_baseline_direct_ollama_cloud")

    def test_direct_llama_cpp_route_is_available_for_uncertified_benchmarking(self) -> None:
        decision = route_task(
            task_family="sentiment",
            jurisdiction="SENTIMENT_CLASSIFICATION",
            provider_override="llama-cpp",
            allowed_models=[],
        )
        self.assertEqual(decision.candidate_version, "version_5")
        self.assertEqual(decision.provider, "llama-cpp")
        self.assertEqual(decision.selected_path, "local_rejected_runtime_evidence")
        self.assertEqual(decision.local_certification["local_status"], "LOCAL_DENIED")

    def test_direct_version5_ollama_route_is_final_candidate_benchmarking(self) -> None:
        decision = route_task(
            task_family="sentiment",
            jurisdiction="SENTIMENT_CLASSIFICATION",
            provider_override=VERSION_5_LOCAL_PROVIDER,
            allowed_models=[],
        )
        self.assertEqual(decision.candidate_version, "version_5")
        self.assertEqual(decision.provider, VERSION_5_LOCAL_PROVIDER)
        self.assertEqual(decision.model, "nemotron-3-nano:4b")
        self.assertEqual(decision.selected_path, "local_final_candidate_benchmark")
        self.assertTrue(decision.final_mode_compliant)
        self.assertEqual(decision.local_certification["local_status"], "LOCAL_DENIED")

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

        command = provider.command_for("Return yes.", "/app/models/nemotron-3-nano-4b.gguf")

        self.assertEqual(command[0], "/app/bin/llama-cli")
        self.assertIn("/app/models/nemotron-3-nano-4b.gguf", command)
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

    def test_ollama_local_provider_records_local_estimates_not_fireworks_tokens(self) -> None:
        provider = OllamaLocalProvider()
        with mock.patch.object(
            pipeline_module.OpenAICompatibleProvider,
            "complete",
            return_value=ProviderResult(
                text="4",
                token_usage={"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
                latency_ms=12,
            ),
        ):
            result = provider.complete("Return 4.", "nemotron-3-nano:4b")

        self.assertEqual(result.text, "4")
        self.assertEqual(result.token_usage["total_tokens"], 0)
        self.assertGreater(result.token_usage["local_prompt_estimate"], 0)
        self.assertGreater(result.token_usage["local_completion_estimate"], 0)

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
            if name == VERSION_5_LOCAL_PROVIDER:
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

    def test_version6_shadow_category_benchmark_loads_with_expected_integrity(self) -> None:
        suite = load_category_benchmark(Path("benchmarks/categories/version6_shadow_category_benchmarks_v1.json"))

        self.assertEqual(len(suite.tasks), 40)
        self.assertEqual({row["id"] for row in suite.payload["categories"]}, set(CANONICAL_CATEGORIES))
        self.assertEqual(len({row["id"] for row in suite.tasks}), 40)
        self.assertEqual(len({row["prompt"] for row in suite.tasks}), 40)
        for category in CANONICAL_CATEGORIES:
            rows = [row for row in suite.tasks if row["task_category"] == category]
            self.assertEqual(len(rows), 5)
            self.assertEqual(sorted(row["difficulty_hint"] for row in rows), [1, 2, 3, 4, 5])

    def test_benchmark_model_visible_projection_excludes_evaluation_metadata(self) -> None:
        task = load_category_benchmark().tasks[0]
        visible = model_visible_task(task)

        self.assertIn("prompt", visible)
        self.assertIn("task_id", visible)
        self.assertNotIn("task_category", visible)
        self.assertNotIn("task_family", visible)
        self.assertNotIn("difficulty_hint", visible)
        self.assertNotIn("expected_format", visible)
        self.assertNotIn("evaluation", visible)
        self.assertNotIn("accepted_answers", json.dumps(visible).lower())
        self.assertNotIn("reference_solution", json.dumps(visible).lower())

    def test_category_benchmark_mock_run_records_qualification_metadata_without_authorizing(self) -> None:
        before = dict(pipeline_module.VERSION_5_LOCAL_CERTIFICATION)
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "qualification" / "mock-results.json"
            result = run_category_benchmark(provider="mock", output_path=output_path)
            self.assertTrue(output_path.exists())
            self.assertTrue(Path(result["model_visible_tasks_path"]).exists())
            self.assertTrue(Path(result["official_results_path"]).exists())

        self.assertEqual(result["benchmark_suite"], BENCHMARK_SUITE_ID)
        self.assertEqual(result["benchmark_hash"], load_category_benchmark().content_hash)
        self.assertEqual(result["candidate"], {"provider": "mock", "model": "mock-model"})
        self.assertTrue(result["production_path_used"])
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
                json.dumps([{"task_id": "one", "prompt": "Classify sentiment: fine"}]),
                encoding="utf-8",
            )
            payload = run_tasks_file(input_path=input_path, output_path=output_path, provider_override="mock")
            public_results = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["schema"], "amd_hackathon.submission_run.v1")
        self.assertNotIn("benchmark_suite", payload)
        self.assertEqual(set(public_results[0]), {"task_id", "answer"})
        self.assertEqual(pipeline_module.VERSION_5_LOCAL_CERTIFICATION, before)

    def test_submission_input_rejects_rich_benchmark_object_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "input" / "tasks.json"
            output_path = root / "output" / "results.json"
            input_path.parent.mkdir()
            input_path.write_text(
                json.dumps({"tasks": [{"id": "one", "prompt": "Classify sentiment: fine"}]}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "top-level list"):
                run_tasks_file(input_path=input_path, output_path=output_path, provider_override="mock")

    def test_submission_input_rejects_extra_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "input" / "tasks.json"
            output_path = root / "output" / "results.json"
            input_path.parent.mkdir()
            input_path.write_text(
                json.dumps([{"task_id": "one", "prompt": "Classify sentiment: fine", "category": "sentiment"}]),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "only task_id and prompt"):
                run_tasks_file(input_path=input_path, output_path=output_path, provider_override="mock")

    def test_version6_production_fallback_uses_fireworks_allowed_models(self) -> None:
        decision = route_task(
            task_family="sentiment",
            jurisdiction="SENTIMENT_CLASSIFICATION",
            provider_override=VERSION_6_PRODUCTION_PROVIDER,
            allowed_models=["allowed-fireworks-model"],
        )

        self.assertEqual(decision.candidate_version, "version_6")
        self.assertEqual(decision.provider, "fireworks")
        self.assertEqual(decision.selected_path, "policy_fallback")
        self.assertEqual(decision.model, "allowed-fireworks-model")
        self.assertEqual(decision.reason, "version_6_compact_policy")
        self.assertEqual(decision.policy["policy_mode"], "production")

    def test_version6_staging_fallback_is_distinct_from_production(self) -> None:
        old_allowed = os.environ.get("STAGING_ALLOWED_MODELS")
        old_model = os.environ.get("STAGING_INFERENCE_MODEL")
        try:
            os.environ["STAGING_ALLOWED_MODELS"] = "minimax-m3:cloud,gemma4:31b-cloud"
            os.environ["STAGING_INFERENCE_MODEL"] = "minimax-m3:cloud"
            decision = route_task(
                task_family="sentiment",
                jurisdiction="SENTIMENT_CLASSIFICATION",
                provider_override=VERSION_6_STAGING_PROVIDER,
                allowed_models=[],
            )
        finally:
            if old_allowed is None:
                os.environ.pop("STAGING_ALLOWED_MODELS", None)
            else:
                os.environ["STAGING_ALLOWED_MODELS"] = old_allowed
            if old_model is None:
                os.environ.pop("STAGING_INFERENCE_MODEL", None)
            else:
                os.environ["STAGING_INFERENCE_MODEL"] = old_model

        self.assertEqual(decision.candidate_version, "version_6")
        self.assertEqual(decision.provider, VERSION_6_STAGING_PROVIDER)
        self.assertEqual(decision.selected_path, "policy_authorized")
        self.assertEqual(decision.model, "gemma4:31b")
        self.assertFalse(decision.final_mode_compliant)
        self.assertEqual(decision.policy["policy_mode"], "staging")

    def test_version6_router_loads_compact_policy(self) -> None:
        policy = load_version6_policy(VERSION_6_PRODUCTION_PROVIDER)

        self.assertEqual(policy["schema"], "amd_hackathon.version6.routing_policy.v1")
        self.assertEqual(policy["policy_mode"], "production")
        self.assertEqual(policy["fallback_routes"]["default"]["selected_provider"], "fireworks")

    def test_version6_policy_selects_known_category_model(self) -> None:
        old_allowed = os.environ.get("STAGING_ALLOWED_MODELS")
        try:
            os.environ["STAGING_ALLOWED_MODELS"] = "gpt-oss:20b-cloud,minimax-m3:cloud"
            decision = route_task(
                task_family="math_reasoning",
                jurisdiction="MATH_LIGHT",
                provider_override=VERSION_6_STAGING_PROVIDER,
                allowed_models=[],
            )
        finally:
            if old_allowed is None:
                os.environ.pop("STAGING_ALLOWED_MODELS", None)
            else:
                os.environ["STAGING_ALLOWED_MODELS"] = old_allowed

        self.assertEqual(decision.provider, VERSION_6_STAGING_PROVIDER)
        self.assertEqual(decision.model, "gpt-oss:20b")
        self.assertEqual(decision.selected_path, "policy_authorized")

    def test_version6_policy_falls_back_when_route_is_not_authorized(self) -> None:
        decision = route_task(
            task_family="code_generation",
            jurisdiction="CODE_GENERATION_SMALL",
            provider_override=VERSION_6_PRODUCTION_PROVIDER,
            allowed_models=["accounts/fireworks/models/minimax-m3"],
        )

        self.assertEqual(decision.provider, "fireworks")
        self.assertEqual(decision.model, "accounts/fireworks/models/minimax-m3")
        self.assertEqual(decision.selected_path, "policy_fallback")

    def test_version6_policy_details_do_not_leak_to_results_json(self) -> None:
        policy = {
            "allowed_model_source": "test",
            "category_routes": {
                "SENTIMENT_CLASSIFICATION": {
                    "authorization_status": "authorized",
                    "fallback_policy": "default",
                    "required_gates_passed": True,
                    "runner_up_model": "mock-runner-up",
                    "runner_up_provider": "mock",
                    "selected_model": "mock-policy-model",
                    "selected_provider": "mock",
                }
            },
            "failed_or_denied_routes": {},
            "fallback_routes": {
                "default": {
                    "authorization_status": "fallback",
                    "fallback_policy": "default",
                    "required_gates_passed": True,
                    "runner_up_model": "mock-model",
                    "runner_up_provider": "mock",
                    "selected_model": "mock-model",
                    "selected_provider": "mock",
                }
            },
            "generated_at": "2026-07-11T00:00:00Z",
            "official_fireworks_token_score_status": "NOT_MEASURED_TEST",
            "policy_id": "test-policy",
            "policy_mode": "staging",
            "provider_boundary": "test_mock_only",
            "schema": "amd_hackathon.version6.routing_policy.v1",
            "source_calibration_artifact_hash": "sha256:test",
            "threshold_config_hash": "sha256:test",
            "work_scope_routes": {},
        }
        env_keys = ["VERSION6_STAGING_POLICY_PATH", "AMD_POLICY_TEST_ALLOW_MOCK"]
        old_values = {key: os.environ.get(key) for key in env_keys}
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                policy_path = root / "policy.json"
                input_path = root / "input" / "tasks.json"
                output_path = root / "output" / "results.json"
                input_path.parent.mkdir()
                policy_path.write_text(json.dumps(policy), encoding="utf-8")
                input_path.write_text(
                    json.dumps([{"task_id": "sentiment-1", "prompt": "Classify sentiment: fine"}]),
                    encoding="utf-8",
                )
                os.environ["VERSION6_STAGING_POLICY_PATH"] = str(policy_path)
                os.environ["AMD_POLICY_TEST_ALLOW_MOCK"] = "1"

                payload = run_tasks_file(
                    input_path=input_path,
                    output_path=output_path,
                    provider_override=VERSION_6_STAGING_PROVIDER,
                )
                public_results = json.loads(output_path.read_text(encoding="utf-8"))
        finally:
            for key, value in old_values.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        self.assertEqual(set(public_results[0]), {"task_id", "answer"})
        self.assertNotIn("policy", json.dumps(public_results))
        self.assertNotIn("mock-policy-model", json.dumps(public_results))
        self.assertEqual(payload["audit_records"][0]["routing_policy"]["policy_id"], "test-policy")

    def test_version6_direct_ollama_records_zero_fireworks_tokens(self) -> None:
        decision = route_task(
            task_family="sentiment",
            jurisdiction="SENTIMENT_CLASSIFICATION",
            provider_override=VERSION_6_LOCAL_PROVIDER,
            allowed_models=[],
        )

        self.assertEqual(decision.candidate_version, "version_6")
        self.assertEqual(decision.provider, VERSION_6_LOCAL_PROVIDER)
        self.assertEqual(decision.model, "nemotron-3-nano:4b")
        self.assertTrue(decision.final_mode_compliant)

    def test_version6_staging_requires_ollama_cloud_guard_environment(self) -> None:
        old_fallback = os.environ.pop("VERSION6_REMOTE_FALLBACK", None)
        old_provider = os.environ.pop("STAGING_REMOTE_PROVIDER", None)
        try:
            with self.assertRaisesRegex(RuntimeError, "VERSION6_REMOTE_FALLBACK=staging"):
                provider_for(VERSION_6_STAGING_PROVIDER)
        finally:
            if old_fallback is not None:
                os.environ["VERSION6_REMOTE_FALLBACK"] = old_fallback
            if old_provider is not None:
                os.environ["STAGING_REMOTE_PROVIDER"] = old_provider

    def test_ollama_cloud_model_mapping_requires_explicit_verified_allowed_model(self) -> None:
        self.assertEqual(
            resolve_ollama_cloud_model("gpt-oss:20b-cloud", ["gpt-oss:20b-cloud"]),
            "gpt-oss:20b",
        )
        self.assertEqual(OLLAMA_CLOUD_MODEL_MAPPINGS["minimax-m3:cloud"]["mapping_status"], "VERIFIED_FROM_API_TAGS")
        with self.assertRaisesRegex(RuntimeError, "STAGING_INFERENCE_MODEL"):
            resolve_ollama_cloud_model("", ["minimax-m3:cloud"])
        with self.assertRaisesRegex(RuntimeError, "not present in STAGING_ALLOWED_MODELS"):
            resolve_ollama_cloud_model("gemma4:31b-cloud", ["minimax-m3:cloud"])
        with self.assertRaisesRegex(RuntimeError, "not been verified"):
            resolve_ollama_cloud_model("unknown:cloud", ["unknown:cloud"])

    def test_ollama_cloud_provider_posts_native_chat_request_without_leaking_key(self) -> None:
        env_updates = {
            "VERSION6_REMOTE_FALLBACK": "staging",
            "STAGING_REMOTE_PROVIDER": STAGING_REMOTE_PROVIDER_OLLAMA_CLOUD,
            "OLLAMA_API_KEY": "test-secret-key",
            "OLLAMA_CLOUD_BASE_URL": "https://ollama.test",
            "STAGING_MAX_RETRIES": "0",
        }
        old_values = {key: os.environ.get(key) for key in env_updates}
        captured = {}

        class FakeResponse:
            status = 200

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def read(self) -> bytes:
                return json.dumps(
                    {
                        "message": {"content": "4"},
                        "prompt_eval_count": 7,
                        "eval_count": 1,
                        "total_duration": 10,
                        "load_duration": 2,
                        "eval_duration": 3,
                    }
                ).encode("utf-8")

        def fake_urlopen(request: object, timeout: int) -> FakeResponse:
            captured["full_url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return FakeResponse()

        try:
            for key, value in env_updates.items():
                os.environ[key] = value
            with mock.patch.object(pipeline_module.urllib.request, "urlopen", side_effect=fake_urlopen):
                result = OllamaCloudStagingProvider().complete("Return 4.", "minimax-m3")
        finally:
            for key, value in old_values.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        self.assertEqual(captured["full_url"], "https://ollama.test/api/chat")
        self.assertNotIn("chat/completions", captured["full_url"])
        self.assertEqual(captured["headers"]["Authorization"], "Bearer test-secret-key")
        self.assertEqual(captured["body"]["stream"], False)
        self.assertEqual(captured["body"]["model"], "minimax-m3")
        self.assertEqual(result.text, "4")
        self.assertEqual(result.token_usage["staging_remote_prompt_tokens"], 7)
        self.assertEqual(result.token_usage["staging_remote_completion_tokens"], 1)
        self.assertEqual(result.token_usage["staging_remote_total_tokens"], 8)
        self.assertEqual(result.token_usage["official_fireworks_token_score"], "NOT_MEASURED")
        self.assertNotIn("test-secret-key", json.dumps(result.token_usage))

    def test_production_route_ignores_ollama_cloud_staging_variables(self) -> None:
        env_updates = {
            "VERSION6_REMOTE_FALLBACK": "staging",
            "STAGING_REMOTE_PROVIDER": STAGING_REMOTE_PROVIDER_OLLAMA_CLOUD,
            "OLLAMA_API_KEY": "test-secret-key",
            "STAGING_ALLOWED_MODELS": "minimax-m3:cloud",
            "STAGING_INFERENCE_MODEL": "minimax-m3:cloud",
        }
        old_values = {key: os.environ.get(key) for key in env_updates}
        try:
            for key, value in env_updates.items():
                os.environ[key] = value
            decision = route_task(
                task_family="sentiment",
                jurisdiction="SENTIMENT_CLASSIFICATION",
                provider_override=VERSION_6_PRODUCTION_PROVIDER,
                allowed_models=["accounts/fireworks/models/minimax-m3"],
            )
        finally:
            for key, value in old_values.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        self.assertEqual(decision.provider, "fireworks")
        self.assertEqual(decision.model, "accounts/fireworks/models/minimax-m3")
        self.assertEqual(decision.selected_path, "policy_fallback")

    def test_grading_join_fails_duplicate_missing_and_unknown_results(self) -> None:
        expected = {"one", "two"}
        with self.assertRaisesRegex(ValueError, "duplicate result task_id"):
            index_submission_results(
                [{"task_id": "one", "answer": "a"}, {"task_id": "one", "answer": "b"}],
                expected,
            )
        with self.assertRaisesRegex(ValueError, "missing results"):
            index_submission_results([{"task_id": "one", "answer": "a"}], expected)
        with self.assertRaisesRegex(ValueError, "unknown result task_id"):
            index_submission_results(
                [{"task_id": "one", "answer": "a"}, {"task_id": "other", "answer": "b"}],
                expected,
            )

    def test_canonical_benchmark_path_uses_version2_not_version1(self) -> None:
        self.assertEqual(CANONICAL_BENCHMARK_PATH.name, "version5_local_category_benchmarks_v2.json")
        self.assertNotIn("v1", str(CANONICAL_BENCHMARK_PATH))

    def test_ui_summary_reports_judged_fireworks_tokens_from_evidence_rows(self) -> None:
        summary = summarize_records(
            [
                {
                    "provider": "fireworks",
                    "model": "allowed-model-a",
                    "judged_fireworks_tokens": 13,
                },
                {
                    "provider": "version6-ollama",
                    "model": "nemotron-3-nano:4b",
                    "judged_fireworks_tokens": 0,
                },
            ]
        )
        self.assertEqual(summary["judged_fireworks_tokens"], 13)
        self.assertEqual(summary["providers"], ["fireworks", "version6-ollama"])


if __name__ == "__main__":
    unittest.main()
