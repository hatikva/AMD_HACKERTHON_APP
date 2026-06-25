#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEED_MODELS = {
    "Qwen3-4B-Instruct-2507-GGUF",
    "Phi-4-mini-instruct-GGUF",
    "LFM2.5-1.2B-Instruct-GGUF",
}


def digest_to_blob(models_dir: Path, digest: str) -> Path:
    return models_dir / "blobs" / digest.replace(":", "-")


def is_gguf(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(4) == b"GGUF"
    except OSError:
        return False


def manifest_model_id(manifest: Path, manifests_root: Path) -> str:
    relative = manifest.relative_to(manifests_root)
    parts = relative.parts
    if len(parts) >= 4 and parts[0] == "registry.ollama.ai" and parts[1] == "library":
        return f"{parts[2]}:{parts[3]}"
    return "/".join(parts)


def parameter_estimate_billions(model_id: str) -> float | None:
    normalized = model_id.lower()
    match = re.search(r"(?<![a-z0-9])e?(\d+(?:\.\d+)?)b(?![a-z0-9])", normalized)
    if match:
        return float(match.group(1))
    match = re.search(r"(?<![a-z0-9])(\d+(?:\.\d+)?)m(?![a-z0-9])", normalized)
    if match:
        return float(match.group(1)) / 1000
    return None


def local_model_tier(parameter_billions: float | None, size_bytes: int) -> str:
    if parameter_billions is not None:
        if parameter_billions < 4:
            return "small_under_4b"
        if parameter_billions < 7:
            return "mid_4b_to_under_7b"
        return "large_7b_plus"

    gib = size_bytes / (1024 ** 3)
    if gib < 3:
        return "small_under_4b_size_inferred"
    if gib < 5.5:
        return "mid_4b_to_under_7b_size_inferred"
    return "large_7b_plus_size_inferred"


def discover(models_dir: Path) -> dict[str, object]:
    manifests_root = models_dir / "manifests"
    rows: list[dict[str, object]] = []

    for manifest in sorted(path for path in manifests_root.rglob("*") if path.is_file()):
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            rows.append({
                "manifest": str(manifest),
                "status": "manifest_unreadable",
                "error": str(exc),
            })
            continue

        layers = payload.get("layers") or []
        model_layers = [
            layer for layer in layers
            if layer.get("mediaType") == "application/vnd.ollama.image.model"
        ]
        for layer in model_layers:
            digest = str(layer.get("digest", ""))
            blob = digest_to_blob(models_dir, digest)
            model_id = manifest_model_id(manifest, manifests_root)
            size_bytes = int(layer.get("size") or 0)
            parameter_billions = parameter_estimate_billions(model_id)
            rows.append({
                "ollama_model": model_id,
                "manifest": str(manifest),
                "digest": digest,
                "blob": str(blob),
                "size_bytes": size_bytes,
                "blob_exists": blob.exists(),
                "is_gguf": blob.exists() and is_gguf(blob),
                "seed_model_id_match": model_id in SEED_MODELS,
                "parameter_estimate_billions": parameter_billions,
                "local_model_tier": local_model_tier(parameter_billions, size_bytes),
                "benchmark_status": "available_for_exploratory_local_benchmark" if blob.exists() and is_gguf(blob) else "not_benchmarkable_blob_missing_or_non_gguf",
            })

    gguf_rows = [row for row in rows if row.get("is_gguf")]
    seed_matches = [row for row in gguf_rows if row.get("seed_model_id_match")]
    tier_counts: dict[str, int] = {}
    for row in gguf_rows:
        tier = str(row.get("local_model_tier"))
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "ollama_models_dir": str(models_dir),
        "summary": {
            "manifest_model_layers": len(rows),
            "gguf_model_blobs": len(gguf_rows),
            "seed_model_id_matches": len(seed_matches),
            "local_model_tiers": tier_counts,
        },
        "doctrine": {
            "direct_ollama_tree_import": "not_assumed",
            "allowed_use": "GGUF blobs may be staged for Lemonade extra_models_dir with explicit evidence, tier classification, and benchmark records.",
            "seed_model_rule": "The original prompt models are seed candidates, not required IDs. Audited local GGUF models may enter exploratory benchmarks when documented as such.",
            "promotion_rule": "Promote local models by validation accuracy first, then token use, latency, and cost within comparable task families.",
        },
        "models": rows,
    }


def stage_symlinks(report: dict[str, object], stage_dir: Path) -> list[dict[str, str]]:
    stage_dir.mkdir(parents=True, exist_ok=True)
    staged: list[dict[str, str]] = []
    for row in report["models"]:  # type: ignore[index]
        if not isinstance(row, dict) or not row.get("is_gguf"):
            continue
        model_name = str(row["ollama_model"]).replace("/", "-").replace(":", "-")
        target = stage_dir / f"ollama-{model_name}.gguf"
        source = Path(str(row["blob"]))
        if target.exists() or target.is_symlink():
            target.unlink()
        target.symlink_to(source)
        staged.append({"ollama_model": str(row["ollama_model"]), "staged_path": str(target), "source_blob": str(source)})
    return staged


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Ollama GGUF blobs for possible Lemonade import.")
    parser.add_argument("--models-dir", default=os.environ.get("OLLAMA_MODELS_DIR", str(Path.home() / ".ollama" / "models")))
    parser.add_argument("--stage", action="store_true", help="Create local symlinks to GGUF blobs under .local/ollama-gguf-import.")
    parser.add_argument("--stage-dir", default=str(ROOT / ".local" / "ollama-gguf-import"))
    args = parser.parse_args()

    models_dir = Path(args.models_dir).expanduser()
    if not models_dir.exists():
        raise SystemExit(f"Ollama models directory not found: {models_dir}")

    report = discover(models_dir)
    if args.stage:
        report["staged"] = stage_symlinks(report, Path(args.stage_dir))

    destination = ROOT / "audit" / "ollama-gguf-import-status.json"
    destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    print(f"wrote {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
