from __future__ import annotations

import asyncio
import json
import tempfile
import time
import unittest
import urllib.error
from pathlib import Path

from amd_hackathon_app.version7 import (
    Category,
    Deadline,
    GenerationResult,
    LOCAL_ANSWER_CATEGORIES,
    REMOTE_CATEGORIES,
    ROUTING_POLICY,
    Version7Error,
    atomic_write_json,
    category_policy,
    is_transient_fireworks_error,
    parse_category_label,
    parse_allowed_models,
    project_official_results,
    resolve_kimi_model,
    resolve_minimax_model,
    run_batch_async,
    run_scheduler,
    validate_official_tasks,
    extract_openai_text,
)


FIREWORKS_MODELS = {
    "kimi-k2p7-code": "accounts/fireworks/models/kimi-k2p7-code",
    "minimax-m3": "accounts/fireworks/models/minimax-m3",
}


class AuditProbe:
    def __init__(self) -> None:
        self.records: list[dict] = []

    def write(self, record: dict) -> None:
        self.records.append(record)


class FakeClassifier:
    def __init__(self, labels: list[str], events: list[str] | None = None) -> None:
        self.labels = labels
        self.events = events if events is not None else []
        self.calls = 0

    async def classify(self, prompt: str, *, retry: bool = False) -> str:
        self.events.append(f"classify_start:{self.calls}:{retry}")
        await asyncio.sleep(0.01)
        label = self.labels[self.calls]
        self.calls += 1
        self.events.append(f"classify_end:{self.calls}")
        return label


class FakeAnswerClient:
    def __init__(
        self,
        name: str,
        events: list[str],
        delays: dict[str, float] | None = None,
        fail_once_empty: bool = False,
        fail_models: set[str] | None = None,
    ) -> None:
        self.name = name
        self.events = events
        self.delays = delays or {}
        self.calls: list[tuple[str, str, int]] = []
        self.active = 0
        self.max_active = 0
        self.fail_once_empty = fail_once_empty
        self.fail_models = fail_models or set()

    async def generate(self, prompt: str, *, model: str, max_completion_tokens: int) -> GenerationResult:
        self.calls.append((prompt, model, max_completion_tokens))
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        self.events.append(f"{self.name}_start:{prompt}")
        await asyncio.sleep(self.delays.get(prompt, 0.01))
        self.active -= 1
        self.events.append(f"{self.name}_end:{prompt}")
        if self.fail_once_empty:
            self.fail_once_empty = False
            return GenerationResult("", {}, 1)
        if model in self.fail_models:
            raise RuntimeError(f"forced failure for {model}")
        if "Categories:" in prompt and "Label:" in prompt:
            return GenerationResult("FACTUAL_KNOWLEDGE", {"completion_tokens": 1}, 1)
        return GenerationResult(f"{self.name}:{prompt}", {"completion_tokens": 1}, 1)

    async def healthcheck(self) -> None:
        self.events.append(f"{self.name}_healthcheck")


