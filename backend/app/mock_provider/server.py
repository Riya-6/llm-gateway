"""Standalone mock LLM provider, run as its own process for chaos testing.

Run separately from the main gateway app:
    uvicorn app.mock_provider.server:app --port 9100 --reload

Being a real, independently-reachable HTTP server (rather than an in-process
Python object) means the gateway's retry/circuit-breaker code sees the same
timeout/connection/5xx failure shapes a real provider outage would produce —
`time.sleep` inside a mocked function can't reproduce a genuinely hung
connection the way an actual slow HTTP response can.
"""

import random
import time
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Mock LLM Provider")

Mode = Literal["normal", "slow", "error", "timeout", "flaky"]

_state = {
    "mode": "normal",
    "slow_latency_seconds": 3.0,
    "flaky_failure_rate": 0.5,
    "call_count": 0,
}


class SetModeRequest(BaseModel):
    mode: Mode
    slow_latency_seconds: float | None = None
    flaky_failure_rate: float | None = None


class GenerateRequest(BaseModel):
    model: str
    prompt: str


@app.post("/admin/mode")
def set_mode(payload: SetModeRequest) -> dict:
    _state["mode"] = payload.mode
    if payload.slow_latency_seconds is not None:
        _state["slow_latency_seconds"] = payload.slow_latency_seconds
    if payload.flaky_failure_rate is not None:
        _state["flaky_failure_rate"] = payload.flaky_failure_rate
    return dict(_state)


@app.get("/admin/mode")
def get_mode() -> dict:
    return dict(_state)


@app.post("/admin/reset")
def reset() -> dict:
    _state.update(mode="normal", slow_latency_seconds=3.0, flaky_failure_rate=0.5, call_count=0)
    return dict(_state)


@app.post("/v1/generate")
def generate(payload: GenerateRequest) -> dict:
    _state["call_count"] += 1
    mode = _state["mode"]

    if mode == "error":
        raise HTTPException(status_code=500, detail="mock provider: simulated error")

    if mode == "timeout":
        # Sleeps far longer than any sane client timeout — simulates a hung
        # connection rather than an immediate failure.
        time.sleep(120)

    if mode == "slow":
        time.sleep(_state["slow_latency_seconds"])

    if mode == "flaky" and random.random() < _state["flaky_failure_rate"]:
        raise HTTPException(status_code=503, detail="mock provider: simulated flaky failure")

    return {
        "content": f"mock response to: {payload.prompt[:50]}",
        "tokens_used": max(1, len(payload.prompt.split())),
    }
