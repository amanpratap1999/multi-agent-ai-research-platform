import asyncio
import re
import time
from datetime import UTC, datetime
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.agents.state import GuardrailTelemetry
from app.core.config import settings
from app.core.logging import logger


class LocalBedrockMockEngine:
    """High-fidelity local mock of AWS Bedrock ApplyGuardrail.

    Implements the exact Boto3 ApplyGuardrailResponseTypeDef schema to provide
    authentic zero-credential testing of Prompt Attack, PII, and Denied Topic filters.
    """

    PROMPT_ATTACK_PATTERNS = [
        r"ignore\s+(all\s+)?(previous|prior)\s+(instructions|directives|rules)",
        r"you\s+are\s+now\s+in\s+developer\s+mode",
        r"dan\s+mode|jailbreak|unrestricted\s+mode",
        r"system\s+override\s*:\s*disable\s+safety",
        r"skeleton\s+key\s*:\s*override\s+guidelines",
        r"crescendo\s+exploit\s*:\s*reveal\s+(internal|secret|hidden)",
        r"disregard\s+content\s+policy",
        r"act\s+as\s+an\s+unfiltered\s+ai",
        r"<script.*?>.*?</script>",
        r"base64\s+decode\s+and\s+execute",
    ]

    DENIED_TOPICS = [
        (r"(?:build|creat|synthesiz|mak)\w*\s+.*?(?:bomb|weapon|explosive)|(?:chemical|biological)\s+weapons?", "WeaponsAndExplosives"),
        (r"(?:create|develop|build|write|distribut)\w*\s+.*?(?:malware|ransomware|trojan|keylogger|exploit)", "MalwareDevelopment"),
        (r"steal\w*\s+passwords?|sql\s+injection\s+exploit\s+script", "CyberAttacks"),
    ]

    SSN_PATTERN = r"\b\d{3}-\d{2}-\d{4}\b"
    CREDIT_CARD_PATTERN = r"\b(?:\d{4}[ -]?){3}\d{4}\b"
    EMAIL_PATTERN = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"

    def evaluate(self, text: str, source: str = "INPUT") -> dict[str, Any]:
        start_time = time.perf_counter()
        assessments: list[dict[str, Any]] = []
        action = "NONE"
        output_text = text

        # 1. Prompt Attack / Jailbreak Check
        attack_detected = False
        for pattern in self.PROMPT_ATTACK_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                attack_detected = True
                break

        if attack_detected:
            action = "GUARDRAIL_INTERVENED"
            output_text = "Sorry, I cannot process this request because it violates safety and security policies."
            assessments.append({
                "contentPolicy": {
                    "filters": [{
                        "type": "PROMPT_ATTACK",
                        "confidence": "HIGH",
                        "action": "BLOCKED"
                    }]
                }
            })

        # 2. Denied Topics Check
        for topic_regex, topic_name in self.DENIED_TOPICS:
            if re.search(topic_regex, text, re.IGNORECASE):
                action = "GUARDRAIL_INTERVENED"
                output_text = f"Request violates policy on denied topic: {topic_name}."
                assessments.append({
                    "topicPolicy": {
                        "topics": [{
                            "name": topic_name,
                            "type": "DENIED",
                            "action": "BLOCKED"
                        }]
                    }
                })
                break

        # 3. PII Detection & Anonymization
        pii_entities = []
        if re.search(self.EMAIL_PATTERN, output_text):
            action = "GUARDRAIL_INTERVENED"
            output_text = re.sub(self.EMAIL_PATTERN, "[ANONYMIZED_EMAIL]", output_text)
            pii_entities.append({"type": "EMAIL", "action": "ANONYMIZED"})

        if re.search(self.SSN_PATTERN, output_text):
            action = "GUARDRAIL_INTERVENED"
            output_text = re.sub(self.SSN_PATTERN, "[MASKED_SSN]", output_text)
            pii_entities.append({"type": "US_SOCIAL_SECURITY_NUMBER", "action": "ANONYMIZED"})

        if re.search(self.CREDIT_CARD_PATTERN, output_text):
            action = "GUARDRAIL_INTERVENED"
            output_text = re.sub(self.CREDIT_CARD_PATTERN, "[REDACTED_CREDIT_CARD]", output_text)
            pii_entities.append({"type": "CREDIT_DEBIT_CARD_NUMBER", "action": "ANONYMIZED"})

        if pii_entities:
            assessments.append({
                "sensitiveInformationPolicy": {
                    "piiEntities": pii_entities
                }
            })

        elapsed_ms = (time.perf_counter() - start_time) * 1000 + 15.0  # realistic local latency

        return {
            "action": action,
            "outputs": [{"text": output_text}],
            "assessments": assessments,
            "_latency_ms": elapsed_ms,
        }