class Version7PolicyTests(unittest.TestCase):
    def test_input_validation_and_duplicate_rejection(self) -> None:
        tasks = validate_official_tasks([{"task_id": "one", "prompt": "Prompt"}])
        self.assertEqual(tasks[0].task_id, "one")
        with self.assertRaises(Version7Error):
            validate_official_tasks({"tasks": []})
        with self.assertRaises(Version7Error):
            validate_official_tasks([{"task_id": "one", "prompt": "A"}, {"task_id": "one", "prompt": "B"}])

    def test_category_parser_is_strict(self) -> None:
        self.assertEqual(parse_category_label("CODE_GENERATION"), Category.CODE_GENERATION)
        for value in ["CODE_GENERATION\nFACTUAL_KNOWLEDGE", "CODE GENERATION", "UNKNOWN", "CODE_GENERATION."]:
            with self.assertRaises(Version7Error):
                parse_category_label(value)

    def test_kimi_model_resolution(self) -> None:
        self.assertEqual(
            resolve_kimi_model(["accounts/fireworks/models/kimi-k2p7-code"]),
            "accounts/fireworks/models/kimi-k2p7-code",
        )
        self.assertEqual(
            resolve_minimax_model(["accounts/fireworks/models/minimax-m3"]),
            "accounts/fireworks/models/minimax-m3",
        )
        self.assertEqual(parse_allowed_models(" a, ,b "), ["a", "b"])
        with self.assertRaises(Version7Error):
            resolve_kimi_model(["accounts/fireworks/models/minimax-m3"])
        with self.assertRaises(Version7Error):
            resolve_kimi_model(["a/kimi-k2p7-code", "b/kimi-k2p7-code"])

    def test_exact_policy_mapping_and_fallbacks(self) -> None:
        self.assertEqual(len(ROUTING_POLICY), 8)
        self.assertEqual(category_policy(Category.CODE_GENERATION).provider, "fireworks")
        self.assertEqual(category_policy(Category.CODE_GENERATION).max_completion_tokens, 1000)
        self.assertEqual(category_policy(Category.MATHEMATICAL_REASONING).max_completion_tokens, 400)
        self.assertEqual(category_policy(Category.FACTUAL_KNOWLEDGE).max_completion_tokens, 64)
        self.assertEqual(category_policy(Category.FACTUAL_KNOWLEDGE).fallback_model_alias, "minimax-m3")
        self.assertEqual(category_policy(Category.SENTIMENT_CLASSIFICATION).fallback_model_alias, "minimax-m3")
        self.assertEqual(category_policy(Category.CODE_DEBUGGING).fallback_model_alias, "kimi-k2p7-code")
        self.assertEqual(category_policy(Category.CODE_GENERATION).fallback_model_alias, "nemotron-3-nano:4b")
        self.assertEqual(
            LOCAL_ANSWER_CATEGORIES,
            {Category.CODE_DEBUGGING, Category.NAMED_ENTITY_RECOGNITION, Category.TEXT_SUMMARISATION},
        )
        self.assertEqual(
            REMOTE_CATEGORIES,
            {
                Category.CODE_GENERATION,
                Category.FACTUAL_KNOWLEDGE,
                Category.LOGICAL_DEDUCTIVE_REASONING,
                Category.MATHEMATICAL_REASONING,
                Category.SENTIMENT_CLASSIFICATION,
            },
        )
        self.assertIn("minimax", json.dumps([route.__dict__ for route in ROUTING_POLICY.values()]).lower())

    def test_official_projection_and_atomic_write(self) -> None:
        tasks = validate_official_tasks([{"task_id": "a", "prompt": "A"}])
        rows = project_official_results(tasks, ["answer"])
        self.assertEqual(rows, [{"task_id": "a", "answer": "answer"}])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "output" / "results.json"
            atomic_write_json(path, rows)
            self.assertEqual(set(json.loads(path.read_text())[0]), {"task_id", "answer"})

    def test_deadline_and_retry_rule_helpers(self) -> None:
        deadline = Deadline(0.001)
        time.sleep(0.01)
        with self.assertRaises(Version7Error):
            deadline.require_time()
        self.assertTrue(is_transient_fireworks_error(urllib.error.HTTPError("u", 429, "rate", {}, None)))
        self.assertTrue(is_transient_fireworks_error(urllib.error.HTTPError("u", 503, "bad", {}, None)))
        self.assertFalse(is_transient_fireworks_error(urllib.error.HTTPError("u", 400, "bad", {}, None)))

    def test_extracts_reasoning_only_ollama_compatible_response(self) -> None:
        payload = {"choices": [{"message": {"content": "", "reasoning": "CODE_GENERATION"}}]}
        self.assertEqual(extract_openai_text(payload), "CODE_GENERATION")


