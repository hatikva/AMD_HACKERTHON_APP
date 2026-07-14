from __future__ import annotations

import asyncio
import json
import os
import random
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol


LOCAL_MODEL = "nemotron-3-nano:4b"
KIMI_ALIAS = "kimi-k2p7-code"
MINIMAX_ALIAS = "minimax-m3"
DEFAULT_BATCH_DEADLINE_SECONDS = 570.0
CLASSIFIER_MAX_COMPLETION_TOKENS = 32
LOCAL_ANSWER_MAX_COMPLETION_TOKENS = 1000
DEFAULT_FIREWORKS_MAX_CONCURRENCY = 4
SCHEDULER_MODE_STREAMING_REMOTE = "streaming_remote"
SCHEDULER_MODE_POST_CLASSIFICATION_PARALLEL = "post_classification_parallel"
DEFAULT_SCHEDULER_MODE = SCHEDULER_MODE_POST_CLASSIFICATION_PARALLEL
DEFAULT_FIREWORKS_MODEL_RESOURCES = {
    KIMI_ALIAS: "accounts/fireworks/models/kimi-k2p7-code",
    MINIMAX_ALIAS: "accounts/fireworks/models/minimax-m3",
}


class Version7Error(RuntimeError):
    pass


class Category(StrEnum):
    CODE_DEBUGGING = "CODE_DEBUGGING"
    CODE_GENERATION = "CODE_GENERATION"
    FACTUAL_KNOWLEDGE = "FACTUAL_KNOWLEDGE"
    LOGICAL_DEDUCTIVE_REASONING = "LOGICAL_DEDUCTIVE_REASONING"
    MATHEMATICAL_REASONING = "MATHEMATICAL_REASONING"
    NAMED_ENTITY_RECOGNITION = "NAMED_ENTITY_RECOGNITION"
    SENTIMENT_CLASSIFICATION = "SENTIMENT_CLASSIFICATION"
    TEXT_SUMMARISATION = "TEXT_SUMMARISATION"


ANSWER_WRAPPERS: dict[Category, str] = {
    Category.CODE_DEBUGGING: "Answer directly. Provide the corrected code or the specific bug and fix. Do not describe your reasoning process.",
    Category.CODE_GENERATION: "Answer directly with the requested code or concise implementation. Do not describe your reasoning process.",
    Category.FACTUAL_KNOWLEDGE: "Answer directly and completely. Cover every part of the question, but stay concise. Do not describe your reasoning process.",
    Category.LOGICAL_DEDUCTIVE_REASONING: "Answer directly with the final conclusion and only the minimal supporting steps needed. Do not describe your reasoning process.",
    Category.MATHEMATICAL_REASONING: "Answer directly with the final numeric result and concise calculation. Do not describe your reasoning process.",
    Category.NAMED_ENTITY_RECOGNITION: "Extract the requested entities only. Preserve the requested labels or format. Do not add commentary.",
    Category.SENTIMENT_CLASSIFICATION: "Return one sentiment label and one sentence reason only. Do not describe your reasoning process.",
    Category.TEXT_SUMMARISATION: "Follow the requested sentence or bullet count exactly. Do not add commentary or extra sections.",
}


@dataclass(frozen=True)
class RoutePolicy:
    category: Category
    provider: str
    model_alias: str
    max_completion_tokens: int
    scheduling: str
    fallback_provider: str
    fallback_model_alias: str


