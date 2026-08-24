"""
Fires a sequence of prompts at a running gateway and records cache hit/miss
+ latency per request, so you can measure real cache effectiveness against a
realistic query distribution (some exact repeats, some unique) instead of
uniform random traffic.

Reuses backend/scripts/chaos_test.py's plumbing (_register_project) instead
of building a parallel harness from scratch.


Usage (three terminals):
    cd backend
    uvicorn app.main:app --reload
    uvicorn app.mock_provider.server:app --port 9100 --reload
    python scripts/load_test_cache.py
"""

import argparse
import csv
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from chaos_test import _register_project  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parent / "results"
METRICS_FILE = Path(__file__).resolve().parents[2] / "docs" / "metrics.md"


def _build_query_sequence(requests: int, repeat_ratio: float, pool_size: int) -> list[str]:
    """Zipf-weighted, not uniform random: real repeat traffic isn't "any of
    N queries with equal odds" — a handful of queries get asked a lot, most
    get asked once.
    """
    if requests <= 0:
        return []
    pool_size = max(1, min(pool_size, requests))
    pool = [f"load-test query {i}" for i in range(pool_size)]
    weights = [1.0 / (rank + 1) for rank in range(pool_size)]  # rank 0 is "hottest"

    introduced: list[str] = []
    sequence: list[str] = []
    for i in range(requests):
        remaining_slots = requests - i
        uninitialized = pool_size - len(introduced)
        should_introduce = uninitialized > 0 and (
            len(introduced) == 0
            or remaining_slots <= uninitialized  # last chance to fit the rest of the pool in
            or random.random() > repeat_ratio
        )
        if should_introduce:
            next_query = pool[len(introduced)]
            introduced.append(next_query)
            sequence.append(next_query)
        else:
            sequence.append(random.choices(introduced, weights=weights[: len(introduced)], k=1)[0])

    return sequence


def run_load_test(
    gateway_url: str,
    requests: int,
    repeat_ratio: float,
    pool_size: int,
    model: str,
    interval: float,
    request_timeout: float,
) -> list[dict]:
    print(f"Registering throwaway user/project against {gateway_url} ...")
    token, project_id = _register_project(gateway_url)
    headers = {"Authorization": f"Bearer {token}"}

    queries = _build_query_sequence(requests, repeat_ratio, pool_size)
    if len(queries) != requests:
        raise ValueError(f"_build_query_sequence returned {len(queries)} prompts, expected {requests}")

    rows: list[dict] = []
    # One persistent, keep-alive client for the whole run — a fresh
    # httpx.post() call per request opens (and tears down) a brand-new TCP
    # connection every time, and on Windows that per-connection setup cost
    # (measured at 240-600ms, vs ~2ms reusing a connection) completely
    # swamps the actual cache/DB latency this script exists to measure. See
    # docs/decisions.md.
    with httpx.Client(timeout=request_timeout) as client:
        for i, prompt in enumerate(queries, start=1):
            started = time.monotonic()
            cache_hit = None
            try:
                response = client.post(
                    f"{gateway_url}/api/v1/projects/{project_id}/generate",
                    json={"prompt": prompt, "model": model},
                    headers=headers,
                )
                status_code = response.status_code
                if 200 <= status_code < 300:
                    try:
                        cache_hit = bool(response.json().get("cache_hit", False))
                    except ValueError:
                        cache_hit = None
            except httpx.HTTPError as exc:
                status_code = -1
                print(f"[request {i}] transport error: {exc}")
            latency_ms = int((time.monotonic() - started) * 1000)

            rows.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "request_number": i,
                "prompt": prompt,
                "status_code": status_code,
                "latency_ms": latency_ms,
                "cache_hit": cache_hit,
            })
            print(f"[request {i}] status={status_code} latency_ms={latency_ms} cache_hit={cache_hit}")

            if interval > 0:
                time.sleep(interval)

    return rows