class Version7SchedulerTests(unittest.TestCase):
    def test_scheduler_barrier_remote_overlap_local_serial_and_order(self) -> None:
        events: list[str] = []
        labels = [
            "CODE_GENERATION",
            "CODE_DEBUGGING",
            "FACTUAL_KNOWLEDGE",
            "NAMED_ENTITY_RECOGNITION",
            "TEXT_SUMMARISATION",
            "SENTIMENT_CLASSIFICATION",
        ]
        tasks = validate_official_tasks([{"task_id": f"t{i}", "prompt": f"p{i}"} for i in range(len(labels))])
        classifier = FakeClassifier(labels, events)
        local = FakeAnswerClient("local", events)
        remote = FakeAnswerClient("remote", events, delays={"p0": 0.05, "p2": 0.02, "p5": 0.01})
        audit = AuditProbe()

        answers = asyncio.run(
            run_scheduler(
                tasks,
                classifier=classifier,
                local_client=local,
                fireworks_client=remote,
                fireworks_models=FIREWORKS_MODELS,
                audit=audit,
                deadline=Deadline(10),
                fireworks_max_concurrency=2,
            )
        )

        self.assertEqual(answers, [f"remote:p0", "local:p1", "remote:p2", "local:p3", "local:p4", "remote:p5"])
        self.assertLess(events.index("remote_start:p0"), events.index("classify_end:2"))
        self.assertLess(events.index("classify_end:6"), events.index("local_start:p1"))
        self.assertEqual([call[0] for call in local.calls], ["p1", "p3", "p4"])
        self.assertNotIn("p0", [call[0] for call in local.calls])
        self.assertEqual(remote.calls[0][2], 1000)
        self.assertLessEqual(local.max_active, 1)
        self.assertGreaterEqual(remote.max_active, 1)

    def test_classifier_invalid_output_retries_once(self) -> None:
        events: list[str] = []
        tasks = validate_official_tasks([{"task_id": "a", "prompt": "p"}])
        classifier = FakeClassifier(["bad label", "FACTUAL_KNOWLEDGE"], events)
        remote = FakeAnswerClient("remote", events)
        local = FakeAnswerClient("local", events)
        answers = asyncio.run(
            run_scheduler(
                tasks,
                classifier=classifier,
                local_client=local,
                fireworks_client=remote,
                fireworks_models=FIREWORKS_MODELS,
                audit=AuditProbe(),
                deadline=Deadline(10),
            )
        )
        self.assertEqual(answers, ["remote:p"])
        self.assertEqual(classifier.calls, 2)

    def test_classifier_falls_back_to_kimi_on_third_attempt(self) -> None:
        events: list[str] = []
        tasks = validate_official_tasks([{"task_id": "a", "prompt": "p"}])
        classifier = FakeClassifier(["bad label", "still bad"], events)
        remote = FakeAnswerClient("remote", events)
        local = FakeAnswerClient("local", events)

        answers = asyncio.run(
            run_scheduler(
                tasks,
                classifier=classifier,
                local_client=local,
                fireworks_client=remote,
                fireworks_models=FIREWORKS_MODELS,
                audit=AuditProbe(),
                deadline=Deadline(10),
            )
        )

        self.assertEqual(answers, ["remote:p"])
        self.assertEqual(classifier.calls, 2)
        self.assertEqual(remote.calls[0][1], "accounts/fireworks/models/kimi-k2p7-code")
        self.assertIn("Categories:", remote.calls[0][0])

    def test_local_empty_answer_retries_serially(self) -> None:
        events: list[str] = []
        tasks = validate_official_tasks([{"task_id": "a", "prompt": "p"}])
        classifier = FakeClassifier(["CODE_DEBUGGING"], events)
        local = FakeAnswerClient("local", events, fail_once_empty=True)
        remote = FakeAnswerClient("remote", events)
        answers = asyncio.run(
            run_scheduler(
                tasks,
                classifier=classifier,
                local_client=local,
                fireworks_client=remote,
                fireworks_models=FIREWORKS_MODELS,
                audit=AuditProbe(),
                deadline=Deadline(10),
            )
        )
        self.assertEqual(answers, ["local:p"])
        self.assertEqual(len(local.calls), 2)
        self.assertLessEqual(local.max_active, 1)

    def test_kimi_primary_can_fallback_to_minimax(self) -> None:
        events: list[str] = []
        tasks = validate_official_tasks([{"task_id": "a", "prompt": "p"}])
        classifier = FakeClassifier(["FACTUAL_KNOWLEDGE"], events)
        remote = FakeAnswerClient("remote", events, fail_models={"accounts/fireworks/models/kimi-k2p7-code"})
        local = FakeAnswerClient("local", events)

        answers = asyncio.run(
            run_scheduler(
                tasks,
                classifier=classifier,
                local_client=local,
                fireworks_client=remote,
                fireworks_models=FIREWORKS_MODELS,
                audit=AuditProbe(),
                deadline=Deadline(10),
            )
        )

        self.assertEqual(answers, ["remote:p"])
        self.assertEqual([call[1] for call in remote.calls], ["accounts/fireworks/models/kimi-k2p7-code", "accounts/fireworks/models/minimax-m3"])

    def test_local_primary_can_fallback_to_kimi(self) -> None:
        events: list[str] = []
        tasks = validate_official_tasks([{"task_id": "a", "prompt": "p"}])
        classifier = FakeClassifier(["CODE_DEBUGGING"], events)
        local = FakeAnswerClient("local", events, fail_models={"nemotron-3-nano:4b"})
        remote = FakeAnswerClient("remote", events)

        answers = asyncio.run(
            run_scheduler(
                tasks,
                classifier=classifier,
                local_client=local,
                fireworks_client=remote,
                fireworks_models=FIREWORKS_MODELS,
                audit=AuditProbe(),
                deadline=Deadline(10),
            )
        )

        self.assertEqual(answers, ["remote:p"])
        self.assertEqual([call[1] for call in remote.calls], ["accounts/fireworks/models/kimi-k2p7-code"])

    def test_run_batch_keeps_audit_separate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "input" / "tasks.json"
            output_path = root / "output" / "results.json"
            audit_path = root / "output" / "audit" / "version7-run.jsonl"
            input_path.parent.mkdir()
            input_path.write_text(json.dumps([{"task_id": "one", "prompt": "p"}]), encoding="utf-8")
            events: list[str] = []
            old_allowed = __import__("os").environ.get("ALLOWED_MODELS")
            try:
                __import__("os").environ["ALLOWED_MODELS"] = "accounts/fireworks/models/kimi-k2p7-code,accounts/fireworks/models/minimax-m3"
                asyncio.run(
                    run_batch_async(
                        input_path=input_path,
                        output_path=output_path,
                        audit_path=audit_path,
                        classifier=FakeClassifier(["FACTUAL_KNOWLEDGE"], events),
                        local_client=FakeAnswerClient("local", events),
                        fireworks_client=FakeAnswerClient("remote", events),
                    )
                )
            finally:
                if old_allowed is None:
                    __import__("os").environ.pop("ALLOWED_MODELS", None)
                else:
                    __import__("os").environ["ALLOWED_MODELS"] = old_allowed
            rows = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(rows, [{"task_id": "one", "answer": "remote:p"}])
            self.assertTrue(audit_path.exists())
            self.assertNotIn("category", rows[0])


if __name__ == "__main__":
    unittest.main()
