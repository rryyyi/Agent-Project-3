"""Reproducible contract evaluation, not a substitute for a held-out business set."""

import json
import platform
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean

from . import __version__
from .agent import Agent


def load_cases(path: str | Path) -> list[dict]:
    cases = []
    ids = set()
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            if not isinstance(item, dict):
                raise ValueError("case must be an object")
            for field in ("id", "message", "intent", "status"):
                if not isinstance(item.get(field), str) or not item[field]:
                    raise ValueError(f"missing {field}")
            if item["id"] in ids:
                raise ValueError("duplicate ID")
            ids.add(item["id"])
            cases.append(item)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid evaluation line {number}: {exc}") from exc
    return cases


def evaluate(cases: list[dict], agent=None) -> dict:
    if not cases:
        raise ValueError("Evaluation set is empty")
    service = agent or Agent()
    counters = {
        name: {"correct": 0, "total": 0}
        for name in (
            "intent_accuracy",
            "status_accuracy",
            "retrieval_hit_at_3",
            "route_exact_match",
        )
    }
    failures = []
    started = time.perf_counter()
    run_id = str(time.time_ns())
    for case in cases:
        result = service.chat(
            case["message"], "eval-" + run_id + "-" + case.get("session", case["id"])
        )
        checks = {
            "intent_accuracy": result["intent"] == case["intent"],
            "status_accuracy": result["status"] == case["status"],
        }
        if "document_id" in case:
            checks["retrieval_hit_at_3"] = case["document_id"] in [
                hit["document_id"] for hit in result["evidence"][:3]
            ]
        if "route" in case:
            route = result["route"] or {}
            checks["route_exact_match"] = all(route.get(k) == v for k, v in case["route"].items())
        for metric, passed in checks.items():
            counters[metric]["total"] += 1
            counters[metric]["correct"] += int(passed)
        if not all(checks.values()):
            failures.append(
                {
                    "id": case["id"],
                    "failed_metrics": [k for k, v in checks.items() if not v],
                    "actual_intent": result["intent"],
                    "actual_status": result["status"],
                    "actual_route": result["route"],
                    "actual_documents": [h["document_id"] for h in result["evidence"]],
                }
            )
    for metric in counters.values():
        metric["score"] = metric["correct"] / metric["total"] if metric["total"] else None
    return {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "project_version": __version__,
        "python": platform.python_version(),
        "knowledge_version": service.kb.version,
        "samples": len(cases),
        "configuration": {
            "retriever": service.tools.version,
            "llm": bool(service.llm),
            "k": 3,
            "dataset": "synthetic authored regression/demo cases",
        },
        "metrics": counters,
        "failures": failures,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "limitations": [
            "Authored regression set, not held-out enterprise evaluation",
            "Hit@3 is document presence, not recall over all relevant documents",
            "Route exact match compares only the explicit expected fields",
            "No claim to reproduce historical resume metrics",
        ],
    }


def benchmark(iterations: int = 200, concurrency: int = 8) -> dict:
    if iterations < 1 or not 1 <= concurrency <= 64:
        raise ValueError("iterations >= 1 and concurrency between 1 and 64 required")
    service = Agent()
    messages = ["Central去紅磡", "HKU去灣仔", "Octopus payment", "咁去旺角呢"]
    # Warm only stateless tool results; fresh session IDs keep context from changing the workload.
    for message in messages:
        service.chat(message)

    def request(index):
        started = time.perf_counter()
        service.chat(messages[index % len(messages)], f"bench-{index}")
        return (time.perf_counter() - started) * 1000

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        durations = sorted(pool.map(request, range(iterations)))
    elapsed = time.perf_counter() - started

    def percentile(p):
        return round(durations[min(len(durations) - 1, int((len(durations) - 1) * p))], 3)

    return {
        "created_at": datetime.now(UTC).isoformat(),
        "python": platform.python_version(),
        "platform": platform.system(),
        "iterations": iterations,
        "concurrency": concurrency,
        "unit": "ms",
        "mean": round(mean(durations), 3),
        "p50": percentile(0.5),
        "p95": percentile(0.95),
        "p99": percentile(0.99),
        "wall_ms": round(elapsed * 1000, 3),
        "requests_per_second": round(iterations / elapsed, 2),
        "workload": messages,
        "knowledge_version": service.kb.version,
        "limitations": [
            "Warm-cache in-process offline calls; excludes HTTP, network and models",
            "Synthetic 15-station/5-document dataset; not production capacity",
        ],
    }
