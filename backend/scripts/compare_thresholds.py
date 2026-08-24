"""Circuit-breaker threshold-sensitivity comparison (Phase 4, stage 10).

Runs the same chaos scenario twice — once against a "trips fast, recovers
fast" circuit-breaker config, once against a "trips slow, recovers slow"
config — and prints/logs both runs side by side. This is what demonstrates
the actual tradeoff (a low threshold stops hammering a broken provider
sooner, at the cost of tripping on transient blips that retry alone might
have absorbed; a high threshold tolerates more noise before giving up, at
the cost of more wasted calls to something already broken) rather than just
asserting a number was implemented.

Usage (two terminals — this script manages its own gateway subprocess per
config, since CIRCUIT_BREAKER_* settings are only read once at startup):
    cd backend
    uvicorn app.mock_provider.server:app --port 9100 --reload   # terminal 1: mock provider (stays up throughout)
    python scripts/compare_thresholds.py                         # terminal 2: this script
"""

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from chaos_test import METRICS_FILE, _summarize, _write_results_csv, run_chaos_test  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]
GATEWAY_PORT = 8000
GATEWAY_URL = f"http://127.0.0.1:{GATEWAY_PORT}"


def _wait_for_gateway(timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            httpx.get(f"{GATEWAY_URL}/api/v1/health", timeout=1.0)
            return
        except httpx.HTTPError:
            time.sleep(0.3)
    raise RuntimeError("gateway did not become ready in time")


def _start_gateway(failure_threshold: int, recovery_timeout_seconds: float) -> subprocess.Popen:
    env = os.environ.copy()
    env.update({
        "GENERATION_MOCK_ONLY": "true",
        "CIRCUIT_BREAKER_FAILURE_THRESHOLD": str(failure_threshold),
        "CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SECONDS": str(recovery_timeout_seconds),
    })
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(GATEWAY_PORT)],
        env=env,
        cwd=str(BACKEND_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _wait_for_gateway()
    return proc


def _run_one_config(
    label: str,
    failure_threshold: int,
    recovery_timeout_seconds: float,
    mock_url: str,
    requests: int,
    fail_after: int,
    fail_for: int,
    mode: str,
    interval: float,
    model: str,
    timeout: float,
) -> dict:
    print(f"\n=== {label} (failure_threshold={failure_threshold}, recovery_timeout_seconds={recovery_timeout_seconds}s) ===")
    proc = _start_gateway(failure_threshold, recovery_timeout_seconds)
    try:
        httpx.post(f"{mock_url}/admin/reset")
        rows = run_chaos_test(GATEWAY_URL, mock_url, requests, fail_after, fail_for, mode, interval, model, timeout)
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        time.sleep(1.0)  # let the port free up before the next config starts its own gateway

    csv_path = _write_results_csv(rows)
    summary = _summarize(rows, fail_after, fail_for)
    return {
        "label": label,
        "failure_threshold": failure_threshold,
        "recovery_timeout_seconds": recovery_timeout_seconds,
        "csv_path": csv_path,
        **summary,
    }


def _append_comparison_to_metrics_md(configs: list[dict], requests: int, fail_after: int, fail_for: int, mode: str) -> None:
    if not METRICS_FILE.exists():
        return
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with METRICS_FILE.open("a", encoding="utf-8") as f:
        for c in configs:
            config = (
                f"{c['label']}: failure_threshold={c['failure_threshold']}, "
                f"recovery_timeout_seconds={c['recovery_timeout_seconds']}, "
                f"requests={requests}, fail_after={fail_after}, fail_for={fail_for}, mode={mode}"
            )
            key_numbers = (
                f"success_rate={c['success_rate_during_failure']:.0%}, "
                f"first_error_response={c['first_error_response_after_n_requests']} req, "
                f"recovery={c['recovery_after_n_requests']} req"
            )
            notes = f"raw results: {c['csv_path'].relative_to(METRICS_FILE.parents[1])} — part of a threshold comparison, see other row for the paired config"
            row = f"| {date} | Circuit-breaker threshold comparison (generation pipeline) | scripts/compare_thresholds.py | {config} | {key_numbers} | {notes} |\n"
            f.write(row)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mock-url", default="http://127.0.0.1:9100")
    parser.add_argument("--requests", type=int, default=20)
    parser.add_argument("--fail-after", type=int, default=3)
    parser.add_argument("--fail-for", type=int, default=8)
    parser.add_argument("--mode", default="error", choices=["error", "flaky", "timeout", "slow"])
    parser.add_argument("--interval", type=float, default=0.3)
    parser.add_argument("--model", default="mock-model")
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--fast-threshold", type=int, default=1, help="failure_threshold for the 'trips fast' config")
    parser.add_argument("--fast-recovery", type=float, default=5.0, help="recovery_timeout_seconds for the 'trips fast' config")
    parser.add_argument("--slow-threshold", type=int, default=5, help="failure_threshold for the 'trips slow' config")
    parser.add_argument("--slow-recovery", type=float, default=30.0, help="recovery_timeout_seconds for the 'trips slow' config")
    args = parser.parse_args()

    fast = _run_one_config(
        "fast-trip", args.fast_threshold, args.fast_recovery, args.mock_url,
        args.requests, args.fail_after, args.fail_for, args.mode, args.interval, args.model, args.timeout,
    )
    slow = _run_one_config(
        "slow-trip", args.slow_threshold, args.slow_recovery, args.mock_url,
        args.requests, args.fail_after, args.fail_for, args.mode, args.interval, args.model, args.timeout,
    )

    print("\n--- Comparison ---")
    header = f"{'Config':<12} {'threshold':<10} {'recovery_s':<11} {'success_rate':<13} {'first_error_req':<17} {'recovery_req':<13}"
    print(header)
    for c in (fast, slow):
        print(
            f"{c['label']:<12} {c['failure_threshold']:<10} {c['recovery_timeout_seconds']:<11} "
            f"{c['success_rate_during_failure']:<13.0%} {str(c['first_error_response_after_n_requests']):<17} "
            f"{str(c['recovery_after_n_requests']):<13}"
        )

    _append_comparison_to_metrics_md([fast, slow], args.requests, args.fail_after, args.fail_for, args.mode)
    print(f"\nAppended both rows to {METRICS_FILE}")


if __name__ == "__main__":
    main()
