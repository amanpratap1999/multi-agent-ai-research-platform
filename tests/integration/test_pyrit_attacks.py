import asyncio

import pytest

from app.redteam.pyrit_runner import redteam_runner


@pytest.mark.asyncio
async def test_pyrit_crescendo_campaign():
    campaign_id = await redteam_runner.start_campaign("crescendo", max_turns=3)
    assert campaign_id is not None

    # Wait for async background worker to process turns
    for _ in range(30):
        campaign = redteam_runner.get_campaign(campaign_id)
        if campaign and campaign.get("status") in ["COMPLETED", "FAILED"]:
            break
        await asyncio.sleep(0.2)

    campaign = redteam_runner.get_campaign(campaign_id)
    assert campaign is not None
    assert campaign.get("status") == "COMPLETED"
    assert len(campaign.get("turns", [])) == 3

    # Check scoring summary
    summary = campaign.get("summary", {})
    assert summary.get("total_turns") == 3
    assert summary.get("block_rate") is not None


@pytest.mark.asyncio
async def test_pyrit_xpia_synthetic_campaign():
    campaign_id = await redteam_runner.start_campaign("xpia")
    assert campaign_id is not None

    for _ in range(30):
        campaign = redteam_runner.get_campaign(campaign_id)
        if campaign and campaign.get("status") in ["COMPLETED", "FAILED"]:
            break
        await asyncio.sleep(0.2)

    campaign = redteam_runner.get_campaign(campaign_id)
    assert campaign is not None
    assert campaign.get("status") == "COMPLETED"
    assert len(campaign.get("turns", [])) == 4

    # Verify quarantine accuracy
    turns = campaign.get("turns", [])
    quarantined = [t for t in turns if "Quarantine: True" in t.get("response", "")]
    assert len(quarantined) == 3  # The 3 injected fixtures must be quarantined


@pytest.mark.asyncio
async def test_pyrit_runner_task_tracking_and_wait():
    """Verifies that PyRIT runner safely tracks async background tasks and wait_for_campaign resolves."""
    campaign_id = await redteam_runner.start_campaign("skeleton_key", max_turns=2)
    assert campaign_id in redteam_runner.active_campaigns
    assert len(campaign_id) == 36  # Full UUID verification

    # Task must be actively tracked in active_tasks while running or completing
    final_campaign = await redteam_runner.wait_for_campaign(campaign_id, timeout=10.0)
    assert final_campaign is not None
    assert final_campaign["status"] == "COMPLETED"
    assert len(final_campaign["turns"]) == 2
    # Task should be pruned from active_tasks after completion
    assert campaign_id not in redteam_runner.active_tasks
