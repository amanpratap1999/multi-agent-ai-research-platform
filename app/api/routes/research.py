import logging
import uuid
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agents.graph import research_pipeline
from app.core.events import event_broadcaster
from app.defense.bedrock_guardrail import guardrail_client
from app.export.exporter import exporter
from app.memory.redis_stm import redis_stm
from app.memory.semantic_cache import semantic_cache

logger = logging.getLogger("api.research")

router = APIRouter(prefix="/research", tags=["Research"])


class ResearchRequest(BaseModel):
    topic: str = Field(..., min_length=2, max_length=500, description="Research topic or question")
    bypass_cache: bool = Field(default=False, description="Bypass pgvector semantic cache")


# In-memory session registry for fast state retrieval
active_sessions: dict[str, dict] = {}


@router.post("", status_code=202)
async def submit_research(req: ResearchRequest, background_tasks: BackgroundTasks):
    """Initiates an autonomous 4-agent research run with Bedrock Ingress defense and pgvector semantic cache check."""
    topic = req.topic.strip()

    # 1. Ingress Bedrock Guardrail Evaluation
    guardrail_result = await guardrail_client.apply_guardrail(
        text=topic,
        source="INPUT",
        boundary="ingress"
    )
    if guardrail_result["action"] == "GUARDRAIL_INTERVENED":
        raise HTTPException(
            status_code=400,
            detail={
                "error": "TOPIC_BLOCKED_BY_GUARDRAIL",
                "message": "The proposed research topic violates safety policies.",
                "policy": guardrail_result.get("policy"),
                "telemetry": guardrail_result.get("telemetry"),
            }
        )

    # 2. Check pgvector Semantic Cache (unless bypass requested)
    if not req.bypass_cache:
        cache_hit = await semantic_cache.lookup(topic)
        if cache_hit:
            logger.info(f"pgvector semantic cache HIT for '{topic}' (similarity: {cache_hit.similarity_score:.4f})")
            return {
                "cached": True,
                "similarity_score": cache_hit.similarity_score,
                "latency_ms": cache_hit.latency_ms,
                "final_report": cache_hit.report_data,
            }

    # 3. Cache Miss — Initialize Agent Session
    session_id = str(uuid.uuid4())
    initial_state = {
        "topic": topic,
        "session_id": session_id,
        "search_queries": [],
        "raw_sources": [],
        "scrubbed_sources": [],
        "quarantined_sources": [],
        "summary": "",
        "draft_report": "",
        "claims_audit": [],
        "verification_feedback": "",
        "verification_score": 0.0,
        "iteration_count": 0,
        "is_degraded": False,
        "final_report": {},
        "defense_telemetry": [guardrail_result["telemetry"]],
    }

    active_sessions[session_id] = {
        "session_id": session_id,
        "topic": topic,
        "status": "RUNNING",
        "state": initial_state,
    }

    # Launch LangGraph pipeline asynchronously
    async def run_pipeline_task():
        try:
            final_output = await research_pipeline.ainvoke(initial_state)
            if session_id in active_sessions:
                active_sessions[session_id]["status"] = "COMPLETED"
                active_sessions[session_id]["state"] = final_output
                await redis_stm.set_session_state(session_id, final_output)
        except Exception as e:
            logger.error(f"Pipeline execution error for session {session_id}: {e}", exc_info=True)
            if session_id in active_sessions:
                active_sessions[session_id]["status"] = "FAILED"
                active_sessions[session_id]["error"] = str(e)
            await event_broadcaster.publish_event(
                session_id=session_id,
                event_type="pipeline_failed",
                data={"session_id": session_id, "error": str(e)}
            )

    background_tasks.add_task(run_pipeline_task)

    return {
        "cached": False,
        "session_id": session_id,
        "status": "QUEUED",
        "stream_url": f"/api/v1/research/stream/{session_id}",
    }


@router.get("/stream/{session_id}")
async def stream_research_events(
    session_id: str,
    last_event_id: str | None = Header(None, alias="Last-Event-ID")
):
    """Server-Sent Events (SSE) endpoint reading from Redis Streams with replay via Last-Event-ID."""
    async def event_generator():
        async for sse_chunk in event_broadcaster.stream_events(session_id=session_id, last_event_id=last_event_id):
            yield sse_chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/status/{session_id}")
@router.get("/{session_id}")
async def get_research_status(session_id: str):
    """Queries current pipeline execution state."""
    # Check in-memory first
    if session_id in active_sessions:
        data = active_sessions[session_id]
        return {
            "session_id": session_id,
            "topic": data.get("topic"),
            "status": data.get("status"),
            "final_report": data.get("state", {}).get("final_report", {}),
            "verification_score": data.get("state", {}).get("verification_score", 0.0),
            "is_degraded": data.get("state", {}).get("is_degraded", False),
        }

    # Check Redis STM
    redis_state = await redis_stm.get_session_state(session_id)
    if redis_state:
        return {
            "session_id": session_id,
            "status": "COMPLETED",
            "final_report": redis_state.get("final_report", {}),
            "verification_score": redis_state.get("verification_score", 0.0),
            "is_degraded": redis_state.get("is_degraded", False),
        }

    raise HTTPException(status_code=404, detail="Research session not found")


@router.get("/export/{session_id}")
async def export_research_report(
    session_id: str,
    format: Literal["markdown", "json", "pdf"] = Query("markdown", description="Export file format")
):
    """Exports the final research report in Markdown, JSON, or pure-Python PDF."""
    report_data = None
    if session_id in active_sessions:
        report_data = active_sessions[session_id].get("state", {}).get("final_report", {})
    if not report_data:
        redis_state = await redis_stm.get_session_state(session_id)
        if redis_state:
            report_data = redis_state.get("final_report", {})

    if not report_data or not report_data.get("report_markdown"):
        raise HTTPException(status_code=404, detail="Final report not yet generated or session not found")

    if format == "markdown":
        md_text = exporter.export_markdown(report_data)
        return Response(
            content=md_text,
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="report_{session_id}.md"'}
        )
    elif format == "json":
        json_str = exporter.export_json(report_data)
        return Response(
            content=json_str,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="report_{session_id}.json"'}
        )
    elif format == "pdf":
        pdf_bytes = exporter.export_pdf(report_data)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="report_{session_id}.pdf"'}
        )