def _write_results_csv(rows: list[dict]) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"load_test_cache_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["timestamp", "request_number", "prompt", "status_code", "latency_ms", "cache_hit"]
        )
        writer.writeheader()
        writer.writerows(rows)
    return out_path


def _summarize(rows: list[dict]) -> dict:
    successful = [r for r in rows if 200 <= r["status_code"] < 300]
    hits = [r for r in successful if r["cache_hit"] is True]
    misses = [r for r in successful if r["cache_hit"] is False]

    hit_rate = (len(hits) / len(successful)) if successful else float("nan")
    avg_latency_cached_ms = (sum(r["latency_ms"] for r in hits) / len(hits)) if hits else None
    avg_latency_uncached_ms = (sum(r["latency_ms"] for r in misses) / len(misses)) if misses else None
    latency_reduction_pct = (
        (1 - avg_latency_cached_ms / avg_latency_uncached_ms) * 100
        if avg_latency_cached_ms is not None and avg_latency_uncached_ms
        else None
    )

    return {
        "hit_rate": hit_rate,
        "avg_latency_cached_ms": avg_latency_cached_ms,
        "avg_latency_uncached_ms": avg_latency_uncached_ms,
        "latency_reduction_pct": latency_reduction_pct,
        "hits": len(hits),
        "misses": len(misses),
    }


def _append_to_metrics_md(requests: int, repeat_ratio: float, pool_size: int, summary: dict, csv_path: Path) -> None:
    if not METRICS_FILE.exists():
        return
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    config = f"requests={requests}, repeat_ratio={repeat_ratio}, pool_size={pool_size}"
    total = summary["hits"] + summary["misses"]
    if summary["avg_latency_cached_ms"] is not None and summary["avg_latency_uncached_ms"] is not None:
        key_numbers = (
            f"hit_rate={summary['hit_rate']:.0%} ({summary['hits']}/{total}), "
            f"avg_latency_cached_ms={summary['avg_latency_cached_ms']:.0f}, "
            f"avg_latency_uncached_ms={summary['avg_latency_uncached_ms']:.0f}, "
            f"latency_reduction={summary['latency_reduction_pct']:.0f}%"
        )
    else:
        key_numbers = (
            f"hit_rate={summary['hit_rate']:.0%} ({summary['hits']}/{total}) — "
            f"not enough of both hits and misses to compute latency reduction"
        )
    notes = f"raw results: {csv_path.relative_to(METRICS_FILE.parents[1])}"
    row = f"| {date} | Cache load test (generation pipeline) | scripts/load_test_cache.py | {config} | {key_numbers} | {notes} |\n"

    with METRICS_FILE.open("a", encoding="utf-8") as f:
        f.write(row)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--gateway-url", default="http://127.0.0.1:8000")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument(
        "--repeat-ratio", type=float, default=0.6,
        help="target fraction of requests that are repeats of an earlier prompt",
    )
    parser.add_argument("--pool-size", type=int, default=20, help="number of distinct prompts in the query pool")
    parser.add_argument("--model", default="mock-model")
    parser.add_argument("--interval", type=float, default=0.05, help="seconds to sleep between requests")
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args()

    rows = run_load_test(
        args.gateway_url, args.requests, args.repeat_ratio, args.pool_size, args.model, args.interval, args.timeout,
    )

    csv_path = _write_results_csv(rows)
    summary = _summarize(rows)

    print("\n--- Summary ---")
    print(f"Cache hit rate: {summary['hit_rate']:.0%} ({summary['hits']}/{summary['hits'] + summary['misses']})")
    print(f"Avg latency (cache hit): {summary['avg_latency_cached_ms']}")
    print(f"Avg latency (cache miss): {summary['avg_latency_uncached_ms']}")
    print(f"Latency reduction: {summary['latency_reduction_pct']}")
    print(f"Raw results: {csv_path}")

    _append_to_metrics_md(args.requests, args.repeat_ratio, args.pool_size, summary, csv_path)
    print(f"Appended summary row to {METRICS_FILE}")


if __name__ == "__main__":
    main()
