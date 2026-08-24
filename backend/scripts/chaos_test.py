"""Chaos-test harness for the generation pipeline (Phase 4, stage 9).

Injects a failure mode into the mock provider server mid-run, via a real
running gateway, and measures how the router/retry/circuit-breaker/fallback
stack actually behaves — not the deterministic unit tests, real timing
against real HTTP.

Usage (three terminals):
    cd backend
    uvicorn app.main:app --reload                                # terminal 1: gateway
    uvicorn app.mock_provider.server:app --port 9100 --reload     # terminal 2: mock provider
    python scripts/chaos_test.py                                  # terminal 3: this script

What it does:
    1. Registers a throwaway user + project against the running gateway.
    2. Resets the mock provider to "normal".
    3. Fires --requests sequential calls to POST /generate, one every
       --interval seconds.
    4. After --fail-after requests, sets the mock provider to --mode via its
       admin endpoint. After --fail-for further requests, resets it back to
       "normal".
    5. Logs every request's timing/outcome to a CSV file under
       backend/scripts/results/.
    6. Prints a summary and appends a row to docs/metrics.md's table.

Note on the default provider chain: router.py tries OpenAI, Anthropic, and
Ollama before the mock. Without real API keys / a running Ollama, those
routes fail fast (401 / connection refused) and their circuit breakers trip
after a few requests — after which they're skipped instantly and the mock
is effectively the active provider for the rest of the run. That's the
fallback/circuit-breaker behavior actually working, not a script bug.
"""

import argparse
import csv
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx

RESULTS_DIR = Path(__file__).resolve().parent / "results"
METRICS_FILE = Path(__file__).resolve().parents[2] / "docs" / "metrics.md"


def _register_project(gateway_url: str) -> tuple[str, str]:
    email = f"chaos-{uuid4().hex[:8]}@example.com"
    password = "hunter22"

    httpx.post(f"{gateway_url}/api/v1/auth/register", json={"email": email, "password": password})
    login = httpx.post(
        f"{gateway_url}/api/v1/auth/login", data={"username": email, "password": password}
    )
    login.raise_for_status()
    token = login.json()["access_token"]

    project = httpx.post(
        f"{gateway_url}/api/v1/projects",
        json={"name": f"chaos-test-{uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    project.raise_for_status()
    return token, project.json()["id"]


def _set_mock_mode(mock_url: str, mode: str) -> None:
    httpx.post(f"{mock_url}/admin/mode", json={"mode": mode})


def run_chaos_test(
    gateway_url: str,
    mock_url: str,
    requests: int,
    fail_after: int,
    fail_for: int,
    mode: str,
    interval: float,
    model: str,
    request_timeout: float,
) -> list[dict]:
    print(f"Registering throwaway user/project against {gateway_url} ...")
    token, project_id = _register_project(gateway_url)
    headers = {"Authorization": f"Bearer {token}"}

    print(f"Resetting mock provider at {mock_url} to normal ...")
    httpx.post(f"{mock_url}/admin/reset")

    rows: list[dict] = []
    fail_start = fail_after
    fail_end = fail_after + fail_for

    for i in range(1, requests + 1):
        if i == fail_start + 1:
            print(f"[request {i}] injecting failure mode: {mode}")
            _set_mock_mode(mock_url, mode)
        if i == fail_end + 1:
            print(f"[request {i}] resetting mock provider to normal")
            _set_mock_mode(mock_url, "normal")

        active_mode = mode if fail_start < i <= fail_end else "normal"

        started = time.monotonic()
        served_by = None
        try:
            response = httpx.post(
                f"{gateway_url}/api/v1/projects/{project_id}/generate",
                json={"prompt": "chaos test prompt", "model": model},
                headers=headers,
                timeout=request_timeout,
            )
            status_code = response.status_code
            if 200 <= status_code < 300:
                try:
                    served_by = response.json().get("provider")
                except ValueError:
                    served_by = None
        except httpx.HTTPError as exc:
            status_code = -1
            print(f"[request {i}] transport error: {exc}")
        latency_ms = int((time.monotonic() - started) * 1000)

        rows.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_number": i,
            "active_mode": active_mode,
            "status_code": status_code,
            "latency_ms": latency_ms,
            "served_by": served_by,
        })
        print(f"[request {i}] mode={active_mode} status={status_code} latency_ms={latency_ms} served_by={served_by}")

        if interval > 0:
            time.sleep(interval)

    return rows


def _write_results_csv(rows: list[dict]) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"chaos_test_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["timestamp", "request_number", "active_mode", "status_code", "latency_ms", "served_by"]
        )
        writer.writeheader()
        writer.writerows(rows)
    return out_path


