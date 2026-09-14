import logging
import time
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from app.agents.search_agent import search_node
from app.agents.state import ResearchState
from app.agents.summarize_agent import summarize_node
from app.agents.verify_agent import verify_node
from app.agents.write_agent import write_node
from app.core.config import settings
from app.core.events import event_broadcaster
from app.defense.egress_filter import egress_filter
from app.memory.postgres_ltm import save_research_artifact
from app.memory.semantic_cache import semantic_cache

logger = logging.getLogger("agents.graph")


async def degraded_export_node(state: ResearchState) -> dict[str, Any]:
    """Node 5 (Fallback): Flags unverified report when budget iterations are exhausted."""
    session_id = state.get("session_id", "default")
    draft = state.get("draft_report", "")
    score = state.get("verification_score", 0.0)

    warning_banner = (
        "> [!CAUTION]\n"
        f"> **CRITICAL_UNVERIFIED_WARNING**: Verification score ({score:.2f}) failed to achieve "
        "the 0.85 threshold after maximum retry iterations. Some empirical claims could not be verified "
        "against primary sources. Review claims audit prior to production use.\n\n"
    )
    degraded_report = warning_banner + draft

    await event_broadcaster.publish_event(
        session_id=session_id,
        event_type="agent_step",
        data={
            "agent": "degraded_export",
            "status": "completed",
            "message": "Flagged report with CRITICAL_UNVERIFIED_WARNING banner"
        }
    )

    return {
        "is_degraded": True,
        "draft_report": degraded_report,
    }


async def egress_guardrail_node(state: ResearchState) -> dict[str, Any]:
    """Node 6: Evaluates final report against Bedrock Guardrail egress filters and commits to LTM & Cache."""
    session_id = state.get("session_id", "default")
    topic = state.get("topic", "")
    draft = state.get("draft_report", "")
    score = state.get("verification_score", 1.0)
    is_degraded = state.get("is_degraded", False)
    claims_audit = state.get("claims_audit", [])
    scrubbed_sources = state.get("scrubbed_sources", [])
    quarantined_sources = state.get("quarantined_sources", [])
    defense_telemetry = list(state.get("defense_telemetry", []))

    await event_broadcaster.publish_event(
        session_id=session_id,
        event_type="agent_step",
        data={"agent": "egress_guardrail", "status": "running", "message": "Evaluating Bedrock Guardrail at egress boundary"}
    )

    # 1. Evaluate Egress Guardrail
    egress_result = await egress_filter.filter_report(draft)
    sanitized_text = egress_result.get("sanitized_text", draft)
    if egress_result.get("telemetry"):
        defense_telemetry.append(egress_result["telemetry"])

    final_report = {
        "session_id": session_id,
        "topic": topic,
        "report_markdown": sanitized_text,
        "verification_score": score,
        "is_degraded": is_degraded,
        "claims_audit": claims_audit,
        "sources": scrubbed_sources,
        "quarantined_sources": quarantined_sources,
        "defense_telemetry": defense_telemetry,
        "completed_at": time.time(),
    }

    # 2. Commit to PostgreSQL LTM
    try:
        await save_research_artifact(
            session_id=session_id,
            topic=topic,
            report_markdown=sanitized_text,
            claims_audit=claims_audit,
            verification_score=score,
            sources=scrubbed_sources,
        )
    except Exception as e:
        logger.warning(f"Could not persist research artifact to PostgreSQL LTM: {e}")

    # 3. Cache Write Gate (score >= threshold and not degraded)
    if score >= settings.SEMANTIC_CACHE_WRITE_GATE_SCORE and not is_degraded:
        try:
            await semantic_cache.store_report(query=topic, report_data=final_report)
            logger.info(f"Report for '{topic}' passed write gate (score={score}) and was stored in pgvector semantic cache.")
        except Exception as e:
            logger.warning(f"Failed to store report in semantic cache: {e}")

    # 4. Broadcast pipeline completion
    await event_broadcaster.publish_event(
        session_id=session_id,
        event_type="pipeline_completed",
        data={
            "session_id": session_id,
            "topic": topic,
            "verification_score": score,
            "is_degraded": is_degraded,
            "report_preview": sanitized_text[:300] + "...",
        }
    )

    return {
        "final_report": final_report,
        "defense_telemetry": defense_telemetry,
    }


def route_verification(state: ResearchState) -> Literal["egress_guardrail", "write", "degraded_export"]:
    """Conditional Edge: Determines whether to finalize, loopback to writer, or degrade."""
    score = state.get("verification_score", 1.0)
    iteration_count = state.get("iteration_count", 1)

    if score >= 0.85:
        logger.info(f"Verification passed with score {score:.2f} >= 0.85. Proceeding to egress guardrail.")
        return "egress_guardrail"

    if iteration_count < 2:
        logger.info(f"Verification score {score:.2f} < 0.85. Triggering loopback to write agent (Iteration {iteration_count}/2).")
        return "write"

    logger.warning(f"Verification score {score:.2f} < 0.85 and max iterations ({iteration_count}) exhausted. Triggering degraded export.")
    return "degraded_export"


def build_research_graph():
    """Builds and compiles the 4-agent LangGraph workflow with deterministic guardrails and memory gates."""
    workflow = StateGraph(ResearchState)

    # Register Nodes
    workflow.add_node("search", search_node)
    workflow.add_node("summarize", summarize_node)
    workflow.add_node("write", write_node)
    workflow.add_node("verify", verify_node)
    workflow.add_node("degraded_export", degraded_export_node)
    workflow.add_node("egress_guardrail", egress_guardrail_node)

    # Register Edges
    workflow.add_edge(START, "search")
    workflow.add_edge("search", "summarize")
    workflow.add_edge("summarize", "write")
    workflow.add_edge("write", "verify")

    # Conditional Branch from Verify
    workflow.add_conditional_edges(
        "verify",
        route_verification,
        {
            "egress_guardrail": "egress_guardrail",
            "write": "write",
            "degraded_export": "degraded_export",
        }
    )

    workflow.add_edge("degraded_export", "egress_guardrail")
    workflow.add_edge("egress_guardrail", END)

    return workflow.compile()


# Global compiled pipeline
research_pipeline = build_research_graph()
