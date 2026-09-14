from typing import Any

from app.core.logging import logger
from app.defense.bedrock_guardrail import guardrail_client


class EgressFilter:
    """Applies guardrail evaluation to synthesized reports before client delivery."""

    @staticmethod
    async def filter_report(report_text: str) -> dict[str, Any]:
        result = await guardrail_client.apply_guardrail(
            text=report_text,
            source="OUTPUT",
            boundary="egress"
        )

        if result["action"] == "GUARDRAIL_INTERVENED":
            policy = result.get("policy", "POLICY_VIOLATION")
            logger.warning(f"Egress Guardrail Intervened: Policy {policy}")
            is_blocked = policy in ["DENIED_TOPIC", "PROMPT_ATTACK"]
            return {
                "safe": not is_blocked,
                "sanitized_text": result["output_text"],
                "policy": policy,
                "telemetry": result["telemetry"],
                "intervened": True,
            }

        return {
            "safe": True,
            "sanitized_text": report_text,
            "policy": "NONE",
            "telemetry": result["telemetry"],
            "intervened": False,
        }


egress_filter = EgressFilter()
