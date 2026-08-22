from dataclasses import dataclass
from typing import Protocol


class GenerationError(Exception):
    """Raised when a provider fails to produce a response."""


class ProviderTimeoutError(GenerationError):
    """Raised when a provider does not respond within its configured timeout."""


@dataclass
class ProviderResponse:
    provider: str
    model: str
    content: str
    tokens_used: int
    latency_ms: int


class Provider(Protocol):
    name: str

    def generate(self, prompt: str, model: str) -> ProviderResponse: ...