ROUTING_POLICY: dict[Category, RoutePolicy] = {
    Category.CODE_DEBUGGING: RoutePolicy(Category.CODE_DEBUGGING, "ollama", LOCAL_MODEL, 1000, "deferred_serial_local", "fireworks", KIMI_ALIAS),
    Category.CODE_GENERATION: RoutePolicy(Category.CODE_GENERATION, "fireworks", KIMI_ALIAS, 1000, "bounded_remote", "ollama", LOCAL_MODEL),
    Category.FACTUAL_KNOWLEDGE: RoutePolicy(Category.FACTUAL_KNOWLEDGE, "fireworks", KIMI_ALIAS, 256, "bounded_remote", "fireworks", MINIMAX_ALIAS),
    Category.LOGICAL_DEDUCTIVE_REASONING: RoutePolicy(Category.LOGICAL_DEDUCTIVE_REASONING, "fireworks", KIMI_ALIAS, 256, "bounded_remote", "fireworks", MINIMAX_ALIAS),
    Category.MATHEMATICAL_REASONING: RoutePolicy(Category.MATHEMATICAL_REASONING, "fireworks", KIMI_ALIAS, 400, "bounded_remote", "ollama", LOCAL_MODEL),
    Category.NAMED_ENTITY_RECOGNITION: RoutePolicy(Category.NAMED_ENTITY_RECOGNITION, "ollama", LOCAL_MODEL, 1000, "deferred_serial_local", "fireworks", KIMI_ALIAS),
    Category.SENTIMENT_CLASSIFICATION: RoutePolicy(Category.SENTIMENT_CLASSIFICATION, "fireworks", KIMI_ALIAS, 256, "bounded_remote", "fireworks", MINIMAX_ALIAS),
    Category.TEXT_SUMMARISATION: RoutePolicy(Category.TEXT_SUMMARISATION, "ollama", LOCAL_MODEL, 1000, "deferred_serial_local", "fireworks", KIMI_ALIAS),
}

REMOTE_CATEGORIES = frozenset(category for category, route in ROUTING_POLICY.items() if route.provider == "fireworks")
LOCAL_ANSWER_CATEGORIES = frozenset(category for category, route in ROUTING_POLICY.items() if route.provider == "ollama")
FIREWORKS_WRAPPED_CATEGORIES = frozenset({Category.FACTUAL_KNOWLEDGE}) | LOCAL_ANSWER_CATEGORIES


@dataclass(frozen=True)
class OfficialTask:
    task_id: str
    prompt: str


@dataclass(frozen=True)
class IndexedTask:
    index: int
    task: OfficialTask


@dataclass(frozen=True)
class GenerationResult:
    text: str
    usage: dict[str, Any]
    latency_ms: int
    attempts: int = 1


class ClassifierClient(Protocol):
    async def classify(self, prompt: str, *, retry: bool = False) -> str:
        ...


class AnswerClient(Protocol):
    async def generate(self, prompt: str, *, model: str, max_completion_tokens: int) -> GenerationResult:
        ...


def parse_allowed_models(value: str | None = None) -> list[str]:
    raw = (os.environ.get("ALLOWED_MODELS", "") if value is None else value).strip()
    if not raw:
        return []
    if raw.startswith("["):
        parsed = json.loads(raw)
        return [str(item).strip() for item in parsed if str(item).strip()]
    entries = [item.strip() for item in raw.replace("\n", ",").split(",")]
    return [item for item in entries if item]


def resolve_kimi_model(allowed_models: list[str]) -> str:
    return resolve_allowed_model(allowed_models, KIMI_ALIAS)


def resolve_minimax_model(allowed_models: list[str]) -> str:
    return resolve_allowed_model(allowed_models, MINIMAX_ALIAS)


def resolve_allowed_model(allowed_models: list[str], alias: str) -> str:
    matches = [model for model in allowed_models if model.rstrip("/").split("/")[-1] == alias]
    if not matches:
        raise Version7Error(f"ALLOWED_MODELS does not contain exactly one {alias} resource")
    if len(matches) > 1:
        raise Version7Error(f"ALLOWED_MODELS contains multiple {alias} resources")
    return matches[0]


def parse_category_label(text: str) -> Category:
    label = text.strip()
    if "\n" in label or " " in label or "," in label:
        raise Version7Error(f"invalid classifier label: {label!r}")
    try:
        return Category(label)
    except ValueError as exc:
        raise Version7Error(f"unknown classifier label: {label!r}") from exc


def category_policy(category: Category) -> RoutePolicy:
    return ROUTING_POLICY[category]