def _summarize(rows: list[dict], fail_after: int, fail_for: int) -> dict:
    """Note on terminology: with the default GENERATION_MOCK_ONLY=true config
    this script expects, there's only one provider — so nothing here measures
    an actual "fallback to a second provider" (that would need 2+ providers
    configured and enough failures to route past the first). What IS
    measured: (1) success rate during the injected-failure window, (2) how
    quickly the pipeline starts returning a proper error status (502/503)
    instead of hanging once failures start, and (3) how many requests after
    the failure window ends it takes for the circuit breaker's half-open
    trial to actually succeed again (real recovery).
    """
    failure_window = [r for r in rows if fail_after < r["request_number"] <= fail_after + fail_for]
    successes_in_window = [r for r in failure_window if 200 <= r["status_code"] < 300]
    success_rate = (len(successes_in_window) / len(failure_window)) if failure_window else float("nan")
    providers_during_failure_window = sorted({r["served_by"] for r in successes_in_window if r["served_by"]})

    first_failure_response = next(
        (r for r in failure_window if r["status_code"] in (502, 503)), None
    )
    first_error_response_after_n_requests = (
        first_failure_response["request_number"] - fail_after if first_failure_response else None
    )

    recovery_window = [r for r in rows if r["request_number"] > fail_after + fail_for]
    first_recovered = next((r for r in recovery_window if 200 <= r["status_code"] < 300), None)
    recovery_request_offset = (
        first_recovered["request_number"] - (fail_after + fail_for) if first_recovered else None
    )

    return {
        "success_rate_during_failure": success_rate,
        "first_error_response_after_n_requests": first_error_response_after_n_requests,
        "recovery_after_n_requests": recovery_request_offset,
        "providers_during_failure_window": providers_during_failure_window,
    }


def _append_to_metrics_md(mode: str, requests: int, fail_after: int, fail_for: int, summary: dict, csv_path: Path) -> None:
    if not METRICS_FILE.exists():
        return
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    config = f"requests={requests}, fail_after={fail_after}, fail_for={fail_for}, mode={mode}"
    key_numbers = (
        f"success_rate={summary['success_rate_during_failure']:.0%}, "
        f"first_error_response={summary['first_error_response_after_n_requests']} req, "
        f"recovery={summary['recovery_after_n_requests']} req, "
        f"served_by_during_failure={summary['providers_during_failure_window'] or 'none'}"
    )
    notes = f"raw results: {csv_path.relative_to(METRICS_FILE.parents[1])}"
    row = f"| {date} | Chaos test (generation pipeline) | scripts/chaos_test.py | {config} | {key_numbers} | {notes} |\n"

    with METRICS_FILE.open("a", encoding="utf-8") as f:
        f.write(row)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--gateway-url", default="http://127.0.0.1:8000")
    parser.add_argument("--mock-url", default="http://127.0.0.1:9100")
    parser.add_argument("--requests", type=int, default=30)
    parser.add_argument("--fail-after", type=int, default=8, help="requests to send before injecting failure")
    parser.add_argument("--fail-for", type=int, default=10, help="requests to keep the failure mode active for")
    parser.add_argument("--mode", default="error", choices=["error", "flaky", "timeout", "slow"])
    parser.add_argument("--interval", type=float, default=0.3, help="seconds to sleep between requests")
    parser.add_argument(
        "--model", default="mock-model",
        help="model name sent with every request — the mock provider ignores this, but a real fallback "
             "provider validates it (e.g. gpt-4o-mini for OpenAI). Wrong model name here looks exactly "
             "like a provider failure, so get this right when testing against a real provider.",
    )
    parser.add_argument(
        "--timeout", type=float, default=15.0,
        help="per-request client timeout in seconds. The mock provider is near-instant, but real "
             "providers can genuinely take 10-15s+ depending on model/load — too short a timeout here "
             "shows up as a client-side 'transport error', which looks like a pipeline failure but isn't.",
    )
    args = parser.parse_args()

    rows = run_chaos_test(
        args.gateway_url, args.mock_url, args.requests, args.fail_after, args.fail_for, args.mode, args.interval,
        args.model, args.timeout,
    )

    csv_path = _write_results_csv(rows)
    summary = _summarize(rows, args.fail_after, args.fail_for)

    print("\n--- Summary ---")
    print(f"Success rate during failure window: {summary['success_rate_during_failure']:.0%}")
    print(
        f"First error response (502/503, not a successful fallback) after: "
        f"{summary['first_error_response_after_n_requests']} requests into the failure window"
    )
    print(f"First recovered (2xx) response after: {summary['recovery_after_n_requests']} requests into the recovery window")
    print(f"Provider(s) that actually served successful responses during the failure window: {summary['providers_during_failure_window'] or 'none'}")
    print(f"Raw results: {csv_path}")

    _append_to_metrics_md(args.mode, args.requests, args.fail_after, args.fail_for, summary, csv_path)
    print(f"Appended summary row to {METRICS_FILE}")


if __name__ == "__main__":
    main()