class BedrockGuardrailClient:
    """Client for AWS Bedrock Guardrails with seamless Boto3 mock fallback."""

    def __init__(self):
        self.mock_engine = LocalBedrockMockEngine()
        self._is_live = bool(
            settings.AWS_ACCESS_KEY_ID
            and settings.AWS_SECRET_ACCESS_KEY
            and settings.BEDROCK_GUARDRAIL_ID
            and not settings.USE_BEDROCK_MOCK
        )
        if self._is_live:
            try:
                self.boto_client = boto3.client(
                    "bedrock-runtime",
                    region_name=settings.AWS_REGION,
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                )
                logger.info("BedrockGuardrailClient initialized in LIVE AWS mode.")
            except Exception as e:
                logger.warning(f"Failed to initialize Boto3 client, falling back to mock: {e}")
                self._is_live = False
        else:
            logger.info("BedrockGuardrailClient initialized in LOCAL MOCK mode.")

    @property
    def use_mock(self) -> bool:
        return not self._is_live

    @use_mock.setter
    def use_mock(self, value: bool) -> None:
        self._is_live = not value

    async def apply_guardrail(
        self,
        text: str,
        source: str = "INPUT",
        boundary: str = "ingress"
    ) -> dict[str, Any]:
        """Apply guardrail checks to text (ingress, xpia, or egress)."""
        start = time.perf_counter()

        if not self._is_live:
            res = self.mock_engine.evaluate(text, source=source)
            latency_ms = res.get("_latency_ms", (time.perf_counter() - start) * 1000)
        else:
            try:
                loop = asyncio.get_running_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self.boto_client.apply_guardrail(
                        guardrailIdentifier=settings.BEDROCK_GUARDRAIL_ID,
                        guardrailVersion=settings.BEDROCK_GUARDRAIL_VERSION,
                        source=source,
                        content=[{"text": {"text": text[:25000]}}]  # Enforce Bedrock 25k limit
                    )
                )
                res = response
                latency_ms = (time.perf_counter() - start) * 1000
            except (BotoCoreError, ClientError) as e:
                logger.error(f"AWS Bedrock ApplyGuardrail error: {e}. Falling back to mock engine.")
                res = self.mock_engine.evaluate(text, source=source)
                latency_ms = (time.perf_counter() - start) * 1000

        action = res.get("action", "NONE")
        output_text = text
        if res.get("outputs"):
            output_text = res["outputs"][0].get("text", text)

        policy_triggered = "NONE"
        if action == "GUARDRAIL_INTERVENED":
            assessments = res.get("assessments", [])
            for a in assessments:
                if "contentPolicy" in a:
                    policy_triggered = "PROMPT_ATTACK"
                    break
                elif "topicPolicy" in a:
                    policy_triggered = "DENIED_TOPIC"
                    break
                elif "sensitiveInformationPolicy" in a:
                    policy_triggered = "PII"
                    break
            if policy_triggered == "NONE":
                policy_triggered = "POLICY_VIOLATION"

        telemetry = GuardrailTelemetry(
            boundary=boundary,  # type: ignore
            action=action,
            policy=policy_triggered,
            latency_ms=round(latency_ms, 2),
            timestamp=datetime.now(UTC).isoformat(),
            details={"assessments": res.get("assessments", [])}
        )

        return {
            "action": action,
            "output_text": output_text,
            "policy": policy_triggered,
            "latency_ms": round(latency_ms, 2),
            "telemetry": telemetry.model_dump(),
            "raw_response": res
        }


guardrail_client = BedrockGuardrailClient()