def answer_prompt(category: Category, task_prompt: str) -> str:
    return f"{ANSWER_WRAPPERS[category]}\n\nTask:\n{task_prompt}"


def validate_official_tasks(payload: Any) -> list[OfficialTask]:
    if not isinstance(payload, list):
        raise Version7Error("official input must be a top-level JSON array")
    tasks: list[OfficialTask] = []
    seen: set[str] = set()
    for index, row in enumerate(payload):
        if not isinstance(row, dict):
            raise Version7Error(f"task {index + 1} must be an object")
        task_id = row.get("task_id")
        prompt = row.get("prompt")
        if not isinstance(task_id, str) or not task_id.strip():
            raise Version7Error(f"task {index + 1} has invalid task_id")
        if not isinstance(prompt, str) or not prompt.strip():
            raise Version7Error(f"task {task_id} has invalid prompt")
        if task_id in seen:
            raise Version7Error(f"duplicate task_id: {task_id}")
        seen.add(task_id)
        tasks.append(OfficialTask(task_id=task_id, prompt=prompt))
    return tasks


def load_official_tasks(path: Path) -> list[OfficialTask]:
    with path.open("r", encoding="utf-8") as handle:
        return validate_official_tasks(json.load(handle))


def project_official_results(tasks: list[OfficialTask], answers: list[str]) -> list[dict[str, str]]:
    if len(tasks) != len(answers):
        raise Version7Error("answer count does not match task count")
    return [{"task_id": task.task_id, "answer": answers[index]} for index, task in enumerate(tasks)]


def remove_stale_output(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    with tmp_path.open("w", encoding="utf-8") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)
    try:
        directory = os.open(str(path.parent), os.O_DIRECTORY)
    except OSError:
        return
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


class AuditWriter:
    def __init__(self, path: Path) -> None:
        self.path = path

    def write(self, record: dict[str, Any]) -> None:
        safe = {key: value for key, value in record.items() if "key" not in key.lower() and "authorization" not in key.lower()}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(safe, sort_keys=True, ensure_ascii=False) + "\n")
        except OSError:
            return


class Deadline:
    def __init__(self, seconds: float) -> None:
        self.started = time.monotonic()
        self.expires = self.started + seconds

    def remaining(self) -> float:
        return self.expires - time.monotonic()

    def require_time(self) -> None:
        if self.remaining() <= 0:
            raise Version7Error("Version 7 batch deadline exceeded")


def classifier_prompt(task_prompt: str, *, retry: bool = False) -> str:
    categories = "\n".join(category.value for category in Category)
    prefix = (
        "Classify the task into exactly one canonical category. "
        "Return only the category identifier, with no commentary.\n\n"
    )
    if retry:
        prefix = "Return exactly one label from the list. No punctuation. No explanation.\n\n"
    return f"{prefix}Categories:\n{categories}\n\nTask:\n{task_prompt}"


