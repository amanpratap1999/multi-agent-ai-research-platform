from typing import Any, Literal

from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class ClaimAudit(BaseModel):
    claim: str = Field(description="The factual claim extracted from the draft report")
    citation_url: str = Field(description="The source URL provided for this claim")
    verdict: Literal["SUPPORTED", "CONTRADICTED", "UNVERIFIED"] = Field(
        description="Verification outcome against the cited source content"
    )
    quoted_evidence: str = Field(
        default="",
        description="Exact or near-verbatim quote from the source supporting or contradicting the claim"
    )


class SourceSnippet(BaseModel):
    id: str
    title: str
    url: str
    snippet: str
    is_quarantined: bool = False
    quarantine_reason: str | None = None


class GuardrailTelemetry(BaseModel):
    boundary: Literal["ingress", "xpia", "egress"]
    action: Literal["NONE", "GUARDRAIL_INTERVENED"]
    policy: str  # e.g., "PROMPT_ATTACK", "PII", "DENIED_TOPIC"
    latency_ms: float
    timestamp: str
    details: dict[str, Any] | None = None


class ResearchState(TypedDict):
    topic: str
    session_id: str
    search_queries: list[str]
    raw_sources: list[dict[str, Any]]
    scrubbed_sources: list[dict[str, Any]]
    quarantined_sources: list[dict[str, Any]]
    summary: str
    draft_report: str
    claims_audit: list[dict[str, Any]]
    verification_feedback: str
    verification_score: float
    iteration_count: int
    is_degraded: bool
    final_report: dict[str, Any]
    defense_telemetry: list[dict[str, Any]]
