import logging
from typing import Literal

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.events import event_broadcaster
from app.redteam.pyrit_runner import redteam_runner

logger = logging.getLogger("api.redteam")

router = APIRouter(prefix="/redteam", tags=["Red Teaming"])


class CampaignRequest(BaseModel):
    attack_type: Literal["jailbreak", "crescendo", "skeleton_key", "xpia"] = Field(
        default="crescendo",
        description="Type of adversarial campaign"
    )
    max_turns: int | None = Field(default=None, ge=1, le=10, description="Optional cap on campaign turns")


@router.post("/campaigns", status_code=202)
async def launch_campaign(req: CampaignRequest):
    """Dispatches an asynchronous PyRIT adversarial campaign against the designated defense target."""
    campaign_id = await redteam_runner.start_campaign(
        attack_type=req.attack_type,
        max_turns=req.max_turns
    )
    return {
        "campaign_id": campaign_id,
        "attack_type": req.attack_type,
        "status": "QUEUED",
        "stream_url": f"/api/v1/redteam/stream/{campaign_id}",
    }


@router.get("/stream/{campaign_id}")
async def stream_campaign_events(
    campaign_id: str,
    last_event_id: str | None = Header(None, alias="Last-Event-ID")
):
    """Server-Sent Events (SSE) stream for real-time attack progression with Last-Event-ID reconnection."""
    stream_id = f"redteam_{campaign_id}"

    async def event_generator():
        async for sse_chunk in event_broadcaster.stream_events(session_id=stream_id, last_event_id=last_event_id):
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


@router.get("/campaigns/{campaign_id}")
async def get_campaign_status(campaign_id: str):
    """Retrieves current execution status, turns, and defense scorecards for a campaign."""
    campaign = redteam_runner.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign
