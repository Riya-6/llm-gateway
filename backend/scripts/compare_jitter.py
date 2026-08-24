"""Backoff jitter on-vs-off comparison (Phase 4, stage 10).

The case for jitter isn't visible from a single request's latency — it's
about what happens when MANY concurrent callers retry the same recovering
provider at once. Without jitter, every caller computes the exact same
exponential-backoff delay and all retry in lockstep, producing a
synchronized burst ("thundering herd") that can knock a barely-recovered
provider back over. With jitter, each caller's retry lands at an
independently randomized point instead of all landing at once.

This is a fast, deterministic, in-process simulation — not a live HTTP
chaos run — because the thing being measured (how spread-out N callers'
retry timings are) only shows up across many simultaneous callers, and
running that for real would mean actually spinning up N concurrent clients
and waiting out real backoff delays. Simulating it directly against
call_with_retry (with a fake sleep_fn recording virtual elapsed time
instead of really sleeping) gets the same answer instantly and repeatably.

Usage:
    cd backend
    python scripts/compare_jitter.py
"""

import argparse
import random
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/, for `import app.*`

from app.domains.generation.providers.base import GenerationError, ProviderResponse  # noqa: E402
from app.domains.generation.retry import call_with_retry  # noqa: E402

METRICS_FILE = Path(__file__).resolve().parents[2] / "docs" / "metrics.md"


class _FlakyThenRecoversProvider:
    name = "sim"

    def __init__(self, fail_times: int) -> None:
        self.fail_times = fail_times
        self.call_count = 0

    def generate(self, prompt: str, model: str) -> ProviderResponse:
        self.call_count += 1
        if self.call_count <= self.fail_times:
            raise GenerationError("simulated failure")
        return ProviderResponse(provider=self.name, model=model, content="ok", tokens_used=1, latency_ms=1)


def _simulate_one_caller(
    jitter: bool,
    base_backoff_seconds: float,
    max_backoff_seconds: float,
    max_attempts: int,
    fail_times: int,
    rng: random.Random,
) -> list[float]:
    """Returns the delay (virtual seconds) computed before each retry, in order."""
    provider = _FlakyThenRecoversProvider(fail_times)
    delays: list[float] = []

    def sleep_fn(delay: float) -> None:
        delays.append(delay)

    call_with_retry(
        provider, "prompt", "model",
        max_attempts=max_attempts, base_backoff_seconds=base_backoff_seconds,
        max_backoff_seconds=max_backoff_seconds, jitter=jitter,
        sleep_fn=sleep_fn, random_fn=rng.random,
    )
    return delays


def _run_scenario(
    jitter: bool,
    callers: int,
    base_backoff_seconds: float,
    max_backoff_seconds: float,
    max_attempts: int,
    fail_times: int,
) -> list[list[float]]:
    all_delays = []
    for i in range(callers):
        rng = random.Random(1000 + i)  # distinct, reproducible stream per caller
        all_delays.append(
            _simulate_one_caller(jitter, base_backoff_seconds, max_backoff_seconds, max_attempts, fail_times, rng)
        )
    return all_delays


def _round_stats(all_delays: list[list[float]], round_index: int) -> dict:
    values = [d[round_index] for d in all_delays if len(d) > round_index]
    return {
        "n": len(values),
        "mean": statistics.mean(values) if values else float("nan"),
        "stddev": statistics.pstdev(values) if len(values) > 1 else 0.0,
        "min": min(values) if values else float("nan"),
        "max": max(values) if values else float("nan"),
    }


def _append_to_metrics_md(config: dict, jitter_off_rounds: list[dict], jitter_on_rounds: list[dict]) -> None:
    if not METRICS_FILE.exists():
        return
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    config_str = (
        f"callers={config['callers']}, base_backoff_seconds={config['base_backoff_seconds']}, "
        f"max_attempts={config['max_attempts']}, fail_times={config['fail_times']}"
    )
    for label, rounds in (("jitter=False", jitter_off_rounds), ("jitter=True", jitter_on_rounds)):
        per_round = "; ".join(
            f"round {i + 1}: stddev={r['stddev']:.3f}s, range=[{r['min']:.3f},{r['max']:.3f}]s"
            for i, r in enumerate(rounds)
        )
        row = (
            f"| {date} | Backoff jitter comparison (generation pipeline) | "
            f"scripts/compare_jitter.py | {label}, {config_str} | {per_round} | "
            f"in-process simulation, not a live HTTP run — see script docstring for why |\n"
        )
        with METRICS_FILE.open("a", encoding="utf-8") as f:
            f.write(row)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--callers", type=int, default=20, help="number of simulated concurrent callers")
    parser.add_argument("--base-backoff-seconds", type=float, default=1.0)
    parser.add_argument("--max-backoff-seconds", type=float, default=10.0)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--fail-times", type=int, default=2, help="failures before the simulated provider recovers")
    args = parser.parse_args()

    jitter_off = _run_scenario(False, args.callers, args.base_backoff_seconds, args.max_backoff_seconds, args.max_attempts, args.fail_times)
    jitter_on = _run_scenario(True, args.callers, args.base_backoff_seconds, args.max_backoff_seconds, args.max_attempts, args.fail_times)

    num_rounds = args.max_attempts - 1
    jitter_off_rounds = [_round_stats(jitter_off, i) for i in range(num_rounds)]
    jitter_on_rounds = [_round_stats(jitter_on, i) for i in range(num_rounds)]

    print(f"\nSimulating {args.callers} concurrent callers, each retrying up to {args.max_attempts} times "
          f"against a provider that fails {args.fail_times} time(s) then recovers.\n")

    for label, rounds in (("jitter=False", jitter_off_rounds), ("jitter=True", jitter_on_rounds)):
        print(f"--- {label} ---")
        for i, r in enumerate(rounds):
            print(
                f"  retry round {i + 1}: n={r['n']}, mean={r['mean']:.3f}s, stddev={r['stddev']:.3f}s, "
                f"range=[{r['min']:.3f}s, {r['max']:.3f}s]"
            )
        print()

    print(
        "Interpretation: stddev=0 (jitter=False) means every caller retried at the EXACT same virtual "
        "time — a perfectly synchronized burst. A non-zero stddev with a spread-out range (jitter=True) "
        "means callers' retries land at different times instead of all landing on the provider at once."
    )

    config = {
        "callers": args.callers, "base_backoff_seconds": args.base_backoff_seconds,
        "max_attempts": args.max_attempts, "fail_times": args.fail_times,
    }
    _append_to_metrics_md(config, jitter_off_rounds, jitter_on_rounds)
    print(f"\nAppended both rows to {METRICS_FILE}")


if __name__ == "__main__":
    main()
