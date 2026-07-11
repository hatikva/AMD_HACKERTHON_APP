from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from amd_hackathon_app.analytics import (
    build_version5_analytics,
    ranking_key,
    write_version5_analytics,
)


class AnalyticsTests(unittest.TestCase):
    def test_build_version5_analytics_generates_review_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "version5_authority_analytics.json"
            payload = write_version5_analytics(Path("qualification/results"), output)

            self.assertTrue(output.exists())
            self.assertEqual(payload["schema"], "amd_hackathon.version5_authority_analytics.v1")
            self.assertFalse(payload["authorization_registry_mutated"])
            self.assertEqual(payload["local_jurisdictions_promoted"], [])
            self.assertGreaterEqual(len(payload["source_result_files"]), 3)

    def test_category_ranking_uses_required_tie_breaks(self) -> None:
        rows = [
            {"id": "b", "passed": 5, "judged_fireworks_tokens": 10, "validation_failures": 0, "latency_ms": 10},
            {"id": "a", "passed": 5, "judged_fireworks_tokens": 8, "validation_failures": 1, "latency_ms": 1},
            {"id": "c", "passed": 4, "judged_fireworks_tokens": 0, "validation_failures": 0, "latency_ms": 0},
            {"id": "d", "passed": 5, "judged_fireworks_tokens": 8, "validation_failures": 0, "latency_ms": 3},
        ]

        ranked = sorted(rows, key=ranking_key)

        self.assertEqual([row["id"] for row in ranked], ["d", "a", "b", "c"])

    def test_avoid_lists_include_zero_pass_and_qualification_only_evidence(self) -> None:
        payload = build_version5_analytics(Path("qualification/results"))

        code_generation_avoid = payload["avoid_list_per_category"]["CODE_GENERATION"]
        avoid_names = {row["model"] for row in code_generation_avoid}

        self.assertTrue(any("ollama-demo" in name for name in avoid_names))
        self.assertGreaterEqual(len(code_generation_avoid), 3)

    def test_qualification_only_evidence_is_blocked_from_promotion(self) -> None:
        payload = build_version5_analytics(Path("qualification/results"))

        local_rows = [
            row
            for row in payload["per_model_overall_metrics"]
            if row["provider"] == "ollama-demo"
        ]

        self.assertEqual(len(local_rows), 1)
        self.assertTrue(local_rows[0]["qualification_only"])
        self.assertFalse(local_rows[0]["final_provider_evidence"])

    def test_categorization_evaluation_uses_official_shape_projection(self) -> None:
        payload = build_version5_analytics(Path("qualification/results"))
        report = payload["categorization_evaluation"]

        self.assertEqual(report["input_shape"], "official_task_array_task_id_prompt_only")
        self.assertTrue(report["official_shape_valid"])
        self.assertTrue(report["benchmark_metadata_withheld"])
        self.assertEqual(report["total_tasks"], 40)
        self.assertIn("confusion_matrix", report)
        self.assertIn("per_category", report)


if __name__ == "__main__":
    unittest.main()
