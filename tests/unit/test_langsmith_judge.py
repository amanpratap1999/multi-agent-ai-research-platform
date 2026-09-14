import pytest

from app.agents.verify_agent import verify_node
from app.evaluation.langsmith_judge import langsmith_judge


@pytest.mark.asyncio
async def test_langsmith_judge_metrics_calculation():
    claims_audit = [
        {
            "claim": "Autonomous multi-agent pipelines require isolation.",
            "citation_url": "https://arxiv.org/abs/2401.multi-agent-eval",
            "verdict": "SUPPORTED",
            "quoted_evidence": "Rigorous isolation prevents prompt injection.",
        },
        {
            "claim": "PostgreSQL pgvector HNSW provides sub-15ms latency.",
            "citation_url": "https://pgvector.dev/benchmarks/hnsw-scaling",
            "verdict": "SUPPORTED",
            "quoted_evidence": "HNSW index benchmarks demonstrate p99 query latency under 12ms.",
        },
        {
            "claim": "Hallucinations can be eliminated with 100% certainty.",
            "citation_url": "",
            "verdict": "CONTRADICTED",
            "quoted_evidence": "",
        },
    ]

    eval_record = await langsmith_judge.submit_evaluation(
        session_id="test-session-judge-1",
        topic="Multi-Agent Security",
        draft_report="# Report\nContent with verified citations.",
        claims_audit=claims_audit,
        verification_score=0.67,
        feedback="Claim 3 was contradicted.",
        iteration=1,
    )

    assert eval_record is not None
    metrics = eval_record["metrics"]
    assert metrics["accuracy_score"] == 0.67
    assert metrics["grounding_score"] == 0.67
    assert metrics["citation_score"] == 0.67
    assert metrics["supported_count"] == 2
    assert metrics["contradicted_count"] == 1
    assert metrics["unverified_count"] == 0
    assert eval_record["session_id"] == "test-session-judge-1"
    assert "timestamp" in eval_record
    assert len(langsmith_judge.evaluation_history) > 0


@pytest.mark.asyncio
async def test_verify_agent_submits_to_langsmith():
    """Verifies that verify_node automatically triggers LangSmith evaluation recording."""
    initial_count = len(langsmith_judge.evaluation_history)

    state = {
        "topic": "Zero Trust Security",
        "session_id": "test-verify-langsmith-session",
        "draft_report": "Empirical studies show 38% reduction in lateral attacks.",
        "scrubbed_sources": [
            {
                "id": "src-1",
                "title": "Zero Trust Benchmarks",
                "url": "https://example.com/zt",
                "snippet": "Study confirms 38% reduction in lateral attacks.",
            }
        ],
        "iteration_count": 0,
    }

    result = await verify_node(state)
    assert "claims_audit" in result
    assert "verification_score" in result

    # An evaluation record should have been appended to langsmith_judge history
    assert len(langsmith_judge.evaluation_history) == initial_count + 1
    latest = langsmith_judge.evaluation_history[-1]
    assert latest["session_id"] == "test-verify-langsmith-session"
    assert latest["metrics"]["accuracy_score"] == result["verification_score"]
