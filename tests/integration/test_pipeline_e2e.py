import pytest

from app.agents.graph import research_pipeline
from app.export.exporter import exporter


@pytest.mark.asyncio
async def test_full_research_pipeline_e2e():
    initial_state = {
        "topic": "Zero Trust Architecture in Cloud Native Infrastructure",
        "session_id": "test-e2e-session",
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
        "defense_telemetry": [],
    }

    final_state = await research_pipeline.ainvoke(initial_state)

    assert "final_report" in final_state
    report = final_state["final_report"]
    assert report["topic"] == "Zero Trust Architecture in Cloud Native Infrastructure"
    assert len(report["report_markdown"]) > 100
    assert report["verification_score"] > 0.0
    assert "sources" in report
    assert "claims_audit" in report

    # Test pure-Python exports
    md_content = exporter.export_markdown(report)
    assert "# " in md_content
    assert "Exported by Autonomous Multi-Agent AI Research Platform" in md_content

    json_content = exporter.export_json(report)
    assert "Zero Trust" in json_content

    pdf_bytes = exporter.export_pdf(report)
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF")
