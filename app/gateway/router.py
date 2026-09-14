import logging
import time
from dataclasses import dataclass
from typing import Any

from app.core.config import settings

logger = logging.getLogger("gateway.router")


@dataclass
class ProviderEndpoint:
    name: str
    model: str
    is_available: bool = True
    consecutive_failures: int = 0
    circuit_open_until: float = 0.0
    failure_threshold: int = 3
    cooldown_seconds: float = 30.0

    def is_healthy(self) -> bool:
        if not self.is_available:
            return False
        if self.circuit_open_until > time.time():
            return False
        return True

    def record_success(self):
        self.consecutive_failures = 0
        self.circuit_open_until = 0.0

    def record_failure(self, error: Exception):
        self.consecutive_failures += 1
        logger.warning(
            f"Provider '{self.name}' failed ({self.consecutive_failures}/{self.failure_threshold}): {error}"
        )
        if self.consecutive_failures >= self.failure_threshold:
            self.circuit_open_until = time.time() + self.cooldown_seconds
            logger.error(
                f"Circuit tripped for provider '{self.name}'. Backing off for {self.cooldown_seconds}s"
            )


class FailoverRouter:
    """Manages prioritized failover routing across OpenAI, Groq, Bedrock, and Mock providers."""

    def __init__(self):
        self.providers: list[ProviderEndpoint] = []
        self._init_providers()

    def _init_providers(self):
        # Primary: OpenAI
        has_openai = bool(settings.OPENAI_API_KEY)
        self.providers.append(
            ProviderEndpoint(
                name="openai",
                model=settings.PRIMARY_MODEL,
                is_available=has_openai,
            )
        )

        # Fallback 1: Groq
        has_groq = bool(settings.GROQ_API_KEY)
        self.providers.append(
            ProviderEndpoint(
                name="groq",
                model=settings.FALLBACK_MODEL_1.replace("groq/", ""),
                is_available=has_groq,
            )
        )

        # Fallback 2: Bedrock (requires AWS credentials for model invocation)
        has_bedrock = bool(
            settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY
        )
        self.providers.append(
            ProviderEndpoint(
                name="bedrock",
                model=settings.FALLBACK_MODEL_2.replace("bedrock/", ""),
                is_available=has_bedrock,
            )
        )

        # Fallback 3: Deterministic Offline Mock (always available for local zero-key evaluation)
        self.providers.append(
            ProviderEndpoint(
                name="mock",
                model="deterministic-research-mock",
                is_available=True,
            )
        )

    def get_candidate_providers(self) -> list[ProviderEndpoint]:
        """Returns ordered list of healthy providers."""
        candidates = [p for p in self.providers if p.is_healthy()]
        if not candidates:
            # If all external circuits are open, always allow the mock fallback
            mock = next((p for p in self.providers if p.name == "mock"), None)
            if mock:
                return [mock]
        return candidates

    def get_status(self) -> list[dict[str, Any]]:
        return [
            {
                "name": p.name,
                "model": p.model,
                "is_available": p.is_available,
                "is_healthy": p.is_healthy(),
                "failures": p.consecutive_failures,
                "circuit_open": p.circuit_open_until > time.time(),
            }
            for p in self.providers
        ]
