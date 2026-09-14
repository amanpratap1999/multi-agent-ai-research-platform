import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings
from app.core.events import event_broadcaster

logger = logging.getLogger("evaluation.langsmith_judge")


class LangSmithJudge:
    """LangSmith LLM-as-judge evaluator for empirical accuracy, grounding, and citation validity."""

    def __init__(self):
        self.is_configured = bool(settings.LANGCHAIN_TRACING_V2 or settings.LANGCHAIN_API_KEY)
        self.client = None
        self.evaluation_history: list[dict[str, Any]] = []

        if self.is_configured:
            try:
                from langsmith import Client
                self.client = Client(api_key=settings.LANGCHAIN_API_KEY)
                logger.info(f"LangSmith Judge connected to project: '{settings.LANGCHAIN_PROJECT}'")
            except Exception as e:
                logger.warning(f"Failed to initialize LangSmith client: {e}. Running in audit mode.")
                self.client = None

    async def submit_evaluation(
        self,
        session_id: str,
        topic: str,
        draft_report: str,
        claims_audit: list[dict[str, Any]],
        verification_score: float,
        feedback: str = "",
        iteration: int = 1,
    ) -> dict[str, Any]:
        """Calculates multi-dimensional judge metrics and submits evaluation to LangSmith."""
        total_claims = len(claims_audit)
        supported_count = sum(1 for c in claims_audit if c.get("verdict") == "SUPPORTED")
        contradicted_count = sum(1 for c in claims_audit if c.get("verdict") == "CONTRADICTED")
        unverified_count = sum(1 for c in claims_audit if c.get("verdict") == "UNVERIFIED")

        # 1. Metric calculations
        accuracy_score = round(verification_score, 2)
        grounding_score = round(supported_count / total_claims, 2) if total_claims > 0 else 1.0

        cited_claims = sum(
            1 for c in claims_audit
            if c.get("citation_url") and (c.get("quoted_evidence") or c.get("verdict") == "SUPPORTED")
        )
        citation_score = round(cited_claims / total_claims, 2) if total_claims > 0 else 1.0

        eval_id = str(uuid.uuid4())
        timestamp = datetime.now(UTC).isoformat()

        eval_record = {
            "evaluation_id": eval_id,
            "session_id": session_id,
            "project_name": settings.LANGCHAIN_PROJECT,
            "topic": topic,
            "iteration": iteration,
            "metrics": {
                "accuracy_score": accuracy_score,
                "grounding_score": grounding_score,
                "citation_score": citation_score,
                "total_claims": total_claims,
                "supported_count": supported_count,
                "contradicted_count": contradicted_count,
                "unverified_count": unverified_count,
            },
            "feedback": feedback,
            "submitted_to_langsmith": False,
            "timestamp": timestamp,
        }

        # 2. Submit to LangSmith if client is available
        if self.client:
            try:
                run = self.client.create_run(
                    name="llm_judge_verification",
                    run_type="evaluator",
                    project_name=settings.LANGCHAIN_PROJECT,
                    inputs={
                        "topic": topic,
                        "session_id": session_id,
                        "iteration": iteration,
                        "report_snippet": draft_report[:500] if draft_report else "",
                    },
                    outputs={
                        "verification_score": verification_score,
                        "accuracy_score": accuracy_score,
                        "grounding_score": grounding_score,
                        "citation_score": citation_score,
                        "claims_count": total_claims,
                        "feedback": feedback,
                    },
                    extra={
                        "claims_audit": claims_audit,
                        "session_id": session_id,
                    }
                )
                run_id = getattr(run, "id", None) or eval_id
                # Post individual metric feedback scores
                self.client.create_feedback(
                    run_id=run_id,
                    key="factual_accuracy",
                    score=accuracy_score,
                    comment=feedback or "Empirical fact verification pass",
                )
                self.client.create_feedback(
                    run_id=run_id,
                    key="citation_grounding",
                    score=grounding_score,
                )
                self.client.create_feedback(
                    run_id=run_id,
                    key="citation_validity",
                    score=citation_score,
                )
                eval_record["submitted_to_langsmith"] = True
                eval_record["langsmith_run_id"] = str(run_id)
                logger.info(f"Submitted LangSmith judge evaluation {eval_id} (run_id: {run_id})")
            except Exception as e:
                logger.warning(f"Could not submit evaluation run to LangSmith API: {e}")

        # 3. Store locally in evaluation history
        self.evaluation_history.append(eval_record)

        # 4. Broadcast evaluation telemetry to SSE clients
        await event_broadcaster.publish_event(
            session_id=session_id,
            event_type="langsmith_evaluation",
            data=eval_record
        )

        return eval_record


langsmith_judge = LangSmithJudge()