class OllamaChatClient:
    def __init__(self, base_url: str | None = None, timeout_seconds: float | None = None) -> None:
        self.base_url = (base_url or os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")).rstrip("/")
        self.timeout_seconds = timeout_seconds or float(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "300"))

    async def classify(self, prompt: str, *, retry: bool = False) -> str:
        return await asyncio.to_thread(self._classify_sync, prompt, retry)

    async def generate(self, prompt: str, *, model: str, max_completion_tokens: int) -> GenerationResult:
        return await asyncio.to_thread(self._generate_sync, prompt, model, max_completion_tokens)

    def _generate_sync(self, prompt: str, model: str, max_completion_tokens: int) -> GenerationResult:
        start = time.perf_counter()
        body = json.dumps(
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": max_completion_tokens,
                "stream": False,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        text = extract_openai_text(payload)
        return GenerationResult(text=text, usage=dict(payload.get("usage") or {}), latency_ms=int((time.perf_counter() - start) * 1000))

    def _classify_sync(self, prompt: str, retry: bool) -> str:
        classify_url = self.base_url.removesuffix("/v1") + "/api/generate"
        body = json.dumps(
            {
                "model": LOCAL_MODEL,
                "prompt": classifier_prompt(prompt, retry=retry) + "\nLabel:",
                "stream": False,
                "think": False,
                "options": {
                    "temperature": 0,
                    "num_predict": CLASSIFIER_MAX_COMPLETION_TOKENS,
                    "stop": ["\n", "<|im_end|>", "</s>"],
                },
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            classify_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return str(payload.get("response") or "")

    async def healthcheck(self) -> None:
        await asyncio.to_thread(self._healthcheck_sync)

    def _healthcheck_sync(self) -> None:
        url = self.base_url.removesuffix("/v1") + "/api/tags"
        with urllib.request.urlopen(url, timeout=5) as response:
            json.loads(response.read().decode("utf-8"))


class FireworksClient:
    def __init__(self, base_url: str, api_key: str, deadline: Deadline, timeout_seconds: float | None = None) -> None:
        if not base_url.strip():
            raise Version7Error("FIREWORKS_BASE_URL is required")
        if not api_key.strip():
            raise Version7Error("FIREWORKS_API_KEY is required")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.deadline = deadline
        self.timeout_seconds = timeout_seconds or float(os.environ.get("FIREWORKS_TIMEOUT_SECONDS", "120"))

    async def generate(self, prompt: str, *, model: str, max_completion_tokens: int) -> GenerationResult:
        return await asyncio.to_thread(self._generate_sync, prompt, model, max_completion_tokens)

    def _generate_sync(self, prompt: str, model: str, max_completion_tokens: int) -> GenerationResult:
        attempts = 0
        start = time.perf_counter()
        last_error: Exception | None = None
        while attempts < 3:
            self.deadline.require_time()
            attempts += 1
            try:
                payload = self._post(prompt, model, max_completion_tokens)
                text = extract_openai_text(payload)
                return GenerationResult(
                    text=text,
                    usage=dict(payload.get("usage") or {}),
                    latency_ms=int((time.perf_counter() - start) * 1000),
                    attempts=attempts,
                )
            except Exception as exc:
                last_error = exc
                if attempts >= 3 or not is_transient_fireworks_error(exc):
                    raise
                delay = min(0.5 * (2 ** (attempts - 1)) + random.uniform(0, 0.2), max(0.0, self.deadline.remaining() - 1.0))
                if delay <= 0:
                    raise Version7Error("deadline exhausted during Fireworks retry") from exc
                time.sleep(delay)
        raise Version7Error(f"Fireworks request failed: {last_error}")

    def _post(self, prompt: str, model: str, max_completion_tokens: int) -> dict[str, Any]:
        timeout = max(1.0, min(self.timeout_seconds, self.deadline.remaining()))
        body = json.dumps(
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": max_completion_tokens,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))


class UnavailableFireworksClient:
    async def generate(self, prompt: str, *, model: str, max_completion_tokens: int) -> GenerationResult:
        raise Version7Error("Fireworks is unavailable because FIREWORKS_BASE_URL or FIREWORKS_API_KEY is not set")


def extract_openai_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    choice = choices[0]
    if not isinstance(choice, dict):
        return ""
    message = choice.get("message") or {}
    text = message.get("content") if isinstance(message, dict) else None
    if text in {None, ""} and isinstance(message, dict):
        text = message.get("reasoning") or message.get("thinking")
    if text is None:
        text = choice.get("text") or ""
    if isinstance(text, list):
        return "".join(str(part.get("text", part)) if isinstance(part, dict) else str(part) for part in text)
    return str(text)


def is_transient_fireworks_error(exc: Exception) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in {408, 429} or 500 <= exc.code <= 599
    if isinstance(exc, (urllib.error.URLError, TimeoutError, TimeoutError)):
        return True
    return False


async def classify_with_retry(
    client: ClassifierClient,
    fallback_client: AnswerClient,
    task: IndexedTask,
    audit: AuditWriter,
    *,
    local_lock: asyncio.Lock,
    classifier_fallback_model: str | None,
) -> Category:
    for attempt in (1, 2):
        async with local_lock:
            raw = await client.classify(task.task.prompt, retry=attempt == 2)
        try:
            category = parse_category_label(raw)
            audit.write({"event": "classified", "task_id": task.task.task_id, "index": task.index, "category": category.value, "retries": attempt - 1})
            return category
        except Version7Error as exc:
            audit.write({"event": "classification_invalid", "task_id": task.task.task_id, "index": task.index, "attempt": attempt, "failure": str(exc)})
    if classifier_fallback_model is None:
        raise Version7Error(f"classification failed for task {task.task.task_id}")
    result = await fallback_client.generate(
        classifier_prompt(task.task.prompt, retry=True) + "\nLabel:",
        model=classifier_fallback_model,
        max_completion_tokens=CLASSIFIER_MAX_COMPLETION_TOKENS,
    )
    try:
        category = parse_category_label(result.text)
        audit.write(
            {
                "event": "classified",
                "task_id": task.task.task_id,
                "index": task.index,
                "category": category.value,
                "retries": 2,
                "classifier_fallback": "fireworks",
                "classifier_fallback_model": classifier_fallback_model,
            }
        )
        return category
    except Version7Error as exc:
        audit.write({"event": "classification_invalid", "task_id": task.task.task_id, "index": task.index, "attempt": 3, "failure": str(exc)})
        raise Version7Error(f"classification failed for task {task.task.task_id}") from exc


async def generate_local_with_retry(client: AnswerClient, task: IndexedTask, audit: AuditWriter, *, max_completion_tokens: int = LOCAL_ANSWER_MAX_COMPLETION_TOKENS) -> GenerationResult:
    last_error: Exception | None = None
    for attempt in (1, 2):
        start = time.perf_counter()
        try:
            result = await client.generate(task.task.prompt, model=LOCAL_MODEL, max_completion_tokens=max_completion_tokens)
            if result.text.strip():
                audit.write({"event": "local_answered", "task_id": task.task.task_id, "index": task.index, "latency_ms": result.latency_ms, "attempts": attempt})
                return result
            last_error = Version7Error("empty local answer")
        except Exception as exc:
            last_error = exc
            healthcheck = getattr(client, "healthcheck", None)
            if callable(healthcheck):
                await healthcheck()
        audit.write({"event": "local_retry", "task_id": task.task.task_id, "index": task.index, "attempt": attempt, "latency_ms": int((time.perf_counter() - start) * 1000)})
    raise Version7Error(f"local generation failed for task {task.task.task_id}: {last_error}")


async def run_scheduler(
    tasks: list[OfficialTask],
    *,
    classifier: ClassifierClient,
    local_client: AnswerClient,
    fireworks_client: AnswerClient,
    fireworks_models: dict[str, str],
    audit: AuditWriter,
    deadline: Deadline,
    fireworks_max_concurrency: int = DEFAULT_FIREWORKS_MAX_CONCURRENCY,
    scheduler_mode: str | None = None,
) -> list[str]:
    answers: list[str | None] = [None] * len(tasks)
    local_queue: list[tuple[IndexedTask, RoutePolicy]] = []
    routed_tasks: list[tuple[IndexedTask, RoutePolicy]] = []
    remote_sem = asyncio.Semaphore(max(1, fireworks_max_concurrency))
    local_lock = asyncio.Lock()
    remote_tasks: list[asyncio.Task[None]] = []
    selected_mode = scheduler_mode or os.environ.get("VERSION7_SCHEDULER_MODE", DEFAULT_SCHEDULER_MODE)
    if selected_mode not in {SCHEDULER_MODE_STREAMING_REMOTE, SCHEDULER_MODE_POST_CLASSIFICATION_PARALLEL}:
        raise Version7Error(f"unsupported Version 7 scheduler mode: {selected_mode}")

    def resolve_fireworks_alias(alias: str) -> str:
        try:
            return fireworks_models[alias]
        except KeyError as exc:
            raise Version7Error(f"missing resolved Fireworks model for {alias}") from exc

    async def local_answer(indexed: IndexedTask, route: RoutePolicy, *, fallback: bool = False) -> GenerationResult:
        wrapped = IndexedTask(index=indexed.index, task=OfficialTask(task_id=indexed.task.task_id, prompt=answer_prompt(route.category, indexed.task.prompt)))
        async with local_lock:
            result = await generate_local_with_retry(local_client, wrapped, audit, max_completion_tokens=route.max_completion_tokens)
        if fallback:
            audit.write({"event": "fallback_answered", "task_id": indexed.task.task_id, "index": indexed.index, "provider": "ollama", "model": LOCAL_MODEL})
        return result

    async def fireworks_answer(indexed: IndexedTask, route: RoutePolicy, model_alias: str, *, fallback: bool = False) -> GenerationResult:
        model = resolve_fireworks_alias(model_alias)
        prompt = answer_prompt(route.category, indexed.task.prompt) if route.category in FIREWORKS_WRAPPED_CATEGORIES else indexed.task.prompt
        result = await fireworks_client.generate(prompt, model=model, max_completion_tokens=route.max_completion_tokens)
        audit.write(
            {
                "event": "fallback_answered" if fallback else "remote_answered",
                "task_id": indexed.task.task_id,
                "index": indexed.index,
                "category": route.category.value,
                "provider": "fireworks",
                "resolved_model_resource": model,
                "max_completion_tokens": route.max_completion_tokens,
                "latency_ms": result.latency_ms,
                "attempts": result.attempts,
                "usage": result.usage,
            }
        )
        return result

    async def answer_with_fallback(indexed: IndexedTask, route: RoutePolicy) -> GenerationResult:
        try:
            if route.provider == "fireworks":
                return await fireworks_answer(indexed, route, route.model_alias)
            return await local_answer(indexed, route)
        except Exception as exc:
            audit.write(
                {
                    "event": "primary_failed",
                    "task_id": indexed.task.task_id,
                    "index": indexed.index,
                    "category": route.category.value,
                    "provider": route.provider,
                    "model_alias": route.model_alias,
                    "failure": str(exc),
                }
            )
            try:
                if route.fallback_provider == "fireworks":
                    return await fireworks_answer(indexed, route, route.fallback_model_alias, fallback=True)
                if route.fallback_provider == "ollama":
                    return await local_answer(indexed, route, fallback=True)
            except Exception as fallback_exc:
                audit.write(
                    {
                        "event": "fallback_failed",
                        "task_id": indexed.task.task_id,
                        "index": indexed.index,
                        "category": route.category.value,
                        "provider": route.fallback_provider,
                        "model_alias": route.fallback_model_alias,
                        "failure": str(fallback_exc),
                    }
                )
                return await local_answer(indexed, route, fallback=True)
            raise Version7Error(f"unsupported fallback provider: {route.fallback_provider}")

    async def remote_answer(indexed: IndexedTask, route: RoutePolicy) -> None:
        async with remote_sem:
            deadline.require_time()
            started = time.perf_counter()
            try:
                result = await answer_with_fallback(indexed, route)
                answers[indexed.index] = result.text
            except Exception as exc:
                audit.write({"event": "remote_failed", "task_id": indexed.task.task_id, "index": indexed.index, "failure": str(exc), "latency_ms": int((time.perf_counter() - started) * 1000)})
                raise

    async def local_answer_task(indexed: IndexedTask, route: RoutePolicy) -> None:
        deadline.require_time()
        try:
            result = await answer_with_fallback(indexed, route)
            answers[indexed.index] = result.text
        except Exception as exc:
            audit.write({"event": "local_failed", "task_id": indexed.task.task_id, "index": indexed.index, "failure": str(exc), "category": route.category.value})
            raise

    for index, task in enumerate(tasks):
        deadline.require_time()
        indexed = IndexedTask(index=index, task=task)
        category = await classify_with_retry(
            classifier,
            fireworks_client,
            indexed,
            audit,
            local_lock=local_lock,
            classifier_fallback_model=fireworks_models.get(KIMI_ALIAS),
        )
        route = category_policy(category)
        audit.write({"event": "routed", "task_id": task.task_id, "index": index, "category": category.value, "provider": route.provider, "max_completion_tokens": route.max_completion_tokens})
        if selected_mode == SCHEDULER_MODE_POST_CLASSIFICATION_PARALLEL:
            routed_tasks.append((indexed, route))
        elif route.provider == "fireworks":
            remote_tasks.append(asyncio.create_task(remote_answer(indexed, route)))
        else:
            local_queue.append((indexed, route))

    if selected_mode == SCHEDULER_MODE_POST_CLASSIFICATION_PARALLEL:
        answer_tasks = [
            asyncio.create_task(remote_answer(indexed, route) if route.provider == "fireworks" else local_answer_task(indexed, route))
            for indexed, route in routed_tasks
        ]
        if answer_tasks:
            await asyncio.gather(*answer_tasks)
    else:
        for indexed, route in local_queue:
            await local_answer_task(indexed, route)

    if remote_tasks:
        await asyncio.gather(*remote_tasks)

    if any(answer is None for answer in answers):
        raise Version7Error("one or more tasks did not produce an answer")
    return [str(answer) for answer in answers]


async def run_batch_async(
    *,
    input_path: Path = Path("/input/tasks.json"),
    output_path: Path = Path("/output/results.json"),
    audit_path: Path = Path("/output/audit/version7-run.jsonl"),
    classifier: ClassifierClient | None = None,
    local_client: AnswerClient | None = None,
    fireworks_client: AnswerClient | None = None,
) -> dict[str, Any]:
    remove_stale_output(output_path)
    started = time.perf_counter()
    deadline = Deadline(float(os.environ.get("VERSION7_BATCH_DEADLINE_SECONDS", str(DEFAULT_BATCH_DEADLINE_SECONDS))))
    audit = AuditWriter(audit_path)
    tasks = load_official_tasks(input_path)
    allowed_models = parse_allowed_models()
    if allowed_models:
        resolved_kimi = resolve_kimi_model(allowed_models)
        resolved_minimax = resolve_minimax_model(allowed_models)
        fireworks_models = {KIMI_ALIAS: resolved_kimi, MINIMAX_ALIAS: resolved_minimax}
    else:
        fireworks_models = DEFAULT_FIREWORKS_MODEL_RESOURCES
    local = local_client or OllamaChatClient()
    classifier_client = classifier or local
    fireworks_base_url = os.environ.get("FIREWORKS_BASE_URL", "")
    fireworks_api_key = os.environ.get("FIREWORKS_API_KEY", "")
    fireworks = fireworks_client or (
        FireworksClient(fireworks_base_url, fireworks_api_key, deadline)
        if fireworks_base_url.strip() and fireworks_api_key.strip()
        else UnavailableFireworksClient()
    )
    answers = await run_scheduler(
        tasks,
        classifier=classifier_client,
        local_client=local,
        fireworks_client=fireworks,
        fireworks_models=fireworks_models,
        audit=audit,
        deadline=deadline,
        fireworks_max_concurrency=int(os.environ.get("FIREWORKS_MAX_CONCURRENCY", str(DEFAULT_FIREWORKS_MAX_CONCURRENCY))),
        scheduler_mode=os.environ.get("VERSION7_SCHEDULER_MODE", DEFAULT_SCHEDULER_MODE),
    )
    public_results = project_official_results(tasks, answers)
    atomic_write_json(output_path, public_results)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    audit.write({"event": "batch_completed", "task_count": len(tasks), "elapsed_ms": elapsed_ms})
    return {"task_count": len(tasks), "result_path": str(output_path), "elapsed_ms": elapsed_ms}


def run_batch(**kwargs: Any) -> dict[str, Any]:
    return asyncio.run(run_batch_async(**kwargs))
